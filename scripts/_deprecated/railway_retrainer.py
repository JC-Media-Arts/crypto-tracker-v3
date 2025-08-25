#!/usr/bin/env python3
"""
Railway Cron Job - Daily Model Retrainer
Runs at 2 AM PST daily via Railway's cron scheduler
"""

import sys
import os
import asyncio
from datetime import datetime
import pytz
from loguru import logger

# Add parent directory to path
sys.path.append(".")

# Configure logging for Railway
logger.add("logs/retraining.log", rotation="10 MB", level="INFO")

from src.data.supabase_client import SupabaseClient
from src.ml.simple_retrainer import SimpleRetrainer
from src.notifications.slack_notifier import SlackNotifier, NotificationType


async def railway_retrain():
    """Railway cron job entry point for model retraining"""

    # Get current time in PST
    pst = pytz.timezone("America/Los_Angeles")
    current_time = datetime.now(pst)

    logger.info("=" * 60)
    logger.info(f"RAILWAY CRON: Daily Model Retraining")
    logger.info(f"Time: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info("=" * 60)

    try:
        # Initialize components
        logger.info("Initializing components...")
        supabase = SupabaseClient()
        retrainer = SimpleRetrainer(supabase.client)
        slack = SlackNotifier()

        # Start retraining
        logger.info("Starting retraining process...")
        results = retrainer.retrain_all_strategies()

        # Prepare summary
        summary_lines = []
        models_updated = 0

        for strategy, result in results.items():
            logger.info(f"{strategy}: {result}")
            summary_lines.append(f"• {strategy}: {result}")

            if "Model updated" in result or "Initial model trained" in result:
                models_updated += 1

        # Send Slack notification
        if slack.enabled:
            title = f"🤖 Railway Cron: Model Retraining Complete"

            if models_updated > 0:
                message = f"✅ {models_updated} model(s) updated successfully!"
                color = "good"
            else:
                message = "No models updated - insufficient new data or no improvement"
                color = "warning"

            details = {
                "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S %Z"),
                "environment": "Railway Production",
                "results": "\n".join(summary_lines),
            }

            await slack.send_notification(
                NotificationType.DAILY_REPORT, title, message, details, color
            )

        logger.info("=" * 60)
        logger.info(f"Retraining complete. {models_updated} models updated.")
        logger.info("Railway cron job finished successfully.")
        logger.info("=" * 60)

        # Exit with success code for Railway
        return 0

    except Exception as e:
        logger.error(f"Railway cron job failed: {e}")

        # Send error notification
        if slack and slack.enabled:
            await slack.send_notification(
                NotificationType.ERROR,
                "❌ Railway Cron: Retraining Failed",
                f"Error during model retraining: {str(e)}",
                {"timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S %Z")},
                "danger",
            )

        # Exit with error code for Railway
        return 1


def main():
    """Main entry point for Railway cron"""
    logger.info("Railway cron job starting...")

    # Check if we're in Railway environment
    if os.getenv("RAILWAY_ENVIRONMENT"):
        logger.info(
            f"Running in Railway environment: {os.getenv('RAILWAY_ENVIRONMENT')}"
        )
    else:
        logger.info("Running locally (not in Railway)")

    # Run the async retraining
    exit_code = asyncio.run(railway_retrain())

    # Exit with appropriate code
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
