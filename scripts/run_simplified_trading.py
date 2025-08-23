#!/usr/bin/env python3
"""
Simplified trading system for Phase 1 Recovery
Direct signal → Hummingbot pipeline without ML
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.strategies.manager import StrategyManager
from src.data.hybrid_fetcher import HybridDataFetcher
from hummingbot_api_client import HummingbotAPIClient  # Use official client
from src.notifications.slack_notifier import SlackNotifier
from src.config.settings import get_settings


class SimplifiedTradingSystem:
    """Simplified trading system that connects signals to Hummingbot"""

    def __init__(self):
        """Initialize the simplified trading system"""

        # Load settings
        self.settings = get_settings()

        # Load recovery config
        config_path = Path("config/recovery_phase.json")
        if config_path.exists():
            with open(config_path, "r") as f:
                self.recovery_config = json.load(f)
                logger.info(
                    f"Loaded recovery config: Phase {self.recovery_config.get('phase')}"
                )
        else:
            self.recovery_config = {}

        # Build config for strategy manager
        self.config = {
            "ml_enabled": False,
            "shadow_testing_enabled": False,
            "regime_detection_enabled": False,  # Keep it simple
            "total_capital": 1000,
            "dca_allocation": 0.4,
            "swing_allocation": 0.3,
            "channel_allocation": 0.3,
            "base_position_usd": 50,
            # Use recovery thresholds
            "dca_config": self.recovery_config.get(
                "dca_config",
                {"drop_threshold": -3.5, "min_confidence": 0.0, "use_ml": False},
            ),
            "swing_config": self.recovery_config.get(
                "swing_config",
                {"breakout_threshold": 2.1, "min_confidence": 0.0, "use_ml": False},
            ),
            "channel_config": self.recovery_config.get(
                "channel_config",
                {"min_channel_strength": 0.42, "min_confidence": 0.0, "use_ml": False},
            ),
            # Trading rules from recovery config
            "trading_rules": self.recovery_config.get(
                "trading_rules",
                {
                    "max_open_positions": 10,
                    "position_size": 50,
                    "stop_loss": -3.0,
                    "take_profit": 5.0,
                    "time_exit_hours": 12,
                },
            ),
        }

        # Initialize components
        self.strategy_manager = StrategyManager(self.config)
        self.data_fetcher = HybridDataFetcher()

        # Initialize Hummingbot client (if available)
        try:
            # Use official Hummingbot API client
            self.hummingbot = HummingbotAPIClient(
                base_url=f"http://{os.getenv('HUMMINGBOT_HOST', 'localhost')}:{os.getenv('HUMMINGBOT_PORT', '8000')}",
                username=os.getenv("HUMMINGBOT_USERNAME", "admin"),
                password=os.getenv("HUMMINGBOT_PASSWORD", "admin"),
            )
            # Connection will be tested in main()
            self.hummingbot_available = (
                False  # Will be set to True after successful connection
            )
            logger.info("✅ Hummingbot API client created (awaiting connection test)")
        except Exception as e:
            logger.warning(f"⚠️ Hummingbot API not available: {e}")
            logger.warning("Running in signal-only mode (no execution)")
            self.hummingbot = None
            self.hummingbot_available = False

        # Initialize Slack (optional)
        try:
            self.slack = SlackNotifier(self.settings)
            logger.info("✅ Slack notifications enabled")
        except:
            self.slack = None
            logger.info("ℹ️ Slack notifications disabled")

        # Track active positions
        self.active_positions = {}
        self.scan_interval = 60  # Scan every minute
        self.symbols = self.get_symbols()

        logger.info(
            f"Simplified trading system initialized for {len(self.symbols)} symbols"
        )

    async def _test_hummingbot_connection(self):
        """Test Hummingbot API connection"""
        try:
            # Initialize the client first
            await self.hummingbot.init()
            logger.info("✅ Hummingbot API client initialized")

            # Check if accounts property is available
            if hasattr(self.hummingbot, "accounts"):
                try:
                    accounts = self.hummingbot.accounts
                    # accounts might be a router object, not a list
                    logger.info(f"✅ Hummingbot API connected - accounts available")
                except Exception as e:
                    logger.info(f"✅ Hummingbot API connected (accounts check: {e})")
            else:
                logger.info("✅ Hummingbot API connected")

            self.hummingbot_available = True
        except Exception as e:
            logger.error(f"❌ Hummingbot API connection failed: {e}")
            self.hummingbot_available = False

    def get_symbols(self) -> List[str]:
        """Get symbols to monitor"""
        # Full list of 90 symbols we're tracking
        return [
            # Major coins
            "BTC",
            "ETH",
            "SOL",
            "XRP",
            "ADA",
            "AVAX",
            "DOGE",
            "DOT",
            "LINK",
            "MATIC",
            "UNI",
            "LTC",
            "BCH",
            "ATOM",
            "ETC",
            "XLM",
            "FIL",
            "ICP",
            "NEAR",
            "VET",
            "ALGO",
            "FTM",
            "HBAR",
            "MANA",
            "SAND",
            "AXS",
            "THETA",
            "EGLD",
            "XTZ",
            "EOS",
            "AAVE",
            "MKR",
            "CRV",
            "LDO",
            "SNX",
            "COMP",
            "GRT",
            "ENJ",
            "CHZ",
            "BAT",
            "DASH",
            "ZEC",
            "KSM",
            "RUNE",
            "SUSHI",
            "YFI",
            "UMA",
            "ZRX",
            "QTUM",
            "OMG",
            "WAVES",
            "BAL",
            "KNC",
            "REN",
            "ANKR",
            "STORJ",
            "OCEAN",
            "BAND",
            "NMR",
            "SRM",
            # Newer/Trending coins
            "APT",
            "ARB",
            "OP",
            "INJ",
            "TIA",
            "SEI",
            "SUI",
            "BLUR",
            "FET",
            "RNDR",
            "WLD",
            "ARKM",
            "PENDLE",
            "JUP",
            "PYTH",
            "STRK",
            "MANTA",
            "ALT",
            "PIXEL",
            "DYM",
            # Meme coins
            "SHIB",
            "PEPE",
            "FLOKI",
            "BONK",
            "WIF",
            "MEME",
            "MYRO",
            "PONKE",
            "POPCAT",
            "TRUMP",
        ]

    async def fetch_market_data(self) -> Dict:
        """Fetch current market data for all symbols"""
        market_data = {}

        for symbol in self.symbols:
            try:
                # Get recent OHLC data (need more for proper analysis)
                data = await self.data_fetcher.get_recent_data(
                    symbol=symbol,
                    hours=24,
                    timeframe="15m",  # Last 24 hours for better signal detection
                )

                if data:
                    market_data[symbol] = data

            except Exception as e:
                logger.error(f"Error fetching data for {symbol}: {e}")

        logger.info(f"Fetched data for {len(market_data)} symbols")
        return market_data

    async def execute_signal(self, signal) -> bool:
        """
        Execute a trading signal through Hummingbot

        Args:
            signal: StrategySignal object

        Returns:
            True if executed successfully
        """
        try:
            # Check if we already have a position
            if signal.symbol in self.active_positions:
                logger.warning(f"Already have position in {signal.symbol}, skipping")
                return False

            # Check position limits
            if (
                len(self.active_positions)
                >= self.config["trading_rules"]["max_open_positions"]
            ):
                logger.warning(
                    f"Max positions reached ({len(self.active_positions)}), skipping {signal.symbol}"
                )
                return False

            # Log the signal
            logger.info(
                f"📊 Executing {signal.strategy_type.value} signal for {signal.symbol}"
            )
            logger.info(f"   Entry: ${signal.setup_data.get('entry_price', 0):.2f}")
            logger.info(f"   Size: ${signal.setup_data.get('position_size', 50):.2f}")
            logger.info(f"   Confidence: {signal.confidence:.1%}")

            # If Hummingbot is available, execute the trade
            if self.hummingbot_available and self.hummingbot:
                # Get the connector name (exchange)
                connector = os.getenv("HUMMINGBOT_CONNECTOR", "kraken_paper_trade")

                # Convert position size from USD to amount
                # For simplicity, using a fixed conversion (should get actual price)
                current_price = signal.setup_data.get("entry_price", 1)
                amount = (
                    signal.setup_data.get("position_size", 50) / current_price
                    if current_price > 0
                    else 0.001
                )

                # Create order through official Hummingbot API
                try:
                    result = await self.hummingbot.trading.place_order(
                        account_name="master_account",  # Use the only available account
                        connector_name=connector,
                        trading_pair=f"{signal.symbol}-USDT",  # Adjust pair format
                        trade_type="BUY",  # Use BUY instead of buy
                        amount=amount,
                        order_type="MARKET",  # Uppercase
                        price=None,  # Market order doesn't need price
                    )

                    if result:
                        # Track position
                        self.active_positions[signal.symbol] = {
                            "signal": signal,
                            "entry_time": datetime.now(),
                            "entry_price": signal.setup_data.get("entry_price", 0),
                            "position_size": signal.setup_data.get("position_size", 50),
                            "amount": amount,
                            "order_id": result.get("order_id"),
                            "connector": connector,
                        }

                        # Send Slack notification
                        if self.slack:
                            await self.slack.send_trade_opened(
                                symbol=signal.symbol,
                                strategy=signal.strategy_type.value,
                                entry_price=signal.setup_data.get("entry_price", 0),
                                position_size=signal.setup_data.get(
                                    "position_size", 50
                                ),
                                confidence=signal.confidence,
                            )

                        logger.info(f"✅ Trade executed: {signal.symbol}")
                        return True
                    else:
                        logger.error(f"❌ Trade execution failed")
                        return False

                except Exception as e:
                    logger.error(f"❌ Order creation error: {e}")
                    return False
            else:
                # Simulation mode - just track the signal
                self.active_positions[signal.symbol] = {
                    "signal": signal,
                    "entry_time": datetime.now(),
                    "entry_price": signal.setup_data.get("entry_price", 0),
                    "position_size": signal.setup_data.get("position_size", 50),
                    "simulated": True,
                }

                logger.info(f"📝 Signal recorded (simulation): {signal.symbol}")
                return True

        except Exception as e:
            logger.error(f"Error executing signal for {signal.symbol}: {e}")
            return False

    async def check_exits(self, market_data: Dict):
        """Check if any positions should be exited"""

        positions_to_close = []

        for symbol, position in self.active_positions.items():
            try:
                # Get current price
                if symbol not in market_data or not market_data[symbol]:
                    continue

                current_price = market_data[symbol][-1]["close"]
                entry_price = position["entry_price"]

                # Calculate P&L
                pnl_pct = ((current_price - entry_price) / entry_price) * 100

                # Check exit conditions
                should_exit = False
                exit_reason = ""

                # Stop loss
                if pnl_pct <= self.config["trading_rules"]["stop_loss"]:
                    should_exit = True
                    exit_reason = "stop_loss"

                # Take profit
                elif pnl_pct >= self.config["trading_rules"]["take_profit"]:
                    should_exit = True
                    exit_reason = "take_profit"

                # Time exit
                elif (
                    datetime.now() - position["entry_time"]
                ).total_seconds() / 3600 > self.config["trading_rules"][
                    "time_exit_hours"
                ]:
                    should_exit = True
                    exit_reason = "time_exit"

                if should_exit:
                    positions_to_close.append(
                        {
                            "symbol": symbol,
                            "reason": exit_reason,
                            "pnl_pct": pnl_pct,
                            "current_price": current_price,
                        }
                    )

            except Exception as e:
                logger.error(f"Error checking exit for {symbol}: {e}")

        # Close positions
        for pos in positions_to_close:
            await self.close_position(
                pos["symbol"], pos["reason"], pos["pnl_pct"], pos["current_price"]
            )

    async def close_position(
        self, symbol: str, reason: str, pnl_pct: float, current_price: float
    ):
        """Close a position"""
        try:
            position = self.active_positions.get(symbol)
            if not position:
                return

            logger.info(f"📊 Closing {symbol}: {reason} (P&L: {pnl_pct:+.1f}%)")

            # Execute close through Hummingbot
            if (
                self.hummingbot_available
                and self.hummingbot
                and not position.get("simulated")
            ):
                try:
                    connector = position.get("connector", "kraken_paper_trade")
                    amount = position.get("amount", 0.001)

                    result = await self.hummingbot.trading.place_order(
                        account_name="master_account",
                        connector_name=connector,
                        trading_pair=f"{symbol}-USDT",
                        trade_type="SELL",
                        amount=amount,
                        order_type="MARKET",
                        price=None,
                    )

                    if not result:
                        logger.error(f"Failed to close position")
                        return
                except Exception as e:
                    logger.error(f"Error closing position via API: {e}")
                    return

            # Calculate P&L
            pnl_usd = position["position_size"] * (pnl_pct / 100)

            # Send notification
            if self.slack:
                await self.slack.send_trade_closed(
                    symbol=symbol,
                    exit_reason=reason,
                    pnl_usd=pnl_usd,
                    pnl_pct=pnl_pct,
                    hold_time=(datetime.now() - position["entry_time"]).total_seconds()
                    / 3600,
                )

            # Remove from active positions
            del self.active_positions[symbol]

            logger.info(f"✅ Position closed: {symbol} ({reason})")

        except Exception as e:
            logger.error(f"Error closing position {symbol}: {e}")

    async def run_trading_loop(self):
        """Main trading loop"""

        logger.info("=" * 60)
        logger.info("STARTING SIMPLIFIED TRADING SYSTEM")
        logger.info(f"Mode: {'LIVE' if self.hummingbot_available else 'SIMULATION'}")
        logger.info(f"Symbols: {len(self.symbols)}")
        logger.info(f"Scan interval: {self.scan_interval} seconds")
        logger.info("=" * 60)

        while True:
            try:
                # Fetch market data
                market_data = await self.fetch_market_data()

                if not market_data:
                    logger.warning("No market data available, skipping scan")
                    await asyncio.sleep(self.scan_interval)
                    continue

                # Check for exit conditions first
                await self.check_exits(market_data)

                # Scan for new opportunities
                signals = await self.strategy_manager.scan_for_opportunities(
                    market_data
                )

                # Log scan results
                logger.info(
                    f"Scan complete: {len(signals)} signals, {len(self.active_positions)} positions"
                )

                # Execute signals
                for signal in signals:
                    # Skip if expired
                    if signal.is_expired():
                        continue

                    # Execute the signal
                    await self.execute_signal(signal)

                # Status update
                if self.active_positions:
                    logger.info(
                        f"Active positions: {list(self.active_positions.keys())}"
                    )

                # Wait for next scan
                await asyncio.sleep(self.scan_interval)

            except KeyboardInterrupt:
                logger.info("Shutting down...")
                break

            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                import traceback

                logger.error(f"Traceback: {traceback.format_exc()}")
                await asyncio.sleep(self.scan_interval)

    async def shutdown(self):
        """Clean shutdown"""
        logger.info("Shutting down trading system...")

        # Close all positions
        if self.active_positions:
            logger.info(f"Closing {len(self.active_positions)} positions...")
            for symbol in list(self.active_positions.keys()):
                await self.close_position(symbol, "shutdown", 0, 0)

        logger.info("Shutdown complete")


async def main():
    """Main entry point"""

    # Set environment variables for recovery mode
    os.environ["ML_ENABLED"] = "false"
    os.environ["SHADOW_TESTING_ENABLED"] = "false"
    os.environ["USE_SIMPLE_RULES"] = "true"

    # Create and run trading system
    system = SimplifiedTradingSystem()

    # Wait for Hummingbot connection to be tested
    if system.hummingbot:
        await system._test_hummingbot_connection()

    try:
        await system.run_trading_loop()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await system.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Trading system stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
