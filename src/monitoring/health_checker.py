"""
Health monitoring module for system health checks.
Monitors data flow, ML predictions, and trading performance.
"""

import asyncio
from datetime import datetime
from typing import Dict, Optional, Any
from loguru import logger

from src.config import Settings
from src.data.supabase_client import SupabaseClient


class HealthChecker:
    """Monitors system health and performance."""

    # Health check configuration from master plan
    HEALTH_CONFIG = {
        "data_flow": {
            "check_frequency": 300,  # 5 minutes
            "alert_threshold": 600,  # Alert if no data for 10 minutes
        },
        "price_sanity": {
            "check_frequency": 60,  # 1 minute
            "max_change_pct": 50,  # Alert if price changes > 50% in 1 min
        },
        "ml_health": {
            "check_frequency": 1800,  # 30 minutes
            "alert_threshold": 1800,  # Alert if no predictions for 30 min
        },
    }

    def __init__(
        self,
        settings: Settings,
        data_collector: Any,
        ml_predictor: Any,
        paper_trader: Any,
    ):
        """Initialize health checker."""
        self.settings = settings
        self.data_collector = data_collector
        self.ml_predictor = ml_predictor
        self.paper_trader = paper_trader
        self.db_client: Optional[SupabaseClient] = None
        self.running = False

        # Health metrics
        self.last_data_time = datetime.utcnow()
        self.last_prediction_time = datetime.utcnow()
        self.data_flow_healthy = True
        self.ml_healthy = True
        self.trading_healthy = True

    async def initialize(self):
        """Initialize health checker."""
        logger.info("Initializing health checker...")

        try:
            # Initialize database client
            self.db_client = SupabaseClient(self.settings)
            await self.db_client.initialize()

            logger.success("Health checker initialized")

        except Exception as e:
            logger.error(f"Failed to initialize health checker: {e}")
            raise

    async def start(self):
        """Start health monitoring."""
        logger.info("Starting health monitoring...")
        self.running = True

        # Start health check tasks
        asyncio.create_task(self._check_data_flow())
        asyncio.create_task(self._check_price_sanity())
        asyncio.create_task(self._check_ml_health())
        asyncio.create_task(self._check_trading_health())

        logger.success("Health monitoring started")

    async def _check_data_flow(self):
        """Check if data is flowing properly."""
        while self.running:
            try:
                # Check if we're receiving data
                active_symbols = self.data_collector.get_active_symbols()

                if active_symbols:
                    self.last_data_time = datetime.utcnow()
                    self.data_flow_healthy = True

                    await self._record_metric(
                        {
                            "metric_name": "data_flow",
                            "status": "healthy",
                            "value": len(active_symbols),
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )
                else:
                    # Check how long since last data
                    time_since_data = (
                        datetime.utcnow() - self.last_data_time
                    ).total_seconds()

                    if (
                        time_since_data
                        > self.HEALTH_CONFIG["data_flow"]["alert_threshold"]
                    ):
                        self.data_flow_healthy = False
                        await self._send_alert(
                            "Data Flow Issue",
                            f"No data received for {time_since_data/60:.1f} minutes",
                        )

                await asyncio.sleep(self.HEALTH_CONFIG["data_flow"]["check_frequency"])

            except Exception as e:
                logger.error(f"Error checking data flow: {e}")
                await asyncio.sleep(60)

    async def _check_price_sanity(self):
        """Check for abnormal price movements."""
        while self.running:
            try:
                # Track price changes
                price_changes = {}

                for symbol in self.data_collector.get_active_symbols()[:10]:
                    current_price = self.data_collector.get_last_price(symbol)

                    if symbol in price_changes and current_price:
                        last_price = price_changes[symbol]
                        change_pct = abs(
                            (current_price - last_price) / last_price * 100
                        )

                        if (
                            change_pct
                            > self.HEALTH_CONFIG["price_sanity"]["max_change_pct"]
                        ):
                            await self._send_alert(
                                "Price Anomaly",
                                f"{symbol} changed {change_pct:.1f}% in 1 minute",
                            )

                    price_changes[symbol] = current_price

                await asyncio.sleep(
                    self.HEALTH_CONFIG["price_sanity"]["check_frequency"]
                )

            except Exception as e:
                logger.error(f"Error checking price sanity: {e}")
                await asyncio.sleep(60)

    async def _check_ml_health(self):
        """Check ML prediction health."""
        while self.running:
            try:
                # Get ML status
                ml_status = self.ml_predictor.get_model_status()

                if ml_status["model_loaded"]:
                    self.ml_healthy = True

                    # Check prediction frequency
                    if ml_status["active_predictions"] > 0:
                        self.last_prediction_time = datetime.utcnow()
                    else:
                        time_since_prediction = (
                            datetime.utcnow() - self.last_prediction_time
                        ).total_seconds()

                        if (
                            time_since_prediction
                            > self.HEALTH_CONFIG["ml_health"]["alert_threshold"]
                        ):
                            self.ml_healthy = False
                            await self._send_alert(
                                "ML Issue",
                                f"No predictions for {time_since_prediction/60:.1f} minutes",
                            )

                    # Check model accuracy
                    if ml_status["model_accuracy"] < 0.50:
                        await self._send_alert(
                            "ML Accuracy Warning",
                            f'Model accuracy dropped to {ml_status["model_accuracy"]:.1%}',
                        )
                else:
                    self.ml_healthy = False
                    await self._send_alert("ML Issue", "Model not loaded")

                await self._record_metric(
                    {
                        "metric_name": "ml_health",
                        "status": "healthy" if self.ml_healthy else "unhealthy",
                        "value": ml_status["model_accuracy"],
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

                await asyncio.sleep(self.HEALTH_CONFIG["ml_health"]["check_frequency"])

            except Exception as e:
                logger.error(f"Error checking ML health: {e}")
                await asyncio.sleep(60)

    async def _check_trading_health(self):
        """Check trading system health."""
        while self.running:
            try:
                # Get trading status
                trading_status = self.paper_trader.get_status()

                self.trading_healthy = trading_status["trading_enabled"]

                # Check for issues
                if trading_status["consecutive_losses"] >= 5:
                    await self._send_alert(
                        "Trading Alert",
                        f'{trading_status["consecutive_losses"]} consecutive losses',
                    )

                if trading_status["daily_pnl"] < -50:
                    await self._send_alert(
                        "P&L Alert", f'Daily P&L: ${trading_status["daily_pnl"]:.2f}'
                    )

                await self._record_metric(
                    {
                        "metric_name": "trading_health",
                        "status": "healthy" if self.trading_healthy else "unhealthy",
                        "value": trading_status["daily_pnl"],
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

                await asyncio.sleep(300)  # Check every 5 minutes

            except Exception as e:
                logger.error(f"Error checking trading health: {e}")
                await asyncio.sleep(60)

    async def _record_metric(self, metric: Dict):
        """Record health metric to database."""
        try:
            await self.db_client.insert_health_metric(metric)
        except Exception as e:
            logger.error(f"Failed to record metric: {e}")

    async def _send_alert(self, alert_type: str, message: str):
        """Send health alert."""
        logger.warning(f"Health Alert - {alert_type}: {message}")

        # Send to Slack if available
        try:
            from src.notifications.slack_notifier import SlackNotifier

            # Note: In production, we'd have a reference to the notifier
            # For now, just log the alert
        except Exception:
            pass

    async def stop(self):
        """Stop health monitoring."""
        logger.info("Stopping health monitoring...")
        self.running = False
        logger.info("Health monitoring stopped")

    def get_health_status(self) -> Dict:
        """Get overall health status."""
        return {
            "data_flow": self.data_flow_healthy,
            "ml_system": self.ml_healthy,
            "trading_system": self.trading_healthy,
            "last_data": self.last_data_time.isoformat(),
            "last_prediction": self.last_prediction_time.isoformat(),
            "overall_health": all(
                [self.data_flow_healthy, self.ml_healthy, self.trading_healthy]
            ),
        }
