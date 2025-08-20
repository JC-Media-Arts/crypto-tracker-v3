#!/usr/bin/env python3
"""
Run the Slack system reporter continuously.
Sends reports at 9 AM and 5 PM daily, plus monitors for critical issues.
"""

import asyncio
import sys
import signal
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from scripts.slack_system_reporter import SlackSystemReporter
from loguru import logger


async def main():
    """Run the Slack reporter with proper signal handling."""
    reporter = SlackSystemReporter()

    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal, stopping reporter...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("=" * 60)
    logger.info("SLACK SYSTEM REPORTER STARTED")
    logger.info(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    logger.info("Reports scheduled for 9 AM and 5 PM daily")
    logger.info("Monitoring for critical issues every 5 minutes")
    logger.info("=" * 60)

    # Send an initial status report
    try:
        logger.info("Sending initial status report...")
        await reporter.send_morning_report()
        logger.info("Initial report sent successfully")
    except Exception as e:
        logger.error(f"Failed to send initial report: {e}")

    # Run continuous monitoring
    try:
        await reporter.run_continuous()
    except KeyboardInterrupt:
        logger.info("Reporter stopped by user")
    except Exception as e:
        logger.error(f"Reporter error: {e}")
        # Send critical alert about reporter failure
        try:
            await reporter.send_critical_alert(
                "Slack Reporter Crashed", f"The Slack reporter service has stopped unexpectedly: {str(e)[:200]}"
            )
        except:
            pass
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Slack reporter shutdown complete")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
