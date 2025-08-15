"""
Slack notification module for alerts and reports.
Handles all Slack communications including trades, alerts, and daily summaries.
"""

import asyncio
from datetime import datetime
from typing import Dict, Optional
from loguru import logger
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import aiohttp

from src.config import Settings


class SlackNotifier:
    """Handles Slack notifications and alerts."""

    # Channel configuration from master plan
    CHANNELS = {
        "ml-signals": "Real-time predictions and trades",
        "daily-reports": "7 AM and 7 PM summaries",
        "system-alerts": "Critical issues only",
    }

    # Notification templates
    TEMPLATES = {
        "trade_opened": """💰 *Trade Opened*
• Coin: `{symbol}`
• Entry: ${price:.2f}
• Confidence: {confidence:.0%}
• Stop Loss: ${stop_loss:.2f} (-5%)
• Take Profit: ${take_profit:.2f} (+10%)""",
        "trade_closed": """{emoji} *Trade Closed*
• Coin: `{symbol}`
• P&L: ${pnl:.2f} ({pnl_pct:+.1f}%)
• Reason: {exit_reason}
• Duration: {hours}h {minutes}m""",
        "daily_summary": """📊 *Daily Summary - {date}*
• Total Trades: {trades_count}
• Wins: {wins} | Losses: {losses}
• Net P&L: ${net_pnl:.2f}
• Win Rate: {win_rate:.1%}
• ML Accuracy: {ml_accuracy:.1%}""",
        "system_alert": """🚨 *System Alert*
• Type: {alert_type}
• Message: {message}
• Time: {timestamp}""",
        "big_win": """🎉 @channel *Big WIN!*
• Coin: {symbol}
• Profit: +${profit:.2f}
• Return: +{return_pct:.1%}""",
        "big_loss": """⚠️ @channel *Loss Alert*
• Coin: {symbol}
• Loss: -${loss:.2f}
• Return: -{return_pct:.1%}""",
    }

    def __init__(self, settings: Settings):
        """Initialize Slack notifier."""
        self.settings = settings
        self.webhook_url = settings.slack_webhook_url
        self.bot_token = settings.slack_bot_token
        self.client: Optional[WebClient] = None
        self.running = False

    async def initialize(self):
        """Initialize Slack client."""
        logger.info("Initializing Slack notifier...")

        try:
            # Initialize Slack Web API client
            self.client = WebClient(token=self.bot_token)

            # Test connection
            response = self.client.auth_test()
            logger.info(f"Connected to Slack as {response['user']}")

            logger.success("Slack notifier initialized")

        except SlackApiError as e:
            logger.error(f"Failed to initialize Slack client: {e}")
            # Continue without Slack if it fails
        except Exception as e:
            logger.error(f"Unexpected error initializing Slack: {e}")

    async def send_message(self, message: str, channel: str = "system-alerts"):
        """Send a message to Slack channel."""
        try:
            # Map channel name to actual channel ID if needed
            channel_id = f"#{channel}"

            if self.client:
                response = self.client.chat_postMessage(
                    channel=channel_id, text=message, mrkdwn=True
                )
                logger.debug(f"Sent message to {channel}")
            else:
                # Fallback to webhook if client not available
                await self._send_via_webhook(message)

        except SlackApiError as e:
            logger.error(f"Failed to send Slack message: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending message: {e}")

    async def _send_via_webhook(self, message: str):
        """Send message via webhook as fallback."""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {"text": message}
                async with session.post(self.webhook_url, json=payload) as response:
                    if response.status != 200:
                        logger.error(f"Webhook failed: {response.status}")
        except Exception as e:
            logger.error(f"Failed to send via webhook: {e}")

    async def notify_trade_opened(self, trade: Dict):
        """Notify when a trade is opened."""
        message = self.TEMPLATES["trade_opened"].format(
            symbol=trade["symbol"],
            price=trade["entry_price"],
            confidence=trade["ml_confidence"],
            stop_loss=trade["stop_loss"],
            take_profit=trade["take_profit"],
        )

        await self.send_message(message, "ml-signals")

    async def notify_trade_closed(self, trade: Dict):
        """Notify when a trade is closed."""
        # Calculate duration
        entry_time = datetime.fromisoformat(trade["entry_time"].replace("Z", "+00:00"))
        exit_time = datetime.fromisoformat(trade["exit_time"].replace("Z", "+00:00"))
        duration = exit_time - entry_time
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)

        # Choose emoji based on P&L
        emoji = "✅" if trade["pnl"] > 0 else "❌"

        message = self.TEMPLATES["trade_closed"].format(
            emoji=emoji,
            symbol=trade["symbol"],
            pnl=trade["pnl"],
            pnl_pct=(trade["exit_price"] - trade["entry_price"])
            / trade["entry_price"]
            * 100,
            exit_reason=trade["exit_reason"],
            hours=hours,
            minutes=minutes,
        )

        await self.send_message(message, "ml-signals")

        # Check for big wins/losses
        if trade["pnl"] > 50:  # Big win > $50
            await self.notify_big_win(trade)
        elif trade["pnl"] < -25:  # Big loss > $25
            await self.notify_big_loss(trade)

    async def notify_big_win(self, trade: Dict):
        """Notify channel about big win."""
        return_pct = (trade["exit_price"] - trade["entry_price"]) / trade["entry_price"]

        message = self.TEMPLATES["big_win"].format(
            symbol=trade["symbol"], profit=trade["pnl"], return_pct=return_pct
        )

        await self.send_message(message, "ml-signals")

    async def notify_big_loss(self, trade: Dict):
        """Notify channel about big loss."""
        return_pct = abs(
            (trade["exit_price"] - trade["entry_price"]) / trade["entry_price"]
        )

        message = self.TEMPLATES["big_loss"].format(
            symbol=trade["symbol"], loss=abs(trade["pnl"]), return_pct=return_pct
        )

        await self.send_message(message, "ml-signals")

    async def send_daily_summary(self, summary: Dict):
        """Send daily performance summary."""
        message = self.TEMPLATES["daily_summary"].format(
            date=summary["date"],
            trades_count=summary["trades_count"],
            wins=summary["wins"],
            losses=summary["losses"],
            net_pnl=summary["net_pnl"],
            win_rate=summary["wins"] / max(summary["trades_count"], 1),
            ml_accuracy=summary["ml_accuracy"],
        )

        await self.send_message(message, "daily-reports")

    async def send_system_alert(self, alert_type: str, message: str):
        """Send system alert."""
        alert_message = self.TEMPLATES["system_alert"].format(
            alert_type=alert_type,
            message=message,
            timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        )

        await self.send_message(alert_message, "system-alerts")

    async def start_scheduled_reports(self):
        """Start scheduled report tasks."""
        self.running = True

        # Schedule morning and evening reports
        asyncio.create_task(self._schedule_reports())

    async def _schedule_reports(self):
        """Schedule daily reports."""
        while self.running:
            try:
                now = datetime.utcnow()

                # Check if it's time for morning report (7 AM)
                if now.hour == 14 and now.minute == 0:  # 14:00 UTC = 7 AM LA time
                    await self._send_morning_report()
                    await asyncio.sleep(60)  # Wait a minute to avoid duplicate

                # Check if it's time for evening report (7 PM)
                elif now.hour == 2 and now.minute == 0:  # 02:00 UTC = 7 PM LA time
                    await self._send_evening_report()
                    await asyncio.sleep(60)

                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                logger.error(f"Error in scheduled reports: {e}")
                await asyncio.sleep(60)

    async def _send_morning_report(self):
        """Send morning report."""
        # TODO: Implement morning report logic
        message = "☀️ *Good Morning!*\nCrypto Tracker v3 is operational.\nLast 12 hours summary coming soon..."
        await self.send_message(message, "daily-reports")

    async def _send_evening_report(self):
        """Send evening report."""
        # TODO: Implement evening report logic
        message = "🌙 *Good Evening!*\nDaily trading summary coming soon..."
        await self.send_message(message, "daily-reports")

    async def shutdown(self):
        """Shutdown Slack notifier."""
        self.running = False
        logger.info("Slack notifier shut down")
