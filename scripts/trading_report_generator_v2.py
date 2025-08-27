#!/usr/bin/env python3
"""
Improved Trading Report Generator V2
Uses correct data sources per MASTER_PLAN design
Pulls from SimplePaperTraderV2 portfolio state as single source of truth
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict
from enum import Enum

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient  # noqa: E402
from src.trading.simple_paper_trader_v2 import SimplePaperTraderV2  # noqa: E402
from src.notifications.slack_notifier import SlackNotifier  # noqa: E402
from loguru import logger  # noqa: E402
import pytz  # noqa: E402


class ReportType(Enum):
    MORNING = "morning"  # 7 AM PST - Overnight activity
    MIDDAY = "midday"  # 12 PM PST - Morning session review
    EVENING = "evening"  # 7 PM PST - Full day summary


class ImprovedTradingReportGenerator:
    """Generate accurate trading reports using proper data sources."""

    def __init__(self):
        """Initialize the improved report generator."""
        self.db = SupabaseClient()
        self.slack = SlackNotifier()
        self.pst = pytz.timezone("America/Los_Angeles")
        self.utc = pytz.UTC

        # Initialize paper trader to get real portfolio state
        # This syncs from database to get actual balance and positions
        self.paper_trader = SimplePaperTraderV2(
            initial_balance=1000.0,  # Will be overridden by database sync
            max_positions=50,
        )

        # The paper trader has now synced from database
        logger.info("Initialized with real portfolio state from database")

    async def generate_morning_report(self) -> str:
        """Generate accurate morning report (7 AM PST)."""
        now = datetime.now(self.utc)
        period_start = now - timedelta(hours=12)  # Since 7 PM yesterday

        # Get real portfolio status from paper trader
        portfolio_stats = self.paper_trader.get_portfolio_stats()

        # Get period activity (overnight trades)
        overnight_activity = await self.get_period_activity(period_start, now)

        # Get current open positions (from paper trader, not database)
        open_positions = self.paper_trader.get_open_positions_summary()

        # Get market conditions with proper BTC price calculation
        market_conditions = await self.get_market_conditions()

        # Get trading opportunities from cache
        opportunities = await self.get_trading_opportunities()

        # Get strategy performance
        strategy_perf = await self.get_strategy_performance(period_start, now)

        # Format the report
        report_lines = [
            "📊 **MORNING TRADING REPORT**",
            "⏰ Period: 7 PM yesterday - 7 AM today",
            "━" * 40,
            "",
            "💰 **PORTFOLIO STATUS**",
            f"• Starting Balance: ${portfolio_stats['initial_balance']:,.2f}",
            f"• Current Balance: ${portfolio_stats['balance']:,.2f}",
            f"• Total P&L: ${portfolio_stats['total_pnl']:+,.2f} ({portfolio_stats['total_pnl_pct']:+.1f}%)",
            f"  ├─ Realized: ${portfolio_stats.get('realized_pnl', portfolio_stats['total_pnl']):+,.2f}",
            f"  └─ Unrealized: ${portfolio_stats.get('unrealized_pnl', 0):+,.2f}",
            "",
            "📈 **OVERNIGHT ACTIVITY** (12 hours)",
            f"• Trades Opened: {overnight_activity['trades_opened']}",
            f"• Trades Closed: {overnight_activity['trades_closed']}",
            f"• Win Rate: {overnight_activity['win_rate']:.0f}%",
        ]

        # Add best/worst trades if they exist
        if overnight_activity.get("best_trade"):
            bt = overnight_activity["best_trade"]
            report_lines.append(f"• Best Trade: {bt['symbol']} +${bt['pnl']:.2f}")

        if overnight_activity.get("worst_trade"):
            wt = overnight_activity["worst_trade"]
            report_lines.append(f"• Worst Trade: {wt['symbol']} ${wt['pnl']:.2f}")

        # Current positions
        report_lines.extend(
            [
                "",
                f"🎯 **CURRENT POSITIONS** ({len(open_positions)} open)",
            ]
        )

        if open_positions:
            # Show first 5 positions
            for pos in open_positions[:5]:
                symbol = pos.get("symbol", "???")
                pnl = pos.get("pnl_usd", 0)
                pnl_pct = pos.get("pnl_pct", 0)
                report_lines.append(f"• {symbol}: ${pnl:+.2f} ({pnl_pct:+.1f}%)")

        # Strategy performance
        report_lines.extend(
            [
                "",
                "🎮 **STRATEGY PERFORMANCE**",
            ]
        )

        for strategy, perf in strategy_perf.items():
            if perf["trades"] > 0:
                report_lines.append(
                    f"• {strategy}: {perf['trades']} trades, "
                    f"{perf['win_rate']:.0f}% win rate"
                )

        # Market conditions
        report_lines.extend(
            [
                "",
                "🌡️ **MARKET CONDITIONS**",
                f"• BTC: ${market_conditions['btc_price']:,.0f} ({market_conditions['btc_change']:+.1f}% overnight)",
                f"• Market Regime: {market_conditions['regime']}",
                f"• Volatility: {market_conditions['volatility']}",
            ]
        )

        # Key opportunities
        report_lines.extend(
            [
                "",
                "💡 **KEY OPPORTUNITIES**",
            ]
        )

        for strategy, count in opportunities.items():
            if count > 0:
                report_lines.append(f"• {count} symbols ready for {strategy}")

        return "\n".join(report_lines)

    async def get_period_activity(self, start: datetime, end: datetime) -> Dict:
        """Get accurate trading activity for period."""
        try:
            # Get trades from database for the period
            trades = (
                self.db.client.table("paper_trades")
                .select("*")
                .gte("created_at", start.isoformat())
                .lte("created_at", end.isoformat())
                .execute()
            )

            opened = 0
            closed = 0
            wins = 0
            losses = 0
            best_trade = None
            worst_trade = None

            if trades.data:
                # Group by trade_group_id to count properly
                trade_groups = {}
                for trade in trades.data:
                    group_id = trade.get("trade_group_id")
                    if group_id:
                        if group_id not in trade_groups:
                            trade_groups[group_id] = {"buys": [], "sells": []}
                        if trade["side"] == "BUY":
                            trade_groups[group_id]["buys"].append(trade)
                        elif trade["side"] == "SELL":
                            trade_groups[group_id]["sells"].append(trade)

                # Count opened and closed trades
                for group_id, group in trade_groups.items():
                    # If group has BUY in period, it was opened
                    if group["buys"]:
                        opened += 1

                    # If group has SELL in period, it was closed
                    for sell in group["sells"]:
                        closed += 1
                        pnl = sell.get("pnl_usd", 0) or 0

                        if pnl > 0:
                            wins += 1
                            if not best_trade or pnl > best_trade["pnl"]:
                                best_trade = {
                                    "symbol": sell["symbol"],
                                    "pnl": pnl,
                                }
                        else:
                            losses += 1
                            if not worst_trade or pnl < worst_trade["pnl"]:
                                worst_trade = {
                                    "symbol": sell["symbol"],
                                    "pnl": pnl,
                                }

            win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0

            return {
                "trades_opened": opened,
                "trades_closed": closed,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "best_trade": best_trade,
                "worst_trade": worst_trade,
            }

        except Exception as e:
            logger.error(f"Error getting period activity: {e}")
            return {
                "trades_opened": 0,
                "trades_closed": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0,
                "best_trade": None,
                "worst_trade": None,
            }

    async def get_market_conditions(self) -> Dict:
        """Get accurate market conditions with proper BTC price change."""
        try:
            # Get BTC data for last 24 hours (more reliable than 2 candles)
            now = datetime.now(self.utc)
            yesterday = now - timedelta(hours=24)

            btc_data = (
                self.db.client.table("ohlc_data")
                .select("*")
                .eq("symbol", "BTC")
                .gte("timestamp", yesterday.isoformat())
                .order("timestamp", desc=False)  # Oldest first
                .execute()
            )

            btc_price = 0
            btc_change = 0

            if btc_data.data and len(btc_data.data) > 0:
                # Current price is the most recent close
                btc_price = float(btc_data.data[-1]["close"])

                # Get price from ~12 hours ago for overnight change
                twelve_hours_ago = now - timedelta(hours=12)
                overnight_price = None

                for candle in btc_data.data:
                    candle_time = datetime.fromisoformat(
                        candle["timestamp"].replace("Z", "+00:00")
                    )
                    if candle_time >= twelve_hours_ago:
                        overnight_price = float(candle["close"])
                        break

                # If we didn't find 12-hour data, use the first available
                if overnight_price is None and len(btc_data.data) > 0:
                    overnight_price = float(btc_data.data[0]["close"])

                if overnight_price and overnight_price > 0:
                    btc_change = ((btc_price - overnight_price) / overnight_price) * 100

            # Get market regime from cache
            market_summary = (
                self.db.client.table("market_summary_cache")
                .select("*")
                .order("calculated_at", desc=True)
                .limit(1)
                .execute()
            )

            regime = "NORMAL"
            volatility = "MEDIUM"

            if market_summary.data and len(market_summary.data) > 0:
                summary = market_summary.data[0]
                regime = summary.get("condition", "NORMAL").split(" - ")[0]

                # Determine volatility based on regime
                if regime in ["PANIC", "CRASH"]:
                    volatility = "HIGH"
                elif regime in ["CAUTION"]:
                    volatility = "MEDIUM-HIGH"
                elif regime in ["EUPHORIA"]:
                    volatility = "MEDIUM"
                else:
                    volatility = "LOW"

            return {
                "btc_price": btc_price,
                "btc_change": btc_change,
                "regime": regime,
                "volatility": volatility,
            }

        except Exception as e:
            logger.error(f"Error getting market conditions: {e}")
            return {
                "btc_price": 0,
                "btc_change": 0,
                "regime": "UNKNOWN",
                "volatility": "UNKNOWN",
            }

    async def get_trading_opportunities(self) -> Dict:
        """Get current trading opportunities from strategy cache."""
        try:
            # Get fresh data from strategy status cache
            strategy_status = (
                self.db.client.table("strategy_status_cache")
                .select("*")
                .gte("readiness", 80)  # Only high readiness
                .execute()
            )

            opportunities = {"DCA": 0, "SWING": 0, "CHANNEL": 0}

            if strategy_status.data:
                # Count unique symbols per strategy
                strategy_symbols = {"DCA": set(), "SWING": set(), "CHANNEL": set()}

                for status in strategy_status.data:
                    strategy = status.get("strategy_name", "").upper()
                    symbol = status.get("symbol")

                    if strategy in strategy_symbols and symbol:
                        strategy_symbols[strategy].add(symbol)

                # Count unique symbols ready per strategy
                for strategy, symbols in strategy_symbols.items():
                    opportunities[strategy] = len(symbols)

            return opportunities

        except Exception as e:
            logger.error(f"Error getting opportunities: {e}")
            return {"DCA": 0, "SWING": 0, "CHANNEL": 0}

    async def get_strategy_performance(self, start: datetime, end: datetime) -> Dict:
        """Get strategy performance for the period."""
        try:
            # Get trades by strategy for the period
            trades = (
                self.db.client.table("paper_trades")
                .select("*")
                .eq("side", "SELL")  # Only closed trades
                .gte("filled_at", start.isoformat())
                .lte("filled_at", end.isoformat())
                .execute()
            )

            strategy_stats = {
                "DCA": {"trades": 0, "wins": 0, "losses": 0, "win_rate": 0},
                "SWING": {"trades": 0, "wins": 0, "losses": 0, "win_rate": 0},
                "CHANNEL": {"trades": 0, "wins": 0, "losses": 0, "win_rate": 0},
            }

            if trades.data:
                for trade in trades.data:
                    strategy = trade.get("strategy_name", "").upper()
                    if strategy in strategy_stats:
                        strategy_stats[strategy]["trades"] += 1

                        pnl = trade.get("pnl_usd", 0) or 0
                        if pnl > 0:
                            strategy_stats[strategy]["wins"] += 1
                        else:
                            strategy_stats[strategy]["losses"] += 1

                # Calculate win rates
                for strategy in strategy_stats:
                    total = strategy_stats[strategy]["trades"]
                    if total > 0:
                        wins = strategy_stats[strategy]["wins"]
                        strategy_stats[strategy]["win_rate"] = (wins / total) * 100

            return strategy_stats

        except Exception as e:
            logger.error(f"Error getting strategy performance: {e}")
            return {}

    async def send_to_slack(self, report: str, channel: str = "trades"):
        """Send report to Slack channel."""
        try:
            # Use the appropriate webhook based on channel
            webhook_map = {
                "trades": os.getenv("SLACK_WEBHOOK_TRADES"),
                "reports": os.getenv("SLACK_WEBHOOK_REPORTS"),
                "system-alerts": os.getenv("SLACK_WEBHOOK_SYSTEM_ALERTS"),
            }

            webhook_url = webhook_map.get(channel)
            if not webhook_url:
                logger.warning(f"No webhook configured for channel: {channel}")
                return False

            # Send via SlackNotifier
            self.slack.webhook_urls[channel] = webhook_url

            # Format as a Slack message
            message = {
                "text": report,
                "mrkdwn": True,
            }

            import requests

            response = requests.post(webhook_url, json=message)

            if response.status_code == 200:
                logger.info(f"Report sent to #{channel} channel")
                return True
            else:
                logger.error(f"Failed to send to Slack: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error sending to Slack: {e}")
            return False


async def main():
    """Generate and send the morning report."""
    generator = ImprovedTradingReportGenerator()

    # Generate morning report
    report = await generator.generate_morning_report()

    # Print to console
    print("\n" + "=" * 50)
    print(report)
    print("=" * 50 + "\n")

    # Send to Slack
    success = await generator.send_to_slack(report, "trades")

    if success:
        logger.info("✅ Morning report sent successfully")
    else:
        logger.warning("⚠️ Failed to send report to Slack")


if __name__ == "__main__":
    asyncio.run(main())
