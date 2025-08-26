#!/usr/bin/env python3
"""
Enhanced trading reporter that sends comprehensive reports 3x daily.
Integrates with existing Slack Reporter service or can run standalone.
"""

import asyncio
import sys
import signal
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pytz
import schedule

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from scripts.trading_report_generator import (  # noqa: E402
    TradingReportGenerator,
    ReportType,
)
from loguru import logger  # noqa: E402


class TradingReporter:
    """Manages scheduled trading reports."""

    def __init__(self):
        """Initialize the reporter."""
        self.generator = TradingReportGenerator()
        self.pst = pytz.timezone("America/Los_Angeles")
        self.running = True

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info("Received shutdown signal, stopping reporter...")
        self.running = False

    async def send_morning_report(self):
        """Send morning report (7 AM PST)."""
        try:
            logger.info("Generating morning trading report...")
            report = await self.generator.generate_report(ReportType.MORNING)
            await self.generator.send_report(report)
            logger.info("Morning report sent successfully to #trades")
        except Exception as e:
            logger.error(f"Failed to send morning report: {e}")

    async def send_midday_report(self):
        """Send midday report (12 PM PST)."""
        try:
            logger.info("Generating midday trading report...")
            report = await self.generator.generate_report(ReportType.MIDDAY)
            await self.generator.send_report(report)
            logger.info("Midday report sent successfully to #trades")
        except Exception as e:
            logger.error(f"Failed to send midday report: {e}")

    async def send_evening_report(self):
        """Send evening report (7 PM PST)."""
        try:
            logger.info("Generating evening trading report...")
            report = await self.generator.generate_report(ReportType.EVENING)
            await self.generator.send_report(report)
            logger.info("Evening report sent successfully to #trades")
        except Exception as e:
            logger.error(f"Failed to send evening report: {e}")

    async def send_weekly_report(self):
        """Send weekly report (Sunday 7 PM PST)."""
        try:
            logger.info("Generating weekly trading report...")
            report = await self.generator.generate_report(ReportType.WEEKLY)
            await self.generator.send_report(report)
            logger.info("Weekly report sent successfully to #trades")
        except Exception as e:
            logger.error(f"Failed to send weekly report: {e}")

    def schedule_reports(self):
        """Schedule all reports."""
        # Daily reports at PST times (converted to system time)
        schedule.every().day.at("07:00").do(
            lambda: asyncio.create_task(self.send_morning_report())
        )
        schedule.every().day.at("12:00").do(
            lambda: asyncio.create_task(self.send_midday_report())
        )
        schedule.every().day.at("19:00").do(
            lambda: asyncio.create_task(self.send_evening_report())
        )

        # Weekly report on Sunday
        schedule.every().sunday.at("19:00").do(
            lambda: asyncio.create_task(self.send_weekly_report())
        )

        logger.info("Reports scheduled for 7 AM, 12 PM, and 7 PM PST daily")
        logger.info("Weekly report scheduled for Sunday 7 PM PST")

    def get_next_report_time(self):
        """Get the time until the next scheduled report."""
        now = datetime.now(self.pst)

        # Define report times in PST
        report_times = [
            now.replace(hour=7, minute=0, second=0),  # 7 AM
            now.replace(hour=12, minute=0, second=0),  # 12 PM
            now.replace(hour=19, minute=0, second=0),  # 7 PM
        ]

        # Find next report time
        for report_time in report_times:
            if report_time > now:
                return report_time - now

        # If all times have passed today, next is tomorrow 7 AM
        tomorrow_7am = (now + timedelta(days=1)).replace(hour=7, minute=0, second=0)
        return tomorrow_7am - now

    async def run_continuous(self):
        """Run the reporter continuously."""
        self.schedule_reports()

        # Send initial report
        logger.info("Sending initial status report...")
        try:
            await self.send_morning_report()
        except Exception as e:
            logger.error(f"Failed to send initial report: {e}")

        # Main loop
        while self.running:
            try:
                schedule.run_pending()

                # Log next report time every hour
                if datetime.now().minute == 0:
                    time_to_next = self.get_next_report_time()
                    logger.info(f"Next report in {time_to_next}")

                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(60)

    async def run_once(self, report_type: str):
        """Run a single report by type."""
        report_map = {
            "morning": ReportType.MORNING,
            "midday": ReportType.MIDDAY,
            "evening": ReportType.EVENING,
            "weekly": ReportType.WEEKLY,
        }

        if report_type not in report_map:
            logger.error(f"Unknown report type: {report_type}")
            logger.info(f"Valid types: {list(report_map.keys())}")
            return

        try:
            logger.info(f"Generating {report_type} report...")
            report = await self.generator.generate_report(report_map[report_type])
            await self.generator.send_report(report)
            logger.info(f"{report_type.capitalize()} report sent successfully")
        except Exception as e:
            logger.error(f"Failed to send {report_type} report: {e}")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Trading Report Generator")
    parser.add_argument(
        "--type",
        choices=["morning", "midday", "evening", "weekly"],
        help="Generate a specific report type",
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run continuously with scheduled reports",
    )

    args = parser.parse_args()

    reporter = TradingReporter()

    logger.info("=" * 60)
    logger.info("TRADING REPORTER STARTED")
    logger.info(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

    if args.type:
        # Run single report
        await reporter.run_once(args.type)
    elif args.continuous:
        # Run continuously
        logger.info("Running in continuous mode")
        await reporter.run_continuous()
    else:
        # Default: run single morning report
        logger.info(
            "Running single morning report (use --continuous for scheduled mode)"
        )
        await reporter.run_once("morning")

    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Trading reporter shutdown complete")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
