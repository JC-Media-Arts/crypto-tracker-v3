"""
Health monitoring and endpoint for the crypto tracker system.
"""

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any
import asyncio
import psutil
import os
from loguru import logger

from src.config.settings import get_settings
from src.data.supabase_client import SupabaseClient


app = FastAPI(title="Crypto Tracker Health API", version="1.0.0")


class HealthChecker:
    """System health checker."""

    def __init__(self):
        """Initialize health checker."""
        self.settings = get_settings()
        self.db_client = SupabaseClient()

        # Track last successful checks
        self.last_data_update: Optional[datetime] = None
        self.last_ml_prediction: Optional[datetime] = None
        self.last_feature_calculation: Optional[datetime] = None
        self.database_connected: bool = False

        # System metrics
        self.start_time = datetime.now(timezone.utc)

    async def check_database(self) -> Dict[str, Any]:
        """Check database connectivity and performance."""
        try:
            # Test basic connectivity
            start_time = datetime.now()
            result = self.db_client.client.table("ohlc_data").select("timestamp").limit(1).execute()
            query_time = (datetime.now() - start_time).total_seconds()

            self.database_connected = True

            return {
                "connected": True,
                "query_time_seconds": query_time,
                "healthy": query_time < 1.0,  # Query should complete in under 1 second
            }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            self.database_connected = False
            return {"connected": False, "error": str(e), "healthy": False}

    async def check_data_freshness(self) -> Dict[str, Any]:
        """Check if data is being updated regularly."""
        try:
            # Check latest data timestamp for each timeframe
            timeframes = ["1d", "1h", "15m"]
            freshness = {}

            for tf in timeframes:
                result = (
                    self.db_client.client.table("ohlc_data")
                    .select("timestamp")
                    .eq("timeframe", tf)
                    .order("timestamp", desc=True)
                    .limit(1)
                    .execute()
                )

                if result.data:
                    latest = datetime.fromisoformat(result.data[0]["timestamp"].replace("Z", "+00:00"))
                    age_minutes = (datetime.now(timezone.utc) - latest).total_seconds() / 60

                    freshness[tf] = {
                        "latest_timestamp": latest.isoformat(),
                        "age_minutes": round(age_minutes, 2),
                        "healthy": age_minutes < self.settings.data_freshness_threshold / 60,
                    }
                else:
                    freshness[tf] = {"latest_timestamp": None, "age_minutes": None, "healthy": False}

            # Overall health
            all_healthy = all(f.get("healthy", False) for f in freshness.values())

            return {"timeframes": freshness, "healthy": all_healthy}

        except Exception as e:
            logger.error(f"Data freshness check failed: {e}")
            return {"error": str(e), "healthy": False}

    async def check_ml_features(self) -> Dict[str, Any]:
        """Check if ML features are being calculated."""
        try:
            # Check latest ML features
            result = (
                self.db_client.client.table("ml_features")
                .select("timestamp")
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )

            if result.data:
                latest = datetime.fromisoformat(result.data[0]["timestamp"].replace("Z", "+00:00"))
                age_minutes = (datetime.now(timezone.utc) - latest).total_seconds() / 60

                return {
                    "latest_timestamp": latest.isoformat(),
                    "age_minutes": round(age_minutes, 2),
                    "healthy": age_minutes < 30,  # Features should update every 30 minutes
                }
            else:
                return {"latest_timestamp": None, "age_minutes": None, "healthy": False}

        except Exception as e:
            logger.error(f"ML features check failed: {e}")
            return {"error": str(e), "healthy": False}

    async def check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory usage
            memory = psutil.virtual_memory()

            # Disk usage
            disk = psutil.disk_usage("/")

            # Process info
            process = psutil.Process(os.getpid())
            process_memory = process.memory_info()

            return {
                "cpu": {"percent": cpu_percent, "healthy": cpu_percent < 80},
                "memory": {
                    "percent": memory.percent,
                    "used_gb": round(memory.used / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "healthy": memory.percent < 90,
                },
                "disk": {
                    "percent": disk.percent,
                    "free_gb": round(disk.free / (1024**3), 2),
                    "healthy": disk.percent < 90,
                },
                "process": {
                    "memory_mb": round(process_memory.rss / (1024**2), 2),
                    "cpu_percent": process.cpu_percent(),
                },
                "healthy": cpu_percent < 80 and memory.percent < 90 and disk.percent < 90,
            }

        except Exception as e:
            logger.error(f"System resources check failed: {e}")
            return {"error": str(e), "healthy": False}

    async def check_active_services(self) -> Dict[str, Any]:
        """Check which services are currently active."""
        services = {}

        # Check if data collector is running
        try:
            result = (
                self.db_client.client.table("health_metrics")
                .select("*")
                .eq("metric_name", "data_flow")
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )

            if result.data:
                latest = datetime.fromisoformat(result.data[0]["timestamp"].replace("Z", "+00:00"))
                age_seconds = (datetime.now(timezone.utc) - latest).total_seconds()
                services["data_collector"] = {
                    "active": age_seconds < 60,
                    "last_seen": latest.isoformat(),
                    "status": result.data[0].get("status", "unknown"),
                }
            else:
                services["data_collector"] = {"active": False}

        except Exception as e:
            services["data_collector"] = {"active": False, "error": str(e)}

        # Check other services similarly
        # This could be expanded to check more services

        return services

    def get_uptime(self) -> Dict[str, Any]:
        """Get system uptime."""
        uptime_seconds = (datetime.now(timezone.utc) - self.start_time).total_seconds()

        return {
            "start_time": self.start_time.isoformat(),
            "uptime_seconds": uptime_seconds,
            "uptime_hours": round(uptime_seconds / 3600, 2),
            "uptime_days": round(uptime_seconds / 86400, 2),
        }


# Global health checker instance
health_checker = HealthChecker()


@app.get("/health")
async def health_check() -> JSONResponse:
    """
    Comprehensive health check endpoint.

    Returns:
        - 200: System is healthy
        - 503: System is unhealthy
    """
    checks = {}

    # Run all health checks in parallel
    results = await asyncio.gather(
        health_checker.check_database(),
        health_checker.check_data_freshness(),
        health_checker.check_ml_features(),
        health_checker.check_system_resources(),
        health_checker.check_active_services(),
        return_exceptions=True,
    )

    # Process results
    checks["database"] = (
        results[0] if not isinstance(results[0], Exception) else {"healthy": False, "error": str(results[0])}
    )
    checks["data_freshness"] = (
        results[1] if not isinstance(results[1], Exception) else {"healthy": False, "error": str(results[1])}
    )
    checks["ml_features"] = (
        results[2] if not isinstance(results[2], Exception) else {"healthy": False, "error": str(results[2])}
    )
    checks["system_resources"] = (
        results[3] if not isinstance(results[3], Exception) else {"healthy": False, "error": str(results[3])}
    )
    checks["services"] = (
        results[4] if not isinstance(results[4], Exception) else {"healthy": False, "error": str(results[4])}
    )

    # Add uptime
    checks["uptime"] = health_checker.get_uptime()

    # Overall health
    all_healthy = all(
        check.get("healthy", False) for check in checks.values() if isinstance(check, dict) and "healthy" in check
    )

    # Prepare response
    response = {
        "status": "healthy" if all_healthy else "unhealthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }

    # Return appropriate status code
    if all_healthy:
        return JSONResponse(content=response, status_code=200)
    else:
        return JSONResponse(content=response, status_code=503)


@app.get("/health/simple")
async def simple_health_check() -> Response:
    """
    Simple health check for load balancers.

    Returns:
        - 200: OK
        - 503: Service Unavailable
    """
    try:
        # Just check database connectivity
        result = await health_checker.check_database()

        if result.get("healthy", False):
            return Response(content="OK", status_code=200)
        else:
            return Response(content="UNHEALTHY", status_code=503)

    except Exception:
        return Response(content="ERROR", status_code=503)


@app.get("/metrics")
async def get_metrics() -> JSONResponse:
    """
    Get detailed system metrics for monitoring.
    """
    metrics = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime": health_checker.get_uptime(),
        "resources": await health_checker.check_system_resources(),
        "database": await health_checker.check_database(),
        "data": await health_checker.check_data_freshness(),
    }

    return JSONResponse(content=metrics)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Crypto Tracker Health API",
        "version": "1.0.0",
        "endpoints": [
            "/health - Comprehensive health check",
            "/health/simple - Simple health check for load balancers",
            "/metrics - Detailed system metrics",
        ],
    }


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()

    uvicorn.run(app, host="0.0.0.0", port=8080, log_level=settings.log_level.lower())
