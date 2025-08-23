"""
Slack notification system for crypto trading bot
Sends alerts, trade updates, and performance reports
"""

import asyncio
import aiohttp
import json
import os
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
from loguru import logger
from enum import Enum
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class NotificationType(Enum):
    """Types of notifications"""

    TRADE_OPENED = "trade_opened"
    TRADE_CLOSED = "trade_closed"
    SIGNAL_DETECTED = "signal_detected"
    DAILY_REPORT = "daily_report"
    SYSTEM_ALERT = "system_alert"
    REGIME_CHANGE = "regime_change"
    ERROR = "error"
    INFO = "info"
    SHADOW_PERFORMANCE = "shadow_performance"
    THRESHOLD_ADJUSTMENT = "threshold_adjustment"
    ROLLBACK_ALERT = "rollback_alert"


class SlackNotifier:
    """Handles all Slack notifications for the trading system"""

    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize Slack notifier

        Args:
            webhook_url: Slack webhook URL (can be set via env var)
        """
        # Load webhook URLs from environment
        self.webhook_urls = {
            "trades": os.getenv("SLACK_WEBHOOK_TRADES"),
            "signals": os.getenv("SLACK_WEBHOOK_SIGNALS"),
            "reports": os.getenv("SLACK_WEBHOOK_REPORTS"),
            "alerts": os.getenv("SLACK_WEBHOOK_ALERTS"),
            "default": webhook_url or os.getenv("SLACK_WEBHOOK_URL"),
        }

        # Map notification types to webhook categories
        self.webhook_mapping = {
            NotificationType.TRADE_OPENED: "trades",
            NotificationType.TRADE_CLOSED: "trades",
            NotificationType.SIGNAL_DETECTED: "signals",
            NotificationType.DAILY_REPORT: "reports",
            NotificationType.SYSTEM_ALERT: "alerts",
            NotificationType.REGIME_CHANGE: "trades",  # Market regime changes go to trades
            NotificationType.ERROR: "alerts",
            NotificationType.INFO: "signals",
            NotificationType.SHADOW_PERFORMANCE: "reports",
            NotificationType.THRESHOLD_ADJUSTMENT: "alerts",
            NotificationType.ROLLBACK_ALERT: "alerts",
        }

        # Channel mapping (for reference, actual routing is via webhooks)
        self.channels = {
            NotificationType.TRADE_OPENED: "#trades",
            NotificationType.TRADE_CLOSED: "#trades",
            NotificationType.SIGNAL_DETECTED: "#ml-signals",
            NotificationType.DAILY_REPORT: "#reports",
            NotificationType.SYSTEM_ALERT: "#system-alerts",
            NotificationType.REGIME_CHANGE: "#trades",
            NotificationType.ERROR: "#system-alerts",
            NotificationType.INFO: "#ml-signals",
        }

        # Check if any webhooks are configured
        self.enabled = any(self.webhook_urls.values())

        if self.enabled:
            configured = [k for k, v in self.webhook_urls.items() if v]
            logger.info(f"Slack notifier initialized with webhooks: {configured}")
        else:
            logger.warning("Slack notifier disabled - no webhook URLs configured")

    async def send_notification(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        details: Optional[Dict] = None,
        color: Optional[str] = None,
    ):
        """
        Send a notification to Slack

        Args:
            notification_type: Type of notification
            title: Notification title
            message: Main message text
            details: Optional details dictionary
            color: Slack attachment color (good, warning, danger, or hex)
        """
        if not self.enabled:
            logger.debug(f"Slack disabled - would send: {title}")
            return False

        # Get the appropriate webhook URL for this notification type
        webhook_category = self.webhook_mapping.get(notification_type, "default")
        webhook_url = self.webhook_urls.get(webhook_category)

        # Fallback to default webhook if specific one not configured
        if not webhook_url:
            webhook_url = self.webhook_urls.get("default")

        if not webhook_url:
            logger.warning(f"No webhook configured for {notification_type.value}")
            return False

        # Determine color based on type if not specified
        if color is None:
            color = self._get_color_for_type(notification_type)

        # Build the Slack message
        slack_message = self._build_slack_message(
            notification_type, title, message, details, color
        )

        # Send to Slack
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=slack_message,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    if response.status == 200:
                        channel = self.channels.get(notification_type, "unknown")
                        logger.debug(f"Slack notification sent to {channel}: {title}")
                        return True
                    else:
                        logger.error(
                            f"Failed to send Slack notification: {response.status}"
                        )
                        return False

        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")
            return False

    def _get_color_for_type(self, notification_type: NotificationType) -> str:
        """Get appropriate color for notification type"""
        color_map = {
            NotificationType.TRADE_OPENED: "#36a64f",  # Green
            NotificationType.TRADE_CLOSED: "#3AA3E3",  # Blue
            NotificationType.SIGNAL_DETECTED: "#FFA500",  # Orange
            NotificationType.DAILY_REPORT: "#9C27B0",  # Purple
            NotificationType.SYSTEM_ALERT: "#FF9800",  # Dark Orange
            NotificationType.REGIME_CHANGE: "#E91E63",  # Pink
            NotificationType.ERROR: "#FF0000",  # Red
            NotificationType.INFO: "#808080",  # Gray
        }
        return color_map.get(notification_type, "#808080")

    def _build_slack_message(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        details: Optional[Dict],
        color: str,
    ) -> Dict:
        """Build Slack message payload"""

        # Base message
        slack_message = {
            "text": title,
            "attachments": [
                {
                    "color": color,
                    "title": title,
                    "text": message,
                    "footer": "Crypto ML Trading Bot",
                    "ts": int(datetime.now().timestamp()),
                }
            ],
        }

        # Add fields if details provided
        if details:
            fields = []
            for key, value in details.items():
                # Format the key nicely
                formatted_key = key.replace("_", " ").title()

                # Format the value
                if isinstance(value, float):
                    if "pct" in key or "rate" in key or "confidence" in key:
                        formatted_value = f"{value:.1f}%"
                    elif "price" in key or "pnl" in key:
                        formatted_value = f"${value:.2f}"
                    else:
                        formatted_value = f"{value:.2f}"
                else:
                    formatted_value = str(value)

                fields.append(
                    {"title": formatted_key, "value": formatted_value, "short": True}
                )

            slack_message["attachments"][0]["fields"] = fields

        return slack_message
