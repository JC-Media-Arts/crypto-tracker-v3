"""
System Health Monitor
Tracks service health, data freshness, and provides single source of truth
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict
from enum import Enum
from loguru import logger
from src.data.supabase_client import SupabaseClient


class ServiceStatus(Enum):
    RUNNING = "running"
    WARNING = "warning"
    ERROR = "error"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


class ServiceHealth:
    """Represents health status of a service."""

    def __init__(
        self,
        name: str,
        last_heartbeat: datetime,
        status: ServiceStatus,
        metadata: Dict = None,
    ):
        self.name = name
        self.last_heartbeat = last_heartbeat
        self.status = status
        self.metadata = metadata or {}
        self.is_healthy = status == ServiceStatus.RUNNING
        self.minutes_since_heartbeat = self._calculate_age()

    def _calculate_age(self) -> float:
        """Calculate minutes since last heartbeat."""
        now = datetime.now(timezone.utc)
        if self.last_heartbeat:
            # Ensure both are timezone-aware
            if self.last_heartbeat.tzinfo is None:
                self.last_heartbeat = self.last_heartbeat.replace(tzinfo=timezone.utc)
            delta = now - self.last_heartbeat
            return delta.total_seconds() / 60
        return float("inf")

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "last_heartbeat": self.last_heartbeat.isoformat()
            if self.last_heartbeat
            else None,
            "minutes_since": round(self.minutes_since_heartbeat, 1),
            "is_healthy": self.is_healthy,
            "metadata": self.metadata,
        }


class HealthMonitor:
    """Monitors system health across all services."""

    # Expected services and their heartbeat thresholds (minutes)
    SERVICE_THRESHOLDS = {
        "paper_trading_engine": 5,  # Should heartbeat every minute
        "ml_analyzer": 10,  # Runs every 5 minutes
        "strategy_precalculator": 10,  # Runs every 5 minutes
        "ohlc_updater": 20,  # Various schedules
        "shadow_testing": 10,  # If enabled
        "dashboard": 60,  # Less critical
    }

    # Data freshness thresholds (minutes)
    DATA_FRESHNESS = {
        "ohlc_data": 10,  # Should update every 5 minutes
        "strategy_status_cache": 10,  # Updates every 5 minutes
        "market_summary_cache": 10,  # Updates every 5 minutes
        "paper_trades": 1440,  # At least daily activity expected
    }

    def __init__(self):
        self.db = SupabaseClient()
        self.services_health = {}
        self.data_freshness = {}
        self.portfolio_status = {}

    async def check_all_services(self) -> Dict[str, ServiceHealth]:
        """Check health of all services."""
        services = {}

        try:
            # Get all heartbeats from database
            result = self.db.client.table("system_heartbeat").select("*").execute()

            if result.data:
                for heartbeat in result.data:
                    service_name = heartbeat["service_name"]
                    last_heartbeat = datetime.fromisoformat(
                        heartbeat["last_heartbeat"].replace("Z", "+00:00")
                    )

                    # Determine status based on age
                    threshold = self.SERVICE_THRESHOLDS.get(service_name, 30)
                    minutes_old = (
                        datetime.now(timezone.utc) - last_heartbeat
                    ).total_seconds() / 60

                    if minutes_old < threshold:
                        status = ServiceStatus.RUNNING
                    elif minutes_old < threshold * 2:
                        status = ServiceStatus.WARNING
                    else:
                        status = ServiceStatus.ERROR

                    services[service_name] = ServiceHealth(
                        name=service_name,
                        last_heartbeat=last_heartbeat,
                        status=status,
                        metadata=heartbeat.get("metadata", {}),
                    )

            # Check for missing services
            for expected_service in self.SERVICE_THRESHOLDS:
                if expected_service not in services:
                    services[expected_service] = ServiceHealth(
                        name=expected_service,
                        last_heartbeat=None,
                        status=ServiceStatus.UNKNOWN,
                        metadata={},
                    )

            self.services_health = services
            return services

        except Exception as e:
            logger.error(f"Error checking service health: {e}")
            return {}

    async def check_data_freshness(self) -> Dict[str, Dict]:
        """Check freshness of critical data tables."""
        freshness = {}

        for table_name, threshold_minutes in self.DATA_FRESHNESS.items():
            try:
                # Get most recent record
                if table_name == "ohlc_data":
                    # Check BTC as a proxy for all symbols
                    result = (
                        self.db.client.table(table_name)
                        .select("timestamp")
                        .eq("symbol", "BTC")
                        .order("timestamp", desc=True)
                        .limit(1)
                        .execute()
                    )
                else:
                    # Check timestamp or created_at field
                    timestamp_field = (
                        "calculated_at" if "cache" in table_name else "created_at"
                    )
                    result = (
                        self.db.client.table(table_name)
                        .select(timestamp_field)
                        .order(timestamp_field, desc=True)
                        .limit(1)
                        .execute()
                    )

                if result.data:
                    # Get the timestamp
                    if table_name == "ohlc_data":
                        last_update = datetime.fromisoformat(
                            result.data[0]["timestamp"].replace("Z", "+00:00")
                        )
                    else:
                        timestamp_field = (
                            "calculated_at" if "cache" in table_name else "created_at"
                        )
                        last_update = datetime.fromisoformat(
                            result.data[0][timestamp_field].replace("Z", "+00:00")
                        )

                    minutes_old = (
                        datetime.now(timezone.utc) - last_update
                    ).total_seconds() / 60
                    is_fresh = minutes_old <= threshold_minutes

                    freshness[table_name] = {
                        "last_update": last_update.isoformat(),
                        "minutes_old": round(minutes_old, 1),
                        "threshold": threshold_minutes,
                        "is_fresh": is_fresh,
                        "status": "OK" if is_fresh else "STALE",
                    }
                else:
                    freshness[table_name] = {
                        "last_update": None,
                        "minutes_old": float("inf"),
                        "threshold": threshold_minutes,
                        "is_fresh": False,
                        "status": "NO_DATA",
                    }

            except Exception as e:
                logger.error(f"Error checking {table_name} freshness: {e}")
                freshness[table_name] = {
                    "error": str(e),
                    "status": "ERROR",
                }

        self.data_freshness = freshness
        return freshness

    async def get_portfolio_truth(self) -> Dict:
        """Get single source of truth for portfolio status."""
        try:
            # Initialize paper trader to get real state
            from src.trading.simple_paper_trader_v2 import SimplePaperTraderV2

            paper_trader = SimplePaperTraderV2(
                initial_balance=1000.0,
                max_positions=50,
            )

            # Get portfolio stats (this syncs from database)
            stats = paper_trader.get_portfolio_stats()

            # Get open positions
            open_positions = paper_trader.get_open_positions_summary()

            # Calculate additional metrics
            portfolio = {
                "source": "SimplePaperTraderV2 (database sync)",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "balance": {
                    "initial": paper_trader.initial_balance,
                    "current": stats["balance"],
                    "total_value": stats["total_value"],
                },
                "performance": {
                    "total_pnl": stats["total_pnl"],
                    "total_pnl_pct": stats["total_pnl_pct"],
                    "realized_pnl": stats.get("realized_pnl", 0),
                    "unrealized_pnl": stats.get("unrealized_pnl", 0),
                    "win_rate": stats["win_rate"],
                    "total_trades": stats["total_trades"],
                    "winning_trades": stats["winning_trades"],
                },
                "positions": {
                    "open_count": len(open_positions),
                    "max_positions": stats["max_positions"],
                    "utilization": f"{(len(open_positions) / stats['max_positions'] * 100):.0f}%",
                    "positions_value": stats["positions_value"],
                },
                "costs": {
                    "total_fees": stats["total_fees"],
                    "total_slippage": stats["total_slippage"],
                },
            }

            self.portfolio_status = portfolio
            return portfolio

        except Exception as e:
            logger.error(f"Error getting portfolio truth: {e}")
            return {"error": str(e)}

    async def generate_health_report(self) -> Dict:
        """Generate comprehensive health report."""
        # Check all components
        services = await self.check_all_services()
        data_freshness = await self.check_data_freshness()
        portfolio = await self.get_portfolio_truth()

        # Determine overall health
        service_issues = sum(1 for s in services.values() if not s.is_healthy)
        data_issues = sum(
            1 for d in data_freshness.values() if not d.get("is_fresh", False)
        )

        if service_issues == 0 and data_issues == 0:
            overall_status = "HEALTHY"
            overall_emoji = "🟢"
        elif service_issues <= 1 and data_issues <= 1:
            overall_status = "WARNING"
            overall_emoji = "🟡"
        else:
            overall_status = "CRITICAL"
            overall_emoji = "🔴"

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": overall_status,
            "overall_emoji": overall_emoji,
            "services": {
                "healthy": sum(1 for s in services.values() if s.is_healthy),
                "unhealthy": service_issues,
                "total": len(services),
                "details": {
                    name: service.to_dict() for name, service in services.items()
                },
            },
            "data_freshness": {
                "fresh": sum(
                    1 for d in data_freshness.values() if d.get("is_fresh", False)
                ),
                "stale": data_issues,
                "total": len(data_freshness),
                "details": data_freshness,
            },
            "portfolio_truth": portfolio,
        }

        return report

    def format_slack_report(self, report: Dict) -> str:
        """Format health report for Slack."""
        lines = [
            f"{report['overall_emoji']} **SYSTEM HEALTH REPORT**",
            f"Status: {report['overall_status']}",
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S PST')}",
            "",
            "**SERVICE STATUS**",
            f"• Healthy: {report['services']['healthy']}/{report['services']['total']}",
        ]

        # Show unhealthy services
        for name, service in report["services"]["details"].items():
            if not service["is_healthy"]:
                lines.append(
                    f"  ⚠️ {name}: {service['status']} "
                    f"(last seen {service['minutes_since']:.0f}m ago)"
                )

        lines.extend(
            [
                "",
                "**DATA FRESHNESS**",
                f"• Fresh: {report['data_freshness']['fresh']}/{report['data_freshness']['total']}",
            ]
        )

        # Show stale data
        for table, freshness in report["data_freshness"]["details"].items():
            if not freshness.get("is_fresh", False):
                lines.append(
                    f"  ⚠️ {table}: {freshness.get('status', 'UNKNOWN')} "
                    f"({freshness.get('minutes_old', 0):.0f}m old)"
                )

        # Portfolio summary
        portfolio = report["portfolio_truth"]
        if "error" not in portfolio:
            lines.extend(
                [
                    "",
                    "**PORTFOLIO STATUS** (Single Source of Truth)",
                    f"• Balance: ${portfolio['balance']['current']:,.2f}",
                    f"• P&L: ${portfolio['performance']['total_pnl']:+,.2f} "
                    f"({portfolio['performance']['total_pnl_pct']:+.1f}%)",
                    f"• Positions: {portfolio['positions']['open_count']}/{portfolio['positions']['max_positions']} "
                    f"({portfolio['positions']['utilization']})",
                    f"• Win Rate: {portfolio['performance']['win_rate']:.1f}%",
                ]
            )

        return "\n".join(lines)


class ServiceHeartbeat:
    """Helper class for services to report heartbeats."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.db = SupabaseClient()

    async def send_heartbeat(self, metadata: Dict = None):
        """Send a heartbeat for this service."""
        try:
            data = {
                "service_name": self.service_name,
                "last_heartbeat": datetime.now(timezone.utc).isoformat(),
                "status": "running",
                "metadata": metadata or {},
            }

            # Upsert (insert or update)
            (
                self.db.client.table("system_heartbeat")
                .upsert(data, on_conflict="service_name")
                .execute()
            )

            logger.debug(f"Heartbeat sent for {self.service_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to send heartbeat for {self.service_name}: {e}")
            return False

    async def send_error(self, error_message: str):
        """Report an error state."""
        try:
            data = {
                "service_name": self.service_name,
                "last_heartbeat": datetime.now(timezone.utc).isoformat(),
                "status": "error",
                "metadata": {"error": error_message},
            }

            (
                self.db.client.table("system_heartbeat")
                .upsert(data, on_conflict="service_name")
                .execute()
            )

            return True

        except Exception as e:
            logger.error(f"Failed to report error for {self.service_name}: {e}")
            return False


