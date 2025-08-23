#!/usr/bin/env python3
"""
Enhanced Paper Trading System with Adaptive Exit Rules
- Uses 1-minute data for faster signals
- Market cap based adaptive exits
- 3-day position timeout
- Supports up to 30 positions
- Saves trades to Supabase
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger
import signal

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.strategies.manager import StrategyManager
from src.data.hybrid_fetcher import HybridDataFetcher
from src.trading.simple_paper_trader_v2 import SimplePaperTraderV2
from src.config.settings import Settings
from src.data.supabase_client import SupabaseClient
from src.notifications.paper_trading_notifier import PaperTradingNotifier


class PaperTradingSystem:
    """Enhanced paper trading system orchestrator"""

    def __init__(self):
        self.settings = Settings()

        # Initialize components
        self.data_fetcher = HybridDataFetcher()
        self.paper_trader = SimplePaperTraderV2(
            initial_balance=1000.0,
            max_positions=50,  # Increased from 30 to allow more concurrent trades
        )

        # Initialize notifier for system-level alerts
        self.notifier = None
        try:
            self.notifier = PaperTradingNotifier()
        except Exception as e:
            logger.warning(f"Could not initialize Slack notifier: {e}")

        # Strategy config for simplified mode
        strategy_config = {
            "ml_enabled": False,
            "shadow_enabled": False,
            "base_position_usd": 50.0,  # $50 per position
            "max_open_positions": 30,  # Increased to match paper trader
            "dca_drop_threshold": -1.0,  # Aggressive for testing
            "swing_breakout_threshold": 0.3,
            "channel_position_threshold": 0.35,
        }

        self.strategy_manager = StrategyManager(strategy_config, self.settings)

        # Trading parameters
        self.min_confidence = 0.0  # Accept all signals in test mode
        self.scan_interval = 60  # Scan every minute
        self.position_size = 50.0  # $50 per trade
        self.use_adaptive_exits = True  # Use market-cap based exit rules
        self.max_position_duration_hours = 72  # 3 days timeout (changed from 4 hours)

        # Track active positions
        self.active_positions = self.paper_trader.positions

        # Shutdown flag
        self.shutdown = False

        logger.info("=" * 80)
        logger.info("📊 ENHANCED PAPER TRADING SYSTEM INITIALIZED")
        logger.info(f"   Balance: ${self.paper_trader.balance:.2f}")
        logger.info(f"   Position Size: ${self.position_size}")
        logger.info(f"   Max Positions: {self.paper_trader.max_positions}")
        logger.info(f"   Exit Rules: Adaptive by Market Cap")
        logger.info(f"   Timeout: {self.max_position_duration_hours} hours (3 days)")
        logger.info(f"   Data: 1-minute candles for faster signals")
        logger.info("=" * 80)

    def get_symbols(self) -> List[str]:
        """Get symbols to monitor"""
        # Full list of 90 symbols we're tracking
        return [
            # Major coins
            "BTC",
            "ETH",
            "SOL",
            "BNB",
            "XRP",
            "ADA",
            "AVAX",
            "DOGE",
            "DOT",
            "MATIC",
            "LINK",
            "TON",
            "SHIB",
            "TRX",
            "UNI",
            "ATOM",
            "BCH",
            "APT",
            "NEAR",
            "ICP",
            # DeFi/Layer 2
            "ARB",
            "OP",
            "AAVE",
            "CRV",
            "MKR",
            "LDO",
            "SUSHI",
            "COMP",
            "SNX",
            "BAL",
            "INJ",
            "SEI",
            "PENDLE",
            "BLUR",
            "ENS",
            "GRT",
            "RENDER",
            "FET",
            "RPL",
            "SAND",
            # Trending/Memecoins
            "PEPE",
            "WIF",
            "BONK",
            "FLOKI",
            "MEME",
            "POPCAT",
            "MEW",
            "TURBO",
            "NEIRO",
            "PNUT",
            "GOAT",
            "ACT",
            "TRUMP",
            "FARTCOIN",
            "MOG",
            "PONKE",
            "TREMP",
            "BRETT",
            "GIGA",
            "HIPPO",
            # Mid-caps
            "FIL",
            "RUNE",
            "IMX",
            "FLOW",
            "MANA",
            "AXS",
            "CHZ",
            "GALA",
            "LRC",
            "OCEAN",
            "QNT",
            "ALGO",
            "XLM",
            "XMR",
            "ZEC",
            "DASH",
            "HBAR",
            "VET",
            "THETA",
            "EOS",
            "KSM",
            "STX",
            "KAS",
            "TIA",
            "JTO",
            "JUP",
            "PYTH",
            "DYM",
            "STRK",
            "ALT",
            "PORTAL",
            "BEAM",
            "MASK",
            "API3",
            "ANKR",
            "CTSI",
            "YFI",
            "AUDIO",
            "ENJ",
        ]

    async def fetch_market_data(self) -> Dict:
        """Fetch latest market data for all symbols"""
        market_data = {}

        try:
            # Fetch 1-minute bars for faster signal detection
            hours = 4  # Get last 4 hours of 1-minute data (240 bars)

            for symbol in self.get_symbols():
                try:
                    result = await self.data_fetcher.get_recent_data(
                        symbol=symbol,
                        hours=hours,
                        timeframe="1m",  # Changed from 15m to 1m
                    )

                    # Handle both DataFrame and list results
                    if hasattr(result, "empty"):
                        if not result.empty and len(result) >= 20:
                            market_data[symbol] = result
                    elif isinstance(result, list) and len(result) >= 20:
                        market_data[symbol] = result

                except Exception as e:
                    logger.debug(f"Failed to fetch data for {symbol}: {e}")
                    continue

            logger.info(f"Fetched data for {len(market_data)} symbols")
            return market_data

        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
            return {}

    async def get_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get current prices for specific symbols"""
        prices = {}

        for symbol in symbols:
            try:
                result = await self.data_fetcher.get_recent_data(
                    symbol=symbol,
                    hours=1,
                    timeframe="1m",  # Get last hour for current price
                )

                if hasattr(result, "empty"):
                    if not result.empty:
                        prices[symbol] = float(result.iloc[-1]["close"])
                elif isinstance(result, list) and result:
                    prices[symbol] = float(result[-1]["close"])

            except Exception as e:
                logger.debug(f"Failed to get price for {symbol}: {e}")

        return prices

    async def execute_signal(self, signal, market_data: Dict) -> None:
        """Execute a trading signal"""
        try:
            # Skip if we already have a position
            if signal.symbol in self.paper_trader.positions:
                logger.debug(f"Already have position in {signal.symbol}")
                return

            # Get current price
            current_price = None
            if signal.symbol in market_data:
                data = market_data[signal.symbol]
                if hasattr(data, "iloc"):
                    current_price = float(data.iloc[-1]["close"])
                elif isinstance(data, list):
                    current_price = float(data[-1]["close"])

            if not current_price:
                logger.warning(f"No price data for {signal.symbol}")
                return

            # Open position with adaptive exits
            result = await self.paper_trader.open_position(
                symbol=signal.symbol,
                usd_amount=self.position_size,
                market_price=current_price,
                strategy=signal.strategy_type.value,
                use_adaptive=self.use_adaptive_exits,  # Use adaptive exits
            )

            # Handle both old format (None/bool) and new format (dict)
            if result and isinstance(result, dict) and result.get("success"):
                logger.info(
                    f"✅ Opened {signal.strategy_type.value} position for {signal.symbol}"
                )
            elif result is True:  # Old format compatibility
                logger.info(
                    f"✅ Opened {signal.strategy_type.value} position for {signal.symbol}"
                )
            else:
                error_msg = (
                    result.get("error")
                    if isinstance(result, dict) and result
                    else "Position opening failed"
                )
                logger.warning(
                    f"Failed to open position for {signal.symbol}: {error_msg}"
                )

        except Exception as e:
            logger.error(f"Error executing signal for {signal.symbol}: {e}")

    async def check_and_close_positions(self, market_data: Dict) -> None:
        """Check and close positions based on exit conditions"""
        if not self.paper_trader.positions:
            return

        # Get current prices for all positions
        symbols = list(self.paper_trader.positions.keys())
        prices = await self.get_current_prices(symbols)

        # Check all exit conditions including trailing stops
        closed_trades = await self.paper_trader.check_and_close_positions(
            prices, max_hold_hours=self.max_position_duration_hours  # 72 hours
        )

        # Log closed trades
        for trade in closed_trades:
            emoji = "✅" if trade.pnl_usd > 0 else "❌"
            logger.info(
                f"{emoji} Closed {trade.symbol}: ${trade.pnl_usd:.2f} ({trade.pnl_percent:+.2f}%) - {trade.exit_reason}"
            )

    async def run_trading_loop(self) -> None:
        """Main trading loop"""
        logger.info("🚀 Starting enhanced paper trading loop...")

        while not self.shutdown:
            try:
                # Fetch market data
                market_data = await self.fetch_market_data()
                if not market_data:
                    logger.warning("No market data available, skipping scan")
                    await asyncio.sleep(self.scan_interval)
                    continue

                # Scan for opportunities
                signals = await self.strategy_manager.scan_for_opportunities(
                    market_data
                )

                # Get portfolio stats
                stats = self.paper_trader.get_portfolio_stats()

                logger.info(
                    f"Scan complete: {len(signals)} signals, {stats['positions']}/{stats['max_positions']} positions"
                )
                logger.info(
                    f"Portfolio: ${stats['total_value']:.2f} ({stats['total_pnl_pct']:+.2f}%)"
                )

                # Execute signals (only if we have room for more positions)
                if stats["positions"] < stats["max_positions"]:
                    for signal in signals:
                        if signal.symbol not in self.paper_trader.positions:
                            await self.execute_signal(signal, market_data)

                # Check and close positions
                await self.check_and_close_positions(market_data)

                # Display current positions
                if self.paper_trader.positions:
                    logger.info("Current positions:")
                    prices = await self.get_current_prices(
                        list(self.paper_trader.positions.keys())
                    )

                    for symbol, position in self.paper_trader.positions.items():
                        current_price = prices.get(symbol, position.entry_price)
                        pnl_pct = (
                            (current_price - position.entry_price)
                            / position.entry_price
                        ) * 100
                        emoji = "🟢" if pnl_pct > 0 else "🔴"

                        # Show trailing stop info
                        trailing_info = ""
                        if position.highest_price > position.entry_price:
                            trailing_stop_price = position.highest_price * (
                                1 - position.trailing_stop_pct
                            )
                            trailing_info = f" | Trail: ${trailing_stop_price:.4f}"

                        logger.info(
                            f"   {emoji} {symbol}: Entry ${position.entry_price:.4f} → ${current_price:.4f} ({pnl_pct:+.2f}%){trailing_info}"
                        )

                # Summary every 5 trades
                if (
                    self.paper_trader.total_trades > 0
                    and self.paper_trader.total_trades % 5 == 0
                ):
                    await self.print_summary()

            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                import traceback

                error_traceback = traceback.format_exc()
                logger.error(f"Traceback: {error_traceback}")

                # Send error notification to Slack
                if self.notifier:
                    try:
                        await self.notifier.notify_system_error(
                            error_type="Trading Loop Error",
                            error_message=str(e),
                            details={
                                "Component": "Paper Trading Loop",
                                "Error": str(e)[:200],
                            },  # Truncate long errors
                        )
                    except:
                        pass  # Don't let notification errors crash the loop

            # Wait for next scan
            await asyncio.sleep(self.scan_interval)

    async def print_summary(self) -> None:
        """Print trading summary"""
        stats = self.paper_trader.get_portfolio_stats()

        logger.info("=" * 80)
        logger.info("📊 TRADING SUMMARY")
        logger.info(f"   Balance: ${stats['balance']:.2f}")
        logger.info(f"   Positions: {stats['positions']}/{stats['max_positions']}")
        logger.info(f"   Total Value: ${stats['total_value']:.2f}")
        logger.info(
            f"   P&L: ${stats['total_pnl']:.2f} ({stats['total_pnl_pct']:+.2f}%)"
        )
        logger.info(f"   Total Trades: {stats['total_trades']}")
        logger.info(f"   Win Rate: {stats['win_rate']:.1f}%")
        logger.info(f"   Fees Paid: ${stats['total_fees']:.2f}")
        logger.info(f"   Slippage: ${stats['total_slippage']:.2f}")
        logger.info("=" * 80)

        # Send daily report every 24 hours
        if hasattr(self, "last_daily_report"):
            if (
                datetime.now() - self.last_daily_report
            ).total_seconds() > 86400:  # 24 hours
                await self.send_daily_report()
        else:
            self.last_daily_report = datetime.now()

    async def send_daily_report(self) -> None:
        """Send daily report to Slack"""
        if not self.notifier:
            return

        try:
            stats = self.paper_trader.get_portfolio_stats()
            trades_today = self.paper_trader.get_trades_today()
            open_positions = self.paper_trader.get_open_positions_summary()

            await self.notifier.send_daily_report(
                stats=stats, trades_today=trades_today, open_positions=open_positions
            )

            self.last_daily_report = datetime.now()
            logger.info("Daily report sent to Slack")
        except Exception as e:
            logger.error(f"Failed to send daily report: {e}")

    async def shutdown_handler(self) -> None:
        """Handle graceful shutdown"""
        logger.info("\n🛑 Shutdown signal received...")
        self.shutdown = True

        # Final summary
        stats = self.paper_trader.get_portfolio_stats()

        logger.info("=" * 80)
        logger.info("📊 FINAL TRADING STATISTICS:")
        logger.info(f"   Initial Balance: ${self.paper_trader.initial_balance:.2f}")
        logger.info(f"   Final Balance: ${stats['balance']:.2f}")
        logger.info(
            f"   Total P&L: ${stats['total_pnl']:.2f} ({stats['total_pnl_pct']:+.2f}%)"
        )
        logger.info(f"   Total Trades: {stats['total_trades']}")
        logger.info(f"   Win Rate: {stats['win_rate']:.1f}%")
        logger.info(f"   Total Fees Paid: ${stats['total_fees']:.2f}")
        logger.info(f"   Total Slippage Cost: ${stats['total_slippage']:.2f}")
        logger.info("=" * 80)


async def main():
    """Main entry point"""
    system = PaperTradingSystem()

    # Setup signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig, lambda: asyncio.create_task(system.shutdown_handler())
        )

    # Run trading loop
    try:
        await system.run_trading_loop()
    except KeyboardInterrupt:
        await system.shutdown_handler()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback

        error_traceback = traceback.format_exc()
        logger.error(f"Traceback: {error_traceback}")

        # Send fatal error notification
        if system.notifier:
            try:
                await system.notifier.notify_system_error(
                    error_type="Fatal System Error",
                    error_message="Paper trading system crashed",
                    details={"Error": str(e)[:500], "Component": "Main Process"},
                )
            except:
                pass


if __name__ == "__main__":
    asyncio.run(main())
