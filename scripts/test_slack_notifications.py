#!/usr/bin/env python3
"""
Test script for Slack notifications
Tests all notification types without a real webhook
"""

import asyncio
import os
from datetime import datetime
from loguru import logger
import sys

sys.path.append(".")

from src.notifications.slack_notifier import SlackNotifier, NotificationType
from src.notifications.slack_methods import SlackNotificationMethods
from src.config.settings import Settings

# Configure logger
logger.add("logs/slack_test.log", rotation="10 MB")


class SlackNotificationTest:
    def __init__(self):
        # Load environment variables
        from dotenv import load_dotenv

        load_dotenv()

        # Initialize notifier (will automatically load all webhook URLs from env)
        self.notifier = SlackNotifier()

        if not self.notifier.enabled:
            logger.info("Running in test mode - no actual notifications will be sent")
            logger.info("To enable real notifications, set webhook URLs in .env:")
            logger.info("  SLACK_WEBHOOK_TRADES - for trade notifications")
            logger.info("  SLACK_WEBHOOK_SIGNALS - for ML signals")
            logger.info("  SLACK_WEBHOOK_REPORTS - for reports")
            logger.info("  SLACK_WEBHOOK_ALERTS - for system alerts")
            logger.info("  SLACK_WEBHOOK_URL - default fallback")
        else:
            configured = [k for k, v in self.notifier.webhook_urls.items() if v]
            logger.info(f"Webhooks configured for: {configured}")

    async def test_trade_opened(self):
        """Test trade opened notification"""
        logger.info("\n" + "=" * 60)
        logger.info("Testing Trade Opened Notification")
        logger.info("=" * 60)

        await SlackNotificationMethods.notify_trade_opened(
            self.notifier,
            symbol="BTC",
            strategy="DCA",
            entry_price=45000.00,
            position_size=100.00,
            confidence=0.75,
            take_profit=47250.00,
            stop_loss=42750.00,
        )

        logger.info("✅ Trade opened notification sent")

    async def test_trade_closed_win(self):
        """Test trade closed notification (winning trade)"""
        logger.info("\n" + "=" * 60)
        logger.info("Testing Trade Closed Notification (WIN)")
        logger.info("=" * 60)

        await SlackNotificationMethods.notify_trade_closed(
            self.notifier,
            symbol="ETH",
            strategy="SWING",
            entry_price=3000.00,
            exit_price=3450.00,
            pnl=45.00,
            pnl_pct=15.0,
            exit_reason="Take Profit Hit",
            duration_hours=24.5,
        )

        logger.info("✅ Trade closed (win) notification sent")

    async def test_trade_closed_loss(self):
        """Test trade closed notification (losing trade)"""
        logger.info("\n" + "=" * 60)
        logger.info("Testing Trade Closed Notification (LOSS)")
        logger.info("=" * 60)

        await SlackNotificationMethods.notify_trade_closed(
            self.notifier,
            symbol="SOL",
            strategy="CHANNEL",
            entry_price=100.00,
            exit_price=95.00,
            pnl=-5.00,
            pnl_pct=-5.0,
            exit_reason="Stop Loss Hit",
            duration_hours=6.2,
        )

        logger.info("✅ Trade closed (loss) notification sent")

    async def test_signal_detected(self):
        """Test signal detected notification"""
        logger.info("\n" + "=" * 60)
        logger.info("Testing Signal Detected Notification")
        logger.info("=" * 60)

        await self.notifier.send_notification(
            NotificationType.SIGNAL_DETECTED,
            "🎯 High Confidence Signal: ADA",
            "DCA setup detected with strong ML confidence",
            {
                "symbol": "ADA",
                "strategy": "DCA",
                "confidence_pct": 82.5,
                "rsi": 28.5,
                "price_drop_pct": -6.2,
                "support_distance": 0.8,
            },
        )

        logger.info("✅ Signal detected notification sent")

    async def test_regime_change_panic(self):
        """Test regime change notification (PANIC)"""
        logger.info("\n" + "=" * 60)
        logger.info("Testing Regime Change Notification (PANIC)")
        logger.info("=" * 60)

        await SlackNotificationMethods.notify_regime_change(
            self.notifier,
            old_regime="NORMAL",
            new_regime="PANIC",
            btc_1h_change=-4.5,
            btc_4h_change=-6.2,
        )

        logger.info("✅ Regime change (panic) notification sent")

    async def test_regime_change_caution(self):
        """Test regime change notification (CAUTION)"""
        logger.info("\n" + "=" * 60)
        logger.info("Testing Regime Change Notification (CAUTION)")
        logger.info("=" * 60)

        await SlackNotificationMethods.notify_regime_change(
            self.notifier,
            old_regime="NORMAL",
            new_regime="CAUTION",
            btc_1h_change=-2.3,
            btc_4h_change=-5.1,
        )

        logger.info("✅ Regime change (caution) notification sent")

    async def test_daily_report(self):
        """Test daily report notification"""
        logger.info("\n" + "=" * 60)
        logger.info("Testing Daily Report Notification")
        logger.info("=" * 60)

        await SlackNotificationMethods.send_daily_report(
            self.notifier,
            date=datetime.now().strftime("%Y-%m-%d"),
            total_trades=15,
            wins=9,
            losses=6,
            total_pnl=125.50,
            win_rate=60.0,
            best_trade={"symbol": "BTC", "pnl": 85.00},
            worst_trade={"symbol": "DOGE", "pnl": -25.00},
            strategy_breakdown={
                "DCA": {"trades": 8, "pnl": 95.00},
                "SWING": {"trades": 4, "pnl": 45.00},
                "CHANNEL": {"trades": 3, "pnl": -14.50},
            },
        )

        logger.info("✅ Daily report notification sent")

    async def test_system_alert(self):
        """Test system alert notification"""
        logger.info("\n" + "=" * 60)
        logger.info("Testing System Alert Notification")
        logger.info("=" * 60)

        await self.notifier.send_notification(
            NotificationType.SYSTEM_ALERT,
            "⚠️ System Alert: Data Feed Issue",
            "No data received from Polygon for 10 minutes",
            {
                "last_update": "2025-01-18 11:45:00",
                "affected_symbols": 99,
                "action_taken": "Attempting reconnection",
            },
            "warning",
        )

        logger.info("✅ System alert notification sent")

    async def test_error_notification(self):
        """Test error notification"""
        logger.info("\n" + "=" * 60)
        logger.info("Testing Error Notification")
        logger.info("=" * 60)

        await self.notifier.send_notification(
            NotificationType.ERROR,
            "❌ Error: ML Model Failure",
            "Failed to load DCA model for predictions",
            {
                "error_type": "FileNotFoundError",
                "model_path": "models/dca/xgboost_multi_output.pkl",
                "timestamp": datetime.now().isoformat(),
            },
            "danger",
        )

        logger.info("✅ Error notification sent")

    async def run_all_tests(self):
        """Run all notification tests"""
        logger.info("Starting Slack Notification Tests")
        logger.info("=" * 80)

        # Test all notification types
        await self.test_trade_opened()
        await asyncio.sleep(1)  # Small delay between notifications

        await self.test_trade_closed_win()
        await asyncio.sleep(1)

        await self.test_trade_closed_loss()
        await asyncio.sleep(1)

        await self.test_signal_detected()
        await asyncio.sleep(1)

        await self.test_regime_change_panic()
        await asyncio.sleep(1)

        await self.test_regime_change_caution()
        await asyncio.sleep(1)

        await self.test_daily_report()
        await asyncio.sleep(1)

        await self.test_system_alert()
        await asyncio.sleep(1)

        await self.test_error_notification()

        logger.info("\n" + "=" * 80)
        logger.info("✅ All Slack Notification Tests Complete!")

        if self.notifier.enabled:
            logger.info("Real notifications were sent to Slack")
            logger.info("Check your Slack workspace to verify they were received")
        else:
            logger.info("Tests ran in simulation mode (no webhook configured)")
            logger.info("To send real notifications:")
            logger.info(
                "1. Create a Slack webhook at: https://api.slack.com/messaging/webhooks"
            )
            logger.info(
                "2. Add to .env: SLACK_WEBHOOK_URL=https://hooks.slack.com/services/..."
            )
            logger.info("3. Run this test again")


def main():
    test = SlackNotificationTest()
    asyncio.run(test.run_all_tests())


if __name__ == "__main__":
    main()