async def main():
    """Test the health monitoring system."""
    monitor = HealthMonitor()

    # Generate health report
    report = await monitor.generate_health_report()

    # Format for display
    print("\n" + "=" * 60)
    print("SYSTEM HEALTH REPORT")
    print("=" * 60)

    # Services
    print(f"\n{report['overall_emoji']} Overall Status: {report['overall_status']}")
    print(
        f"\nServices ({report['services']['healthy']}/{report['services']['total']} healthy):"
    )
    for name, service in report["services"]["details"].items():
        emoji = "✅" if service["is_healthy"] else "❌"
        print(
            f"  {emoji} {name}: {service['status']} (last: {service['minutes_since']:.1f}m ago)"
        )

    # Data freshness
    print(
        f"\nData Freshness ({report['data_freshness']['fresh']}/{report['data_freshness']['total']} fresh):"
    )
    for table, freshness in report["data_freshness"]["details"].items():
        emoji = "✅" if freshness.get("is_fresh", False) else "❌"
        print(
            f"  {emoji} {table}: {freshness.get('status')} ({freshness.get('minutes_old', 0):.1f}m old)"
        )

    # Portfolio
    portfolio = report["portfolio_truth"]
    if "error" not in portfolio:
        print("\nPortfolio (Source of Truth):")
        print(f"  Balance: ${portfolio['balance']['current']:,.2f}")
        print(
            f"  P&L: ${portfolio['performance']['total_pnl']:+,.2f} ({portfolio['performance']['total_pnl_pct']:+.1f}%)"
        )
        print(
            f"  Positions: {portfolio['positions']['open_count']}/{portfolio['positions']['max_positions']}"
        )
        print(f"  Win Rate: {portfolio['performance']['win_rate']:.1f}%")

    # Slack format
    print("\n" + "=" * 60)
    print("SLACK FORMAT:")
    print("=" * 60)
    slack_report = monitor.format_slack_report(report)
    print(slack_report)


if __name__ == "__main__":
    asyncio.run(main())
