#!/usr/bin/env python3
"""
Scheduled Health Report Generator
Sends system health reports to Slack at 7 AM, 12 PM, and 7 PM PST
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from loguru import logger

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.monitoring.health_monitor import HealthMonitor  # noqa: E402
from src.notifications.slack_notifier import SlackNotifier  # noqa: E402
import pytz  # noqa: E402


class ScheduledHealthReporter:
    """Sends scheduled health reports to Slack."""

    def __init__(self):
        self.monitor = HealthMonitor()
        self.slack = SlackNotifier()
        self.pst = pytz.timezone("America/Los_Angeles")

    async def send_health_report(self, report_type: str = "scheduled"):
        """Generate and send health report to Slack."""
        try:
            # Generate comprehensive health report
            report = await self.monitor.generate_health_report()

            # Format for Slack
            slack_message = self.monitor.format_slack_report(report)

            # Add timestamp header based on report type
            current_time = datetime.now(self.pst).strftime("%I:%M %p PST")
            if report_type == "morning":
                header = f"🌅 **MORNING HEALTH CHECK** - {current_time}"
            elif report_type == "midday":
                header = f"☀️ **MIDDAY HEALTH CHECK** - {current_time}"
            elif report_type == "evening":
                header = f"🌆 **EVENING HEALTH CHECK** - {current_time}"
            else:
                header = f"🔍 **SYSTEM HEALTH CHECK** - {current_time}"

            # Combine header with report
            full_message = f"{header}\n{'━' * 40}\n\n{slack_message}"

            # Send to appropriate channel based on health status
            webhook_url = None
            if report["overall_status"] == "CRITICAL":
                # Critical issues go to alerts channel
                webhook_url = os.getenv("SLACK_WEBHOOK_SYSTEM_ALERTS")
                channel = "system-alerts"
            else:
                # Normal reports go to reports channel
                webhook_url = os.getenv("SLACK_WEBHOOK_REPORTS")
                channel = "reports"

            if webhook_url:
                import requests

                message_payload = {
                    "text": full_message,
                    "mrkdwn": True,
                }

                response = requests.post(webhook_url, json=message_payload)

                if response.status_code == 200:
                    logger.info(f"✅ Health report sent to #{channel} channel")
                    return True
                else:
                    logger.error(
                        f"Failed to send health report: {response.status_code}"
                    )
                    return False
            else:
                logger.warning("No webhook configured for health reports")
                return False

        except Exception as e:
            logger.error(f"Error sending health report: {e}")
            return False

    def determine_report_type(self) -> Optional[str]:
        """Determine which type of report to send based on current time."""
        current_hour = datetime.now(self.pst).hour

        if 6 <= current_hour < 8:  # 6-8 AM window
            return "morning"
        elif 11 <= current_hour < 13:  # 11 AM - 1 PM window
            return "midday"
        elif 18 <= current_hour < 20:  # 6-8 PM window
            return "evening"
        else:
            return None  # Outside scheduled times

    async def run_scheduled(self):
        """Run on schedule - check if it's time for a report."""
        report_type = self.determine_report_type()

        if report_type:
            logger.info(f"Time for {report_type} health report")
            success = await self.send_health_report(report_type)
            return success
        else:
            logger.debug("Not a scheduled report time")
            return False

    async def run_continuous(self):
        """Run continuously, sending reports at scheduled times."""
        logger.info("Starting continuous health reporting")
        logger.info("Scheduled times: 7 AM, 12 PM, 7 PM PST")

        last_report_hour = -1

        while True:
            try:
                current_hour = datetime.now(self.pst).hour

                # Check if it's a scheduled hour and we haven't sent this hour's report yet
                if current_hour in [7, 12, 19] and current_hour != last_report_hour:
                    # Determine report type
                    if current_hour == 7:
                        report_type = "morning"
                    elif current_hour == 12:
                        report_type = "midday"
                    else:  # 19 (7 PM)
                        report_type = "evening"

                    logger.info(f"Sending {report_type} health report")
                    await self.send_health_report(report_type)
                    last_report_hour = current_hour

                # Sleep for 5 minutes before checking again
                await asyncio.sleep(300)

            except Exception as e:
                logger.error(f"Error in continuous health reporting: {e}")
                await asyncio.sleep(300)


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Send scheduled health reports")
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run continuously, sending at scheduled times",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force send a report now regardless of time",
    )
    args = parser.parse_args()

    reporter = ScheduledHealthReporter()

    if args.force:
        # Force send a report now
        logger.info("Force sending health report")
        success = await reporter.send_health_report("manual")
        sys.exit(0 if success else 1)
    elif args.continuous:
        # Run continuously
        await reporter.run_continuous()
    else:
        # Check if it's time for a scheduled report
        success = await reporter.run_scheduled()
        if not success:
            logger.info("No report scheduled at this time")
            logger.info(
                "Use --force to send immediately or --continuous to run as daemon"
            )
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
