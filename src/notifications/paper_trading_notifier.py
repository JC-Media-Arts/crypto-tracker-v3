"""
Paper Trading Slack Notifications
Sends trade notifications, daily reports, and system alerts
"""

import os
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
from loguru import logger
from .slack_notifier import SlackNotifier, NotificationType
from .slack_methods import SlackNotificationMethods


class PaperTradingNotifier:
    """Handles all notifications for paper trading system"""

    def __init__(self):
        """Initialize with channel-specific webhooks"""
        # Get webhook URLs from environment
        self.webhook_urls = {
            "trades": os.getenv("SLACK_WEBHOOK_TRADES"),
            "reports": os.getenv("SLACK_WEBHOOK_REPORTS"),
            "alerts": os.getenv("SLACK_WEBHOOK_SYSTEM_ALERTS"),
        }

        # Create notifier instance
        self.notifier = SlackNotifier()

        # Override the webhook mapping for our specific channels
        self.notifier.webhook_urls = {
            "trades": self.webhook_urls["trades"],
            "reports": self.webhook_urls["reports"],
            "alerts": self.webhook_urls["alerts"],
            "default": os.getenv("SLACK_WEBHOOK_URL"),  # Fallback
        }

        # Update webhook mapping
        self.notifier.webhook_mapping = {
            NotificationType.TRADE_OPENED: "trades",
            NotificationType.TRADE_CLOSED: "trades",
            NotificationType.DAILY_REPORT: "reports",
            NotificationType.SYSTEM_ALERT: "alerts",
            NotificationType.ERROR: "alerts",
        }

        # Check if enabled
        self.enabled = any(self.webhook_urls.values())

        if self.enabled:
            configured = [k for k, v in self.webhook_urls.items() if v]
            logger.info(f"Paper Trading Notifier initialized with channels: {configured}")
        else:
            logger.warning("Paper Trading Notifier disabled - no webhook URLs configured")

    async def notify_position_opened(
        self,
        symbol: str,
        strategy: str,
        entry_price: float,
        position_size: float,
        stop_loss: float,
        take_profit: float,
        trailing_stop_pct: float,
        market_cap_tier: str,
    ):
        """Send notification when a position is opened"""
        if not self.enabled:
            return

        # Determine emoji based on strategy
        emoji_map = {"dca": "💰", "swing": "🚀", "channel": "📊"}
        emoji = emoji_map.get(strategy.lower(), "📈")

        title = f"{emoji} Position Opened: {symbol}"
        message = f"New {strategy.upper()} position | {market_cap_tier.replace('_', ' ').title()}"

        # Calculate risk/reward
        risk = abs((entry_price - stop_loss) / entry_price) * 100
        reward = abs((take_profit - entry_price) / entry_price) * 100
        risk_reward = reward / risk if risk > 0 else 0

        details = {
            "Strategy": strategy.upper(),
            "Entry Price": f"${entry_price:.4f}",
            "Position Size": f"${position_size:.2f}",
            "Stop Loss": f"${stop_loss:.4f} (-{risk:.1f}%)",
            "Take Profit": f"${take_profit:.4f} (+{reward:.1f}%)",
            "Trailing Stop": f"{trailing_stop_pct*100:.1f}%",
            "Risk/Reward": f"{risk_reward:.2f}",
            "Market Cap": market_cap_tier.replace("_", " ").title(),
        }

        await self.notifier.send_notification(NotificationType.TRADE_OPENED, title, message, details, color="good")

    async def notify_position_closed(
        self,
        symbol: str,
        strategy: str,
        entry_price: float,
        exit_price: float,
        pnl_usd: float,
        pnl_percent: float,
        exit_reason: str,
        duration_hours: float,
        highest_price: Optional[float] = None,
    ):
        """Send notification when a position is closed with exit reason"""
        if not self.enabled:
            return

        # Determine emoji and color based on P&L
        if pnl_usd > 0:
            emoji = "✅"
            color = "good"
        else:
            emoji = "❌"
            color = "danger"

        # Format exit reason nicely
        exit_reason_display = {
            "stop_loss": "Stop Loss Hit 🛑",
            "take_profit": "Take Profit Hit 🎯",
            "trailing_stop": "Trailing Stop Hit 📉",
            "time_exit": "Timeout (3 days) ⏰",
            "manual": "Manual Close 👤",
        }.get(exit_reason, exit_reason)

        title = f"{emoji} Position Closed: {symbol}"
        message = f"{strategy.upper()} | {exit_reason_display}"

        details = {
            "Entry Price": f"${entry_price:.4f}",
            "Exit Price": f"${exit_price:.4f}",
            "P&L USD": f"${pnl_usd:+.2f}",
            "P&L %": f"{pnl_percent:+.2f}%",
            "Exit Reason": exit_reason_display,
            "Duration": f"{duration_hours:.1f} hours",
        }

        # Add highest price if trailing stop
        if exit_reason == "trailing_stop" and highest_price:
            details["Highest Price"] = f"${highest_price:.4f}"
            details["Drawdown from High"] = f"{((highest_price - exit_price) / highest_price * 100):.1f}%"

        await self.notifier.send_notification(NotificationType.TRADE_CLOSED, title, message, details, color=color)

    async def notify_system_error(self, error_type: str, error_message: str, details: Optional[Dict] = None):
        """Send notification for serious system errors"""
        if not self.enabled:
            return

        title = f"🚨 System Error: {error_type}"
        message = error_message

        error_details = {
            "Error Type": error_type,
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        if details:
            error_details.update(details)

        await self.notifier.send_notification(NotificationType.ERROR, title, message, error_details, color="danger")

    async def send_daily_report(self, stats: Dict, trades_today: List[Dict], open_positions: List[Dict]):
        """Send comprehensive daily paper trading report"""
        if not self.enabled:
            return

        # Calculate daily metrics
        today_pnl = sum(t.get("pnl_usd", 0) for t in trades_today)
        today_wins = sum(1 for t in trades_today if t.get("pnl_usd", 0) > 0)
        today_losses = sum(1 for t in trades_today if t.get("pnl_usd", 0) < 0)
        today_count = len(trades_today)

        # Determine emoji based on performance
        if today_pnl > 0:
            emoji = "📈"
            color = "good"
        elif today_pnl < 0:
            emoji = "📉"
            color = "danger"
        else:
            emoji = "📊"
            color = "#808080"

        title = f"{emoji} Daily Paper Trading Report"

        # Build message
        message_parts = []

        # Today's performance
        if today_count > 0:
            today_win_rate = (today_wins / today_count * 100) if today_count > 0 else 0
            message_parts.append(f"*Today's Performance:*")
            message_parts.append(f"• Trades: {today_count} ({today_wins}W / {today_losses}L)")
            message_parts.append(f"• P&L: ${today_pnl:+.2f}")
            message_parts.append(f"• Win Rate: {today_win_rate:.1f}%")
        else:
            message_parts.append("*No trades closed today*")

        message_parts.append("")  # Empty line

        # Overall performance
        message_parts.append(f"*Overall Performance:*")
        message_parts.append(f"• Total Value: ${stats['total_value']:.2f}")
        message_parts.append(f"• Total P&L: ${stats['total_pnl']:+.2f} ({stats['total_pnl_pct']:+.2f}%)")
        message_parts.append(
            f"• Win Rate: {stats['win_rate']:.1f}% ({stats['winning_trades']}/{stats['total_trades']})"
        )

        message = "\n".join(message_parts)

        # Build details
        details = {
            "Balance": f"${stats['balance']:.2f}",
            "Open Positions": f"{stats['positions']}/{stats['max_positions']}",
            "Positions Value": f"${stats['positions_value']:.2f}",
            "Total Trades": stats["total_trades"],
            "Total Fees": f"${stats['total_fees']:.2f}",
            "Total Slippage": f"${stats['total_slippage']:.2f}",
        }

        # Add best/worst trade of the day
        if trades_today:
            best_trade = max(trades_today, key=lambda x: x.get("pnl_usd", 0))
            worst_trade = min(trades_today, key=lambda x: x.get("pnl_usd", 0))

            if best_trade["pnl_usd"] > 0:
                details["Best Trade Today"] = f"{best_trade['symbol']} +${best_trade['pnl_usd']:.2f}"
            if worst_trade["pnl_usd"] < 0:
                details["Worst Trade Today"] = f"{worst_trade['symbol']} ${worst_trade['pnl_usd']:.2f}"

        # Add current positions summary
        if open_positions:
            position_symbols = [p["symbol"] for p in open_positions[:5]]  # Show first 5
            if len(open_positions) > 5:
                position_symbols.append(f"... +{len(open_positions)-5} more")
            details["Open Positions"] = ", ".join(position_symbols)

        await self.notifier.send_notification(NotificationType.DAILY_REPORT, title, message, details, color=color)

    async def notify_position_alert(
        self,
        symbol: str,
        alert_type: str,
        current_price: float,
        entry_price: float,
        message: str,
    ):
        """Send alerts for positions nearing exit conditions"""
        if not self.enabled:
            return

        # Determine emoji
        emoji_map = {
            "near_stop_loss": "⚠️",
            "near_take_profit": "🎯",
            "trailing_stop_active": "📉",
            "timeout_warning": "⏰",
        }
        emoji = emoji_map.get(alert_type, "📊")

        pnl_pct = ((current_price - entry_price) / entry_price) * 100

        title = f"{emoji} Position Alert: {symbol}"

        details = {
            "Alert Type": alert_type.replace("_", " ").title(),
            "Entry Price": f"${entry_price:.4f}",
            "Current Price": f"${current_price:.4f}",
            "P&L": f"{pnl_pct:+.2f}%",
        }

        # Don't send to trades channel - this is informational
        # Could create a separate alerts channel if needed
        logger.info(f"Position alert for {symbol}: {message}")
