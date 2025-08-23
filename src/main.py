#!/usr/bin/env python3
"""
Main entry point for the Crypto ML Trading System.
Coordinates all components and manages the application lifecycle.
"""

import sys
import asyncio
import signal
from pathlib import Path
from loguru import logger
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings
from src.data.collector import DataCollector
from src.ml.predictor import MLPredictor
from src.trading.paper_trader import PaperTrader
from src.monitoring.health_checker import HealthChecker
from src.notifications.slack_notifier import SlackNotifier


class CryptoTrackerApp:
    """Main application class that coordinates all components."""

    def __init__(self):
        """Initialize the application."""
        self.settings = get_settings()
        self.running = False

        # Initialize components
        self.data_collector: Optional[DataCollector] = None
        self.ml_predictor: Optional[MLPredictor] = None
        self.paper_trader: Optional[PaperTrader] = None
        self.health_checker: Optional[HealthChecker] = None
        self.slack_notifier: Optional[SlackNotifier] = None

        # Setup logging
        self._setup_logging()

    def _setup_logging(self):
        """Configure application logging."""
        logger.remove()  # Remove default handler

        # Console logging
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
            level=self.settings.log_level,
        )

        # File logging
        logger.add(
            f"{self.settings.logs_dir}/crypto-tracker.log",
            rotation="100 MB",
            retention="30 days",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level="DEBUG",
        )

        # Error logging
        logger.add(
            f"{self.settings.logs_dir}/errors.log",
            rotation="50 MB",
            retention="30 days",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level="ERROR",
        )

    async def initialize(self):
        """Initialize all components."""
        logger.info("Initializing Crypto Tracker v3...")

        try:
            # Initialize Slack notifier first for alerts
            self.slack_notifier = SlackNotifier(self.settings)
            await self.slack_notifier.initialize()

            # Initialize data collector
            self.data_collector = DataCollector(self.settings)
            await self.data_collector.initialize()

            # Initialize ML predictor
            self.ml_predictor = MLPredictor(self.settings)
            await self.ml_predictor.initialize()

            # Initialize paper trader
            self.paper_trader = PaperTrader(self.settings, self.ml_predictor)
            await self.paper_trader.initialize()

            # Initialize health checker
            self.health_checker = HealthChecker(
                self.settings, self.data_collector, self.ml_predictor, self.paper_trader
            )
            await self.health_checker.initialize()

            logger.success("All components initialized successfully!")
            await self.slack_notifier.send_message(
                "🚀 Crypto Tracker v3 initialized and ready!", channel="system-alerts"
            )

        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            if self.slack_notifier:
                await self.slack_notifier.send_message(
                    f"❌ Failed to initialize: {e}", channel="system-alerts"
                )
            raise

    async def start(self):
        """Start all components."""
        logger.info("Starting Crypto Tracker v3...")
        self.running = True

        try:
            # Start all components
            await asyncio.gather(
                self.data_collector.start(),
                self.ml_predictor.start(),
                self.paper_trader.start(),
                self.health_checker.start(),
            )

            logger.success("All components started!")
            await self.slack_notifier.send_message(
                "✅ All systems operational!", channel="system-alerts"
            )

            # Keep running until stopped
            while self.running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error during execution: {e}")
            await self.shutdown()
            raise

    async def shutdown(self):
        """Gracefully shutdown all components."""
        logger.info("Shutting down Crypto Tracker v3...")
        self.running = False

        # Stop all components
        if self.health_checker:
            await self.health_checker.stop()
        if self.paper_trader:
            await self.paper_trader.stop()
        if self.ml_predictor:
            await self.ml_predictor.stop()
        if self.data_collector:
            await self.data_collector.stop()

        # Send final notification
        if self.slack_notifier:
            await self.slack_notifier.send_message(
                "🛑 Crypto Tracker v3 shutting down", channel="system-alerts"
            )
            await self.slack_notifier.shutdown()

        logger.info("Shutdown complete")

    def handle_signal(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}")
        asyncio.create_task(self.shutdown())


async def main():
    """Main application entry point."""
    app = CryptoTrackerApp()

    # Setup signal handlers
    signal.signal(signal.SIGINT, app.handle_signal)
    signal.signal(signal.SIGTERM, app.handle_signal)

    try:
        await app.initialize()
        await app.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Application error: {e}")
    finally:
        await app.shutdown()


if __name__ == "__main__":
    # Run the application
    asyncio.run(main())
