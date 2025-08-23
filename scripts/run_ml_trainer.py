#!/usr/bin/env python3
"""
ML Model Trainer Runner

Trains the XGBoost model for crypto price prediction.
Runs on a schedule (e.g., daily at 2 AM).
"""

import asyncio
import sys
import os
from datetime import datetime, timezone, time as datetime_time
from loguru import logger

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.settings import get_settings

settings = get_settings()

# Configure logger
logger.remove()
logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
)
logger.add("logs/ml_trainer.log", rotation="100 MB", retention="7 days")


async def train_model():
    """Train the ML model"""
    logger.info("Starting ML model training...")

    # TODO: Implement model training
    # This is a placeholder for now
    logger.info("ML model training not yet implemented")

    # Simulate training time
    await asyncio.sleep(5)

    logger.info("ML model training complete")


async def wait_until_next_training_time():
    """Wait until the next scheduled training time (2 AM)"""
    now = datetime.now(timezone.utc)
    target_time = datetime_time(2, 0)  # 2 AM UTC

    # Calculate next 2 AM
    next_run = now.replace(hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0)
    if now >= next_run:
        # If it's already past 2 AM today, schedule for tomorrow
        next_run = next_run.replace(day=next_run.day + 1)

    wait_seconds = (next_run - now).total_seconds()
    logger.info(f"Next training scheduled for {next_run}. Waiting {wait_seconds/3600:.1f} hours...")

    await asyncio.sleep(wait_seconds)


async def main():
    """Main function to run ML trainer on schedule"""
    logger.info("Starting ML Model Trainer (Production)")
    logger.info(f"Environment: {settings.environment}")
    logger.info("Training schedule: Daily at 2 AM UTC")

    while True:
        try:
            # Wait until next training time
            await wait_until_next_training_time()

            # Train the model
            await train_model()

        except Exception as e:
            logger.error(f"Error in ML training loop: {e}")
            logger.info("Waiting 1 hour before retry...")
            await asyncio.sleep(3600)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("ML trainer stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
