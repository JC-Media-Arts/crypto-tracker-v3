"""
Specific notification methods for SlackNotifier
"""

from typing import Dict, Optional
from .slack_notifier import SlackNotifier, NotificationType


class SlackNotificationMethods:
    """Extension methods for specific types of notifications"""

    @staticmethod
    async def notify_trade_opened(
        notifier: SlackNotifier,
        symbol: str,
        strategy: str,
        entry_price: float,
        position_size: float,
        confidence: float,
        take_profit: float,
        stop_loss: float,
    ):
        """Notify when a new trade is opened"""

        emoji = "🚀" if strategy == "SWING" else "💰" if strategy == "DCA" else "📊"

        title = f"{emoji} Trade Opened: {symbol}"
        message = f"New {strategy} position opened with {confidence:.0f}% confidence"

        details = {
            "symbol": symbol,
            "strategy": strategy,
            "entry_price": entry_price,
            "position_size": position_size,
            "confidence_pct": confidence * 100,
            "take_profit": take_profit,
            "stop_loss": stop_loss,
            "risk_reward": abs((take_profit - entry_price) / (entry_price - stop_loss)),
        }

        await notifier.send_notification(NotificationType.TRADE_OPENED, title, message, details, "good")

    @staticmethod
    async def notify_trade_closed(
        notifier: SlackNotifier,
        symbol: str,
        strategy: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        exit_reason: str,
        duration_hours: float,
    ):
        """Notify when a trade is closed"""

        # Determine emoji based on P&L
        if pnl > 0:
            emoji = "✅"
            color = "good"
        elif pnl < 0:
            emoji = "❌"
            color = "danger"
        else:
            emoji = "➖"
            color = "warning"

        title = f"{emoji} Trade Closed: {symbol}"
        message = f"{strategy} position closed - {exit_reason}"

        details = {
            "symbol": symbol,
            "strategy": strategy,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "exit_reason": exit_reason,
            "duration_hours": duration_hours,
        }

        await notifier.send_notification(NotificationType.TRADE_CLOSED, title, message, details, color)

    @staticmethod
    async def notify_regime_change(
        notifier: SlackNotifier,
        old_regime: str,
        new_regime: str,
        btc_1h_change: float,
        btc_4h_change: Optional[float] = None,
    ):
        """Notify when market regime changes"""

        # Determine emoji and urgency
        emoji_map = {"PANIC": "🚨", "CAUTION": "⚠️", "EUPHORIA": "🚀", "NORMAL": "✅"}

        emoji = emoji_map.get(new_regime, "📊")

        # Determine color
        if new_regime == "PANIC":
            color = "danger"
        elif new_regime == "CAUTION":
            color = "warning"
        elif new_regime == "EUPHORIA":
            color = "#FFA500"  # Orange
        else:
            color = "good"

        title = f"{emoji} Market Regime Change: {old_regime} → {new_regime}"

        # Build message based on regime
        if new_regime == "PANIC":
            message = "⚠️ FLASH CRASH DETECTED - All new trades stopped!"
        elif new_regime == "CAUTION":
            message = "Market showing signs of stress - Position sizes reduced by 50%"
        elif new_regime == "EUPHORIA":
            message = "Rapid price increase detected - FOMO protection activated (30% reduction)"
        else:
            message = "Market conditions have normalized"

        # Get action description
        actions = {
            "PANIC": "No new trades",
            "CAUTION": "50% position reduction",
            "EUPHORIA": "30% position reduction",
            "NORMAL": "Normal trading",
        }

        details = {
            "btc_1h_change_pct": btc_1h_change,
            "btc_4h_change_pct": btc_4h_change if btc_4h_change else "N/A",
            "action": actions.get(new_regime, "Unknown"),
        }

        await notifier.send_notification(NotificationType.REGIME_CHANGE, title, message, details, color)

    @staticmethod
    async def send_daily_report(
        notifier: SlackNotifier,
        date: str,
        total_trades: int,
        wins: int,
        losses: int,
        total_pnl: float,
        win_rate: float,
        best_trade: Optional[Dict] = None,
        worst_trade: Optional[Dict] = None,
        strategy_breakdown: Optional[Dict] = None,
    ):
        """Send daily performance report"""

        # Determine overall emoji
        if total_pnl > 0:
            emoji = "📈"
            color = "good"
        elif total_pnl < 0:
            emoji = "📉"
            color = "danger"
        else:
            emoji = "📊"
            color = "warning"

        title = f"{emoji} Daily Report - {date}"

        # Build summary message
        message_parts = [
            f"📊 Total Trades: {total_trades}",
            f"✅ Wins: {wins} | ❌ Losses: {losses}",
            f"📈 Win Rate: {win_rate:.1f}%",
            f"💰 Total P&L: ${total_pnl:+.2f}",
        ]

        message = "\n".join(message_parts)

        # Build details
        details = {
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": win_rate,
            "total_pnl": total_pnl,
        }

        # Add best/worst trades if available
        if best_trade:
            details["best_trade"] = f"{best_trade['symbol']} +${best_trade['pnl']:.2f}"
        if worst_trade:
            details["worst_trade"] = f"{worst_trade['symbol']} -${abs(worst_trade['pnl']):.2f}"

        # Add strategy breakdown if available
        if strategy_breakdown:
            for strategy, stats in strategy_breakdown.items():
                details[f"{strategy.lower()}_pnl"] = stats.get("pnl", 0)
                details[f"{strategy.lower()}_trades"] = stats.get("trades", 0)

        await notifier.send_notification(NotificationType.DAILY_REPORT, title, message, details, color)
