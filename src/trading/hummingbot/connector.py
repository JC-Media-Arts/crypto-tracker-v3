"""
Hummingbot Connector

Bridges our ML Signal Generator with Hummingbot's trading engine.
Manages communication between our system and Hummingbot.
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger
import docker
from docker.errors import NotFound, APIError

from src.data.supabase_client import SupabaseClient
from src.strategies.signal_generator import SignalGenerator


class HummingbotConnector:
    """Manages connection and communication with Hummingbot."""

    def __init__(
        self,
        supabase_client: SupabaseClient,
        signal_generator: SignalGenerator,
        config: Optional[Dict] = None,
    ):
        """
        Initialize Hummingbot Connector.

        Args:
            supabase_client: Database client
            signal_generator: Signal generator instance
            config: Connector configuration
        """
        self.supabase = supabase_client
        self.signal_generator = signal_generator
        self.config = config or self._default_config()

        # Docker client for managing Hummingbot container
        try:
            self.docker_client = docker.from_env()
        except Exception as e:
            logger.error(f"Failed to connect to Docker: {e}")
            self.docker_client = None

        # State tracking
        self.hummingbot_container = None
        self.is_running = False
        self.last_health_check = None

    def _default_config(self) -> Dict:
        """Default connector configuration."""
        return {
            "container_name": "crypto-tracker-hummingbot",
            "health_check_interval": 60,  # seconds
            "signal_sync_interval": 30,  # seconds
            "max_retries": 3,
            "retry_delay": 5,  # seconds
        }

    async def start(self):
        """Start Hummingbot and begin signal synchronization."""
        try:
            # Check if Hummingbot container exists
            if not self._check_container():
                logger.error(
                    "Hummingbot container not found. Please run setup_hummingbot.sh first."
                )
                return False

            # Start container if not running
            if not self._is_container_running():
                logger.info("Starting Hummingbot container...")
                self.hummingbot_container.start()
                await asyncio.sleep(10)  # Wait for startup

            # Start signal generator monitoring
            await self.signal_generator.start_monitoring()

            # Start synchronization loop
            self.is_running = True
            asyncio.create_task(self._sync_loop())

            logger.info("Hummingbot connector started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start Hummingbot connector: {e}")
            return False

    async def stop(self):
        """Stop Hummingbot and signal synchronization."""
        try:
            self.is_running = False

            # Stop signal generator
            await self.signal_generator.stop_monitoring()

            # Optionally stop Hummingbot container
            if self.config.get("stop_container_on_exit", False):
                if self.hummingbot_container:
                    logger.info("Stopping Hummingbot container...")
                    self.hummingbot_container.stop()

            logger.info("Hummingbot connector stopped")

        except Exception as e:
            logger.error(f"Error stopping Hummingbot connector: {e}")

    def _check_container(self) -> bool:
        """Check if Hummingbot container exists."""
        if not self.docker_client:
            return False

        try:
            self.hummingbot_container = self.docker_client.containers.get(
                self.config["container_name"]
            )
            return True
        except NotFound:
            return False
        except Exception as e:
            logger.error(f"Error checking container: {e}")
            return False

    def _is_container_running(self) -> bool:
        """Check if Hummingbot container is running."""
        if not self.hummingbot_container:
            return False

        try:
            self.hummingbot_container.reload()
            return self.hummingbot_container.status == "running"
        except Exception as e:
            logger.error(f"Error checking container status: {e}")
            return False

    async def _sync_loop(self):
        """Main synchronization loop between Signal Generator and Hummingbot."""
        while self.is_running:
            try:
                # Sync signals to database for Hummingbot to read
                await self._sync_signals()

                # Check Hummingbot health
                await self._health_check()

                # Sync trade results back
                await self._sync_trade_results()

                # Wait before next sync
                await asyncio.sleep(self.config["signal_sync_interval"])

            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
                await asyncio.sleep(self.config["retry_delay"])

    async def _sync_signals(self):
        """Sync active signals to database for Hummingbot to read."""
        try:
            # Get active signals
            signals = self.signal_generator.get_active_signals()

            for signal in signals:
                # Check if signal already exists in database
                existing = (
                    self.supabase.client.table("ml_predictions")
                    .select("*")
                    .eq("symbol", signal["symbol"])
                    .eq("strategy_name", signal.get("strategy", "DCA"))
                    .gte(
                        "timestamp", (datetime.now() - timedelta(minutes=5)).isoformat()
                    )
                    .execute()
                )

                if not existing.data:
                    # Insert new signal
                    prediction_data = {
                        "timestamp": datetime.now().isoformat(),
                        "strategy_name": signal.get("strategy", "DCA"),
                        "symbol": signal["symbol"],
                        "prediction": "TAKE_SETUP"
                        if signal["status"] == "APPROVED"
                        else "SKIP_SETUP",
                        "confidence": signal.get("confidence", 0.5),
                        "optimal_take_profit": signal.get("ml_predictions", {}).get(
                            "take_profit_percent", 10.0
                        ),
                        "optimal_stop_loss": signal.get("ml_predictions", {}).get(
                            "stop_loss_percent", -5.0
                        ),
                        "position_size_mult": signal.get("ml_predictions", {}).get(
                            "position_size_multiplier", 1.0
                        ),
                        "expected_hold_hours": signal.get("ml_predictions", {}).get(
                            "hold_time", 24
                        ),
                        "features_used": json.dumps(signal.get("setup_data", {})),
                    }

                    self.supabase.client.table("ml_predictions").insert(
                        prediction_data
                    ).execute()

                    logger.info(f"Synced signal for {signal['symbol']} to database")

        except Exception as e:
            logger.error(f"Error syncing signals: {e}")

    async def _health_check(self):
        """Check Hummingbot health and status."""
        try:
            if not self._is_container_running():
                logger.warning("Hummingbot container is not running")
                # Attempt to restart
                if self.config.get("auto_restart", True):
                    logger.info("Attempting to restart Hummingbot...")
                    self.hummingbot_container.start()
                    await asyncio.sleep(10)

            # Check container logs for errors
            if self.hummingbot_container:
                logs = self.hummingbot_container.logs(tail=100, timestamps=True)
                log_lines = logs.decode("utf-8").split("\n")

                # Look for error patterns
                for line in log_lines[-20:]:  # Check last 20 lines
                    if "ERROR" in line or "CRITICAL" in line:
                        logger.warning(f"Hummingbot error detected: {line}")

            # Update health status in database
            health_data = {
                "timestamp": datetime.now().isoformat(),
                "metric_name": "hummingbot_health",
                "status": "HEALTHY" if self._is_container_running() else "UNHEALTHY",
                "value": 1.0 if self._is_container_running() else 0.0,
            }

            self.supabase.client.table("health_metrics").insert(health_data).execute()

            self.last_health_check = datetime.now()

        except Exception as e:
            logger.error(f"Error in health check: {e}")

    async def _sync_trade_results(self):
        """Sync trade results from Hummingbot back to our system."""
        try:
            # Query recent trades from Hummingbot database
            recent_trades = (
                self.supabase.client.table("hummingbot_trades")
                .select("*")
                .gte("created_at", (datetime.now() - timedelta(minutes=5)).isoformat())
                .execute()
            )

            for trade in recent_trades.data:
                # Update setup outcomes if this was from a signal
                if trade.get("setup_id"):
                    outcome = "WIN" if trade.get("pnl", 0) > 0 else "LOSS"

                    self.supabase.client.table("strategy_setups").update(
                        {
                            "outcome": outcome,
                            "pnl": trade.get("pnl", 0),
                            "is_executed": True,
                            "executed_at": trade.get("filled_at"),
                        }
                    ).eq("setup_id", trade["setup_id"]).execute()

                # Update ML predictions with actual outcome
                if trade.get("ml_confidence"):
                    self.supabase.client.table("ml_predictions").update(
                        {
                            "actual_outcome": outcome,
                            "correct": (
                                outcome == "WIN" and trade.get("ml_confidence", 0) > 0.5
                            )
                            or (
                                outcome == "LOSS"
                                and trade.get("ml_confidence", 0) <= 0.5
                            ),
                        }
                    ).eq("symbol", trade["symbol"]).eq(
                        "timestamp", trade["created_at"]
                    ).execute()

        except Exception as e:
            logger.error(f"Error syncing trade results: {e}")

    def get_status(self) -> Dict:
        """Get current status of Hummingbot connector."""
        return {
            "connector_running": self.is_running,
            "container_exists": self._check_container(),
            "container_running": self._is_container_running(),
            "last_health_check": self.last_health_check.isoformat()
            if self.last_health_check
            else None,
            "signal_generator_active": self.signal_generator.monitoring_active,
            "active_signals": len(self.signal_generator.get_active_signals()),
        }

    async def execute_command(self, command: str) -> str:
        """
        Execute a command in the Hummingbot container.

        Args:
            command: Command to execute

        Returns:
            Command output
        """
        if not self.hummingbot_container:
            return "Error: Hummingbot container not found"

        try:
            result = self.hummingbot_container.exec_run(command)
            return result.output.decode("utf-8")
        except Exception as e:
            return f"Error executing command: {e}"

    async def get_performance_stats(self) -> Dict:
        """Get performance statistics from Hummingbot."""
        try:
            # Query aggregated performance from database
            trades = (
                self.supabase.client.table("hummingbot_trades").select("*").execute()
            )

            if not trades.data:
                return {
                    "total_trades": 0,
                    "win_rate": 0,
                    "total_pnl": 0,
                    "avg_pnl": 0,
                }

            total_trades = len(trades.data)
            wins = sum(1 for t in trades.data if t.get("pnl", 0) > 0)
            total_pnl = sum(t.get("pnl", 0) for t in trades.data)

            return {
                "total_trades": total_trades,
                "win_rate": (wins / total_trades * 100) if total_trades > 0 else 0,
                "total_pnl": total_pnl,
                "avg_pnl": total_pnl / total_trades if total_trades > 0 else 0,
                "winning_trades": wins,
                "losing_trades": total_trades - wins,
            }

        except Exception as e:
            logger.error(f"Error getting performance stats: {e}")
            return {}
