#!/usr/bin/env python3
"""
Run the Polygon data collector.
Collects real-time crypto prices and stores them in Supabase.
"""

import asyncio
import sys
import signal
from pathlib import Path
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.collector import DataCollector
from src.config import get_settings


# Global collector instance for signal handling
collector = None


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info("Received shutdown signal, stopping collector...")
    if collector:
        # Cancel all tasks
        for task in asyncio.all_tasks():
            task.cancel()
    sys.exit(0)


async def main():
    """Main function to run the data collector."""
    global collector

    logger.info("Starting Crypto Tracker v3 - Data Collector")

    try:
        # Get settings
        settings = get_settings()
        logger.info(f"Environment: {settings.environment}")

        # Create and start collector
        collector = DataCollector()

        # Set up signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        logger.info("Data collector initialized, starting collection...")

        # Run the collector
        await collector.start()

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Data collector error: {e}")
        raise
    finally:
        logger.info("Data collector stopped")


if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
    )

    # Also log to file
    logger.add("logs/data_collector.log", rotation="1 day", retention="7 days", level="DEBUG")

    # Run the async main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Data collector shut down cleanly")
