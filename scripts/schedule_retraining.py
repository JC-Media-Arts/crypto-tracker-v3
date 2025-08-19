#!/usr/bin/env python3
"""
Schedule Daily Model Retraining
Can be run as a cron job or continuous scheduler
"""

import sys
import asyncio
import schedule
import time
from datetime import datetime
from loguru import logger

sys.path.append('.')

from scripts.run_daily_retraining import run_daily_retraining


async def scheduled_retrain():
    """Wrapper for scheduled retraining"""
    logger.info(f"Starting scheduled retraining at {datetime.now()}")
    try:
        await run_daily_retraining()
    except Exception as e:
        logger.error(f"Error in scheduled retraining: {e}")


def run_scheduler():
    """Run the scheduler continuously"""
    
    # Schedule daily retraining at 2 AM
    schedule.every().day.at("02:00").do(
        lambda: asyncio.run(scheduled_retrain())
    )
    
    logger.info("="*60)
    logger.info("MODEL RETRAINING SCHEDULER STARTED")
    logger.info("Scheduled for daily execution at 2:00 AM")
    logger.info("="*60)
    
    # Keep running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute


def run_once():
    """Run retraining once (for cron jobs)"""
    asyncio.run(run_daily_retraining())


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Schedule Model Retraining')
    parser.add_argument('--once', action='store_true', 
                       help='Run once and exit (for cron jobs)')
    parser.add_argument('--continuous', action='store_true',
                       help='Run continuously as a scheduler')
    
    args = parser.parse_args()
    
    if args.once:
        run_once()
    elif args.continuous:
        run_scheduler()
    else:
        print("Usage:")
        print("  --once       Run retraining once and exit (for cron)")
        print("  --continuous Run as continuous scheduler")
        print("")
        print("For cron job, add to crontab:")
        print("  0 2 * * * /path/to/python /path/to/schedule_retraining.py --once")
        print("")
        print("For continuous scheduler:")
        print("  python schedule_retraining.py --continuous")
