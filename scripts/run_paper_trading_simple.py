#!/usr/bin/env python3
"""
Market-Aware Paper Trading System with Intelligent Strategy Prioritization
Prioritizes strategies based on market analysis and manages positions intelligently
Version: 2.4.0 - Batch scan logging to capture all learning opportunities
BUILD_ID: 20250827-173000
"""

import asyncio
import os

# Force disable ML and Shadow Testing
os.environ["ML_ENABLED"] = "false"
os.environ["SHADOW_ENABLED"] = "false"

import sys  # noqa: E402
from pathlib import Path  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from typing import Dict, List  # noqa: E402
from loguru import logger  # noqa: E402
import signal as sig_handler  # noqa: E402

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

# Import configuration
from src.config.config_loader import ConfigLoader  # noqa: E402

from src.data.hybrid_fetcher import HybridDataFetcher  # noqa: E402
from src.trading.simple_paper_trader_v2 import SimplePaperTraderV2  # noqa: E402
from src.config.settings import Settings  # noqa: E402
from src.data.supabase_client import SupabaseClient  # noqa: E402

# Notification handled internally by SimplePaperTraderV2

# Import only what we need from strategies - NO ML
from src.strategies.dca.detector import DCADetector  # noqa: E402
from src.strategies.swing.detector import SwingDetector  # noqa: E402
from src.strategies.channel.detector import ChannelDetector  # noqa: E402
from src.strategies.simple_rules import SimpleRules  # noqa: E402
from src.strategies.regime_detector import RegimeDetector, MarketRegime  # noqa: E402
from src.trading.trade_limiter import TradeLimiter  # noqa: E402


class ScanBuffer:
    """Buffer for batching scan_history logs to respect Railway limits"""

    def __init__(
        self, supabase_client, max_size: int = 500, max_age_seconds: int = 300
    ):
        """
        Initialize scan buffer

        Args:
            supabase_client: Supabase client for database writes
            max_size: Maximum buffer size before flush (default 500)
            max_age_seconds: Maximum age in seconds before flush (default 300 = 5 minutes)
        """
        self.supabase = supabase_client
        self.buffer = []
        self.last_flush = datetime.now(timezone.utc)
        self.max_size = max_size
        self.max_age_seconds = max_age_seconds
        self.flush_in_progress = False
        self.total_scans_logged = 0
        self.total_batches_sent = 0

    async def add_scan(self, scan_data: Dict):
        """
        Add a scan to the buffer and flush if needed

        Args:
            scan_data: Scan data to log
        """
        # Add to buffer (instant, non-blocking)
        self.buffer.append(scan_data)

        # Check if we should flush (non-blocking check)
        if self.should_flush() and not self.flush_in_progress:
            # Fire and forget - doesn't block trading
            asyncio.create_task(self.flush())

    def should_flush(self) -> bool:
        """Check if buffer should be flushed"""
        if not self.buffer:
            return False

        # Flush if buffer is full
        if len(self.buffer) >= self.max_size:
            return True

        # Flush if time elapsed
        time_elapsed = (datetime.now(timezone.utc) - self.last_flush).total_seconds()
        if time_elapsed >= self.max_age_seconds:
            return True

        return False

    async def flush(self):
        """Flush buffer to database (runs async in background)"""
        if not self.buffer or self.flush_in_progress:
            return

        try:
            self.flush_in_progress = True

            # Copy buffer for sending (so we can continue adding)
            buffer_to_send = self.buffer.copy()
            self.buffer = []

            # Batch insert to scan_history
            if buffer_to_send:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.supabase.client.table("scan_history")
                    .insert(buffer_to_send)
                    .execute(),
                )

                self.total_scans_logged += len(buffer_to_send)
                self.total_batches_sent += 1

                logger.debug(
                    f"Flushed {len(buffer_to_send)} scans to database "
                    f"(Total: {self.total_scans_logged} scans in {self.total_batches_sent} batches)"
                )

            self.last_flush = datetime.now(timezone.utc)

        except Exception as e:
            logger.error(f"Error flushing scan buffer: {e}")
            # Re-add failed scans to buffer for retry
            self.buffer = buffer_to_send + self.buffer
        finally:
            self.flush_in_progress = False

    async def force_flush(self):
        """Force flush the buffer (e.g., on shutdown)"""
        if self.buffer:
            logger.info(f"Force flushing {len(self.buffer)} pending scans...")
            await self.flush()


class SimplifiedPaperTradingSystem:
    """
    Simplified paper trading system with NO ML dependencies
    Uses only rule-based strategies for complete independence
    """

    def __init__(self):
        self.settings = Settings()

        # CRITICAL: Disable ML and Shadow Testing completely
        os.environ["ML_ENABLED"] = "false"
        os.environ["SHADOW_ENABLED"] = "false"

        # Initialize components
        self.data_fetcher = HybridDataFetcher()
        
        # Load initial balance from unified config
        self.config_loader = ConfigLoader()
        unified_config = self.config_loader.load()
        initial_balance = unified_config.get("global_settings", {}).get("initial_balance", 10000.0)
        max_positions = unified_config.get("position_management", {}).get("max_positions_total", 150)
        max_per_strategy = unified_config.get("position_management", {}).get("max_positions_per_strategy", 50)
        
        self.paper_trader = SimplePaperTraderV2(
            initial_balance=initial_balance,  # Use config value (10000.0)
            max_positions=max_positions,  # Use config value (150)
            max_positions_per_strategy=max_per_strategy,  # Use config value (50)
            config_path="configs/paper_trading_config_unified.json",  # Use unified config
        )

        # Notifier is handled by SimplePaperTraderV2 internally
        # It respects the config flag for individual trade notifications

        # Initialize database
        self.supabase = SupabaseClient()

        # Load open positions from database on startup
        self._load_positions_from_database()

        # Initialize scan buffer for batch logging
        self.scan_buffer = ScanBuffer(self.supabase, max_size=500, max_age_seconds=300)
        logger.info(
            "Scan buffer initialized - will batch log every 5 minutes or 500 scans"
        )

        # Track last heartbeat time to avoid too frequent updates
        self.last_heartbeat_time = datetime.now(timezone.utc)

    def _load_positions_from_database(self):
        """Load all open positions from database into memory on startup"""
        try:
            logger.info("Loading open positions from database...")

            # Get all open positions from database
            open_trades = (
                self.supabase.client.table("paper_trades")
                .select("*")
                .eq("status", "FILLED")
                .is_("exit_price", "null")
                .execute()
            )

            if not open_trades.data:
                logger.info("No open positions found in database")
                return

            # Group trades by trade_group_id to identify unique positions
            positions_by_group = {}
            for trade in open_trades.data:
                group_id = trade.get("trade_group_id")
                if group_id:
                    if group_id not in positions_by_group:
                        positions_by_group[group_id] = []
                    positions_by_group[group_id].append(trade)

            # Count positions by strategy
            strategy_counts = {"DCA": 0, "SWING": 0, "CHANNEL": 0}
            total_positions = len(positions_by_group)

            for group_id, trades in positions_by_group.items():
                # Get strategy from first trade in group
                strategy = trades[0].get("strategy", "UNKNOWN")
                if strategy in strategy_counts:
                    strategy_counts[strategy] += 1

            logger.info(f"Loaded {total_positions} open positions from database:")
            logger.info(f"  DCA: {strategy_counts['DCA']}")
            logger.info(f"  SWING: {strategy_counts['SWING']}")
            logger.info(f"  CHANNEL: {strategy_counts['CHANNEL']}")

            # Check if we're over limits
            if total_positions > 150:
                logger.error(
                    f"⚠️ WARNING: {total_positions} positions exceeds total limit of 150!"
                )

            for strategy, count in strategy_counts.items():
                if count > 50:
                    logger.error(
                        f"⚠️ WARNING: {strategy} has {count} positions (limit: 50)!"
                    )

        except Exception as e:
            logger.error(f"Failed to load positions from database: {e}")
            # Don't crash on this error, continue with empty positions

        # Load configuration using unified config loader
        self.config_loader = ConfigLoader()
        unified_config = self.config_loader.load()

        # Build config from unified configuration
        self.config = {
            "ml_enabled": False,  # ALWAYS FALSE
            "shadow_enabled": False,  # ALWAYS FALSE
            "base_position_usd": unified_config.get("position_management", {})
            .get("position_sizing", {})
            .get("base_position_size_usd", 50.0),
            "max_open_positions": unified_config.get("position_management", {}).get(
                "max_positions_total", 30
            ),
            # Detection thresholds from unified config
            "dca_drop_threshold": unified_config.get("strategies", {})
            .get("DCA", {})
            .get("detection_thresholds", {})
            .get("drop_threshold", -4.0),
            "swing_breakout_threshold": unified_config.get("strategies", {})
            .get("SWING", {})
            .get("detection_thresholds", {})
            .get("breakout_threshold", 1.015),
            "buy_zone": unified_config.get("strategies", {})
            .get("CHANNEL", {})
            .get("detection_thresholds", {})
            .get("buy_zone", 0.15),
            "sell_zone": unified_config.get("strategies", {})
            .get("CHANNEL", {})
            .get("detection_thresholds", {})
            .get("sell_zone", 0.85),
            "channel_strength_min": unified_config.get("strategies", {})
            .get("CHANNEL", {})
            .get("detection_thresholds", {})
            .get("channel_strength_min", 0.75),
            # Volume and other thresholds
            "swing_volume_surge": unified_config.get("strategies", {})
            .get("SWING", {})
            .get("detection_thresholds", {})
            .get("volume_surge", 1.5),
            "channel_touches": unified_config.get("strategies", {})
            .get("CHANNEL", {})
            .get("detection_thresholds", {})
            .get("channel_touches", 3),
            # ML confidence removed - paper trading is rule-based only
            # "min_confidence" check has been disabled
            "scan_interval": unified_config.get("global_settings", {}).get(
                "trading_cycle_seconds", 300
            ),  # Default 5 minutes
            "position_size": 50.0,
            "max_position_duration_hours": 72,
        }

        # Initialize ONLY rule-based components
        self.simple_rules = SimpleRules(self.config)
        self.dca_detector = DCADetector(self.config)
        self.swing_detector = SwingDetector(self.config)
        self.channel_detector = ChannelDetector(self.config)
        self.regime_detector = RegimeDetector(enabled=True)
        self.current_regime = MarketRegime.NORMAL  # Default until first scan

        # Initialize Trade Limiter for revenge trading protection
        self.trade_limiter = TradeLimiter()
        logger.info("✅ Trade Limiter initialized for revenge trading protection")

        # Track active positions
        self.active_positions = self.paper_trader.positions

        # Track market strategy changes
        self.last_best_strategy = None
        self.strategy_change_time = None
        self.position_timestamps = {}  # Track when each position was opened

        # Shutdown flag
        self.shutdown = False

        logger.info("=" * 80)
        logger.info("🚀 MARKET-AWARE PAPER TRADING SYSTEM v2.3.2")
        logger.info(
            "   BUILD_ID: 20250827-164500 - Fixed timezone and method signatures"
        )
        logger.info("   Mode: Rule-Based with Market Intelligence")
        logger.info(f"   Balance: ${self.paper_trader.balance:.2f}")
        logger.info(f"   Position Size: ${self.config['position_size']}")
        logger.info(
            f"   Max Positions: {self.paper_trader.max_positions} (50 per strategy)"
        )
        logger.info(f"   DCA Drop: {self.config['dca_drop_threshold']}%")
        logger.info(
            f"   Swing Breakout: {self.config['swing_breakout_threshold']} "
            f"(volume: {self.config['swing_volume_surge']}x)"
        )
        logger.info(
            f"   Channel Buy Zone: {self.config.get('buy_zone', 0.05)} "
            f"(touches: {self.config.get('channel_touches', 3)})"
        )
        logger.info("   📈 Market analysis guides strategy prioritization")
        logger.info("=" * 80)

    def get_symbols(self) -> List[str]:
        """Get symbols to monitor"""
        # Full list of 90 symbols
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
            # Solid Mid-Caps
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
        ]

    def get_market_best_strategy(self) -> str:
        """Get the current best strategy from market analysis cache"""
        try:
            # Query market summary cache for best strategy
            result = (
                self.supabase.client.table("market_summary_cache")
                .select("best_strategy")
                .order("calculated_at", desc=True)
                .limit(1)
                .execute()
            )

            if result.data and len(result.data) > 0:
                best_strategy = result.data[0].get("best_strategy", "").upper()
                if best_strategy in ["DCA", "SWING", "CHANNEL"]:
                    return best_strategy
        except Exception as e:
            logger.debug(f"Could not fetch best strategy from cache: {e}")

        # Default to no preference (equal allocation)
        return None

    def assess_market_sentiment(self, signals: list) -> str:
        """Assess overall market sentiment from signals"""
        if not signals:
            return "NEUTRAL"

        # Count bullish (buy) vs bearish indicators
        bullish = 0
        bearish = 0

        for signal in signals:
            strategy = signal.get("strategy", "")
            if strategy == "DCA":
                # DCA signals indicate oversold/bearish recently but potential bounce
                bullish += 0.5  # Mildly bullish (buying dip)
            elif strategy == "SWING":
                # SWING signals indicate breakout/momentum
                bullish += 1  # Strongly bullish
            elif strategy == "CHANNEL":
                # CHANNEL at bottom is bullish, at top is bearish
                position = signal.get("position", 0.5)
                if position <= 0.15:  # Near bottom
                    bullish += 1
                elif position >= 0.85:  # Near top
                    bearish += 1

        # Determine overall sentiment
        if bullish > bearish * 1.5:
            return "BULLISH"
        elif bearish > bullish * 1.5:
            return "BEARISH"
        else:
            return "NEUTRAL"

    async def handle_market_transition(self, new_best_strategy: str):
        """Handle market strategy transitions by closing stale positions"""
        if not new_best_strategy or new_best_strategy == self.last_best_strategy:
            return  # No change

        # First time or actual strategy change
        if self.last_best_strategy is None:
            self.last_best_strategy = new_best_strategy
            self.strategy_change_time = datetime.now(timezone.utc)
            return

        logger.info(
            f"📊 Market shift detected: {self.last_best_strategy} → {new_best_strategy}"
        )

        # Check how long since strategy changed
        time_since_change = (
            datetime.now(timezone.utc) - self.strategy_change_time
        ).total_seconds() / 3600  # hours

        # Get current prices for all positions
        current_prices = {}
        for symbol in list(self.active_positions.keys()):
            try:
                data = await self.data_fetcher.get_recent_data(
                    symbol=symbol, timeframe="1m", hours=1
                )
                if data:
                    current_prices[symbol] = data[-1]["close"]
            except Exception:
                pass

        # Evaluate positions from old best strategy
        positions_to_close = []
        for symbol, position in self.active_positions.items():
            if position.strategy != self.last_best_strategy:
                continue  # Only check old best strategy positions

            if symbol not in current_prices:
                continue

            current_price = current_prices[symbol]
            pnl_pct = (
                (current_price - position.entry_price) / position.entry_price
            ) * 100
            position_age = (
                datetime.now(timezone.utc)
                - self.position_timestamps.get(symbol, datetime.now(timezone.utc))
            ).total_seconds() / 3600

            # Scenario 5 logic: tiered closing based on performance and age
            close_position = False
            reason = ""

            if pnl_pct <= -5:  # Immediate: Close big losers
                close_position = True
                reason = "STRATEGY_SHIFT_BIG_LOSS"
            elif (
                pnl_pct <= -2 and time_since_change >= 2
            ):  # 2-4 hours: Close moderate losers
                close_position = True
                reason = "STRATEGY_SHIFT_MODERATE_LOSS"
            elif (
                abs(pnl_pct) < 2 and time_since_change >= 4
            ):  # 4 hours: Close flat positions
                close_position = True
                reason = "STRATEGY_SHIFT_FLAT"
            elif pnl_pct > 0 and position_age >= 12:  # 12 hours: Close stale winners
                close_position = True
                reason = "STRATEGY_SHIFT_STALE_WIN"

            if close_position:
                positions_to_close.append((symbol, position, pnl_pct, reason))

        # Close identified positions
        for symbol, position, pnl_pct, reason in positions_to_close:
            logger.info(
                f"Closing {position.strategy} position {symbol} (P&L: {pnl_pct:.2f}%) - {reason}"
            )
            try:
                await self.paper_trader.close_position(
                    symbol=symbol, market_price=current_prices[symbol], reason=reason
                )
            except Exception as e:
                logger.error(f"Failed to close {symbol}: {e}")

        # Update tracking
        if positions_to_close:
            logger.info(
                f"Closed {len(positions_to_close)} positions due to strategy shift"
            )

        self.last_best_strategy = new_best_strategy
        self.strategy_change_time = datetime.now(timezone.utc)

    async def close_worst_positions(self, strategy: str, count: int) -> int:
        """Close worst performing positions of a strategy to make room"""
        closed = 0
        try:
            # Get current positions for this strategy
            strategy_positions = [
                (symbol, pos)
                for symbol, pos in self.active_positions.items()
                if pos.strategy == strategy
            ]

            if not strategy_positions:
                return 0

            # Get current prices for all positions
            current_prices = {}
            for symbol, _ in strategy_positions:
                try:
                    data = await self.data_fetcher.get_recent_data(
                        symbol=symbol, timeframe="1m", hours=1
                    )
                    if data:
                        current_prices[symbol] = data[-1]["close"]
                except Exception:
                    pass

            # Calculate P&L for each position
            positions_with_pnl = []
            for symbol, position in strategy_positions:
                if symbol in current_prices:
                    current_price = current_prices[symbol]
                    pnl_pct = (
                        (current_price - position.entry_price) / position.entry_price
                    ) * 100
                    positions_with_pnl.append((symbol, position, pnl_pct))

            # Sort by P&L (worst first)
            positions_with_pnl.sort(key=lambda x: x[2])

            # Close worst positions
            for symbol, position, pnl_pct in positions_with_pnl[:count]:
                logger.info(
                    f"Closing worst {strategy} position: {symbol} (P&L: {pnl_pct:.2f}%)"
                )

                result = await self.paper_trader.close_position(
                    symbol=symbol,
                    current_price=current_prices[symbol],
                    exit_reason="POSITION_LIMIT_CLEANUP",
                )

                if result.get("success"):
                    closed += 1
                    if closed >= count:
                        break

        except Exception as e:
            logger.error(f"Error closing worst positions: {e}")

        return closed

    async def scan_for_opportunities(self):
        """
        Market-aware scanning that prioritizes based on market analysis
        """
        symbols = self.get_symbols()

        # Skip symbols we already have positions in
        symbols_with_positions = set(self.active_positions.keys())
        available_symbols = [s for s in symbols if s not in symbols_with_positions]

        if not available_symbols:
            logger.info("All symbols have active positions")
            return

        logger.info(
            f"Scanning {len(available_symbols)} symbols for opportunities... (detailed logs suppressed for Railway)"
        )

        # Get best strategy from market analysis
        best_strategy = self.get_market_best_strategy()
        if best_strategy:
            logger.info(f"📈 Market Analysis: {best_strategy} is best strategy")
        else:
            logger.info("📊 Market Analysis: No clear best strategy (equal allocation)")

        # Handle market transitions (Scenario 5)
        await self.handle_market_transition(best_strategy)

        # Fetch market data
        market_data = {}
        for symbol in available_symbols:
            try:
                # Get 1-minute data for faster signals
                data = await self.data_fetcher.get_recent_data(
                    symbol=symbol, timeframe="1m", hours=24
                )
                if data and len(data) > 100:
                    market_data[symbol] = data
            except Exception as e:
                logger.debug(f"Could not fetch data for {symbol}: {e}")

        if not market_data:
            logger.warning("No market data available")
            return

        # Update BTC price for regime detection
        if "BTC" in market_data and market_data["BTC"]:
            btc_price = market_data["BTC"][-1]["close"]
            self.regime_detector.update_btc_price(btc_price)

        # Detect regime
        self.current_regime = self.regime_detector.get_market_regime()
        if self.current_regime == MarketRegime.PANIC:
            logger.warning("🚨 Market PANIC detected - skipping all new trades")
            return

        # Log regime and volatility info
        regime_stats = self.regime_detector.get_regime_stats()
        if regime_stats.get("volatility_24h"):
            logger.info(
                f"Market Regime: {self.current_regime.value}, Volatility: {regime_stats['volatility_24h']:.2f}%"
            )

        # Fetch BTC price for correlations
        if "BTC" in market_data:
            btc_data = market_data["BTC"]
            if btc_data and len(btc_data) > 0:
                self._btc_price = btc_data[-1]["close"]
            else:
                self._btc_price = 0.0
        else:
            self._btc_price = 0.0

        # Collect signals by strategy
        signals_by_strategy = {"DCA": [], "SWING": [], "CHANNEL": []}

        for symbol, data in market_data.items():
            try:
                current_price = data[-1]["close"] if data else 0

                # Check each strategy type and log ALL scans
                # DCA - Check if disabled due to volatility
                if not self.regime_detector.should_disable_strategy("DCA"):
                    dca_signal = self.simple_rules.check_dca_setup(symbol, data)
                    if dca_signal and dca_signal.get("signal"):
                        dca_signal["should_trade"] = True
                        dca_signal["strategy"] = "DCA"
                        # Ensure we have current_price in all signals
                        if "current_price" not in dca_signal:
                            dca_signal["current_price"] = dca_signal.get(
                                "price", current_price
                            )
                        signals_by_strategy["DCA"].append(dca_signal)
                        # Log signal detection for ML learning
                        await self.log_scan(
                            symbol,
                            "DCA",
                            "BUY",
                            "Signal detected",
                            confidence=dca_signal["confidence"],
                            metadata={"drop_pct": dca_signal.get("drop_pct", 0)},
                            market_data=data,
                        )
                    else:
                        # Log no signal for complete ML dataset
                        await self.log_scan(
                            symbol,
                            "DCA",
                            "SKIP",
                            "No signal",
                            confidence=0.0,
                            market_data=data,
                        )

                # Swing - Check if disabled due to volatility
                if not self.regime_detector.should_disable_strategy("SWING"):
                    swing_signal = self.simple_rules.check_swing_setup(symbol, data)
                    if swing_signal and swing_signal.get("signal"):
                        swing_signal["should_trade"] = True
                        swing_signal["strategy"] = "SWING"
                        if "current_price" not in swing_signal:
                            swing_signal["current_price"] = swing_signal.get(
                                "price", current_price
                            )
                        signals_by_strategy["SWING"].append(swing_signal)
                        # Log signal detection for ML learning
                        await self.log_scan(
                            symbol,
                            "SWING",
                            "BUY",
                            "Signal detected",
                            confidence=swing_signal["confidence"],
                            metadata={
                                "breakout_pct": swing_signal.get("breakout_pct", 0)
                            },
                            market_data=data,
                        )
                    else:
                        # Log no signal for complete ML dataset
                        await self.log_scan(
                            symbol,
                            "SWING",
                            "SKIP",
                            "No signal",
                            confidence=0.0,
                            market_data=data,
                        )

                # Channel - Check if disabled due to volatility
                if not self.regime_detector.should_disable_strategy("CHANNEL"):
                    channel_signal = self.simple_rules.check_channel_setup(symbol, data)
                    if channel_signal and channel_signal.get("signal"):
                        channel_signal["should_trade"] = True
                        channel_signal["strategy"] = "CHANNEL"
                        if "current_price" not in channel_signal:
                            channel_signal["current_price"] = channel_signal.get(
                                "price", current_price
                            )
                        signals_by_strategy["CHANNEL"].append(channel_signal)
                        # Log signal detection for ML learning
                        await self.log_scan(
                            symbol,
                            "CHANNEL",
                            "BUY",
                            "Signal detected",
                            confidence=channel_signal["confidence"],
                            metadata={"position": channel_signal.get("position", 0)},
                            market_data=data,
                        )
                    else:
                        # Log no signal for complete ML dataset
                        await self.log_scan(
                            symbol,
                            "CHANNEL",
                            "SKIP",
                            "No signal",
                            confidence=0.0,
                            market_data=data,
                        )

            except Exception as e:
                logger.error(f"Error evaluating {symbol}: {e}")
                continue

        # Log signal counts and scan completion
        total_signals = sum(len(s) for s in signals_by_strategy.values())
        logger.info(
            f"✅ Scan complete! Found {total_signals} signals: DCA={len(signals_by_strategy['DCA'])}, "
            f"SWING={len(signals_by_strategy['SWING'])}, CHANNEL={len(signals_by_strategy['CHANNEL'])}"
        )

        # Build prioritized signal list based on market analysis
        prioritized_signals = []

        if best_strategy:
            # Scenario 1-4: Market has a best strategy
            # First, add all signals from best strategy
            prioritized_signals.extend(signals_by_strategy[best_strategy])

            # Then add others if best strategy has no/few signals (Scenario 1C)
            if len(prioritized_signals) < 3:  # If best strategy has few signals
                # Check market sentiment alignment
                all_signals = []
                for strategy_signals in signals_by_strategy.values():
                    all_signals.extend(strategy_signals)

                sentiment = self.assess_market_sentiment(all_signals)
                logger.info(f"Market sentiment: {sentiment}")

                # Add aligned signals from other strategies
                for strategy in ["DCA", "SWING", "CHANNEL"]:
                    if strategy != best_strategy:
                        for signal in signals_by_strategy[strategy]:
                            # Check if signal aligns with market sentiment
                            signal_sentiment = (
                                "BULLISH"  # Most signals are bullish by nature
                            )
                            if strategy == "DCA":
                                signal_sentiment = "BULLISH"  # Buying dips
                            elif strategy == "SWING":
                                signal_sentiment = "BULLISH"  # Breakout
                            elif strategy == "CHANNEL":
                                position = signal.get("position", 0.5)
                                signal_sentiment = (
                                    "BULLISH" if position <= 0.5 else "BEARISH"
                                )

                            # Add if aligned or neutral
                            if sentiment == "NEUTRAL" or signal_sentiment == sentiment:
                                prioritized_signals.append(signal)
        else:
            # Scenario 6: No clear best - equal allocation
            # Interleave signals from each strategy for balance
            max_signals = max(len(s) for s in signals_by_strategy.values())
            for i in range(max_signals):
                for strategy in ["DCA", "SWING", "CHANNEL"]:
                    if i < len(signals_by_strategy[strategy]):
                        prioritized_signals.append(signals_by_strategy[strategy][i])

        # Sort by confidence as secondary factor (Scenario 3B)
        prioritized_signals.sort(key=lambda x: x.get("confidence", 0), reverse=True)

        # Check strategy position limits and handle overflow
        strategy_positions_count = {}
        for strategy in ["DCA", "SWING", "CHANNEL"]:
            count = sum(
                1 for p in self.active_positions.values() if p.strategy == strategy
            )
            strategy_positions_count[strategy] = count
            if count > 0:
                logger.info(f"{strategy} positions: {count}/50")

        # Execute signals with smart position management
        executed = 0
        available_slots = self.paper_trader.max_positions - len(self.active_positions)

        for trading_signal in prioritized_signals:
            if available_slots <= 0:
                break

            # ML confidence check removed - paper trading is rule-based only
            strategy = trading_signal["strategy"]
            symbol = trading_signal["symbol"]

            # Check if strategy is at limit (Scenario 2)
            if (
                strategy_positions_count.get(strategy, 0)
                >= self.paper_trader.max_positions_per_strategy
            ):
                # Close worst performer to make room (Scenario 2C)
                logger.info(
                    f"{strategy} at limit - closing worst position to make room"
                )
                closed = await self.close_worst_positions(strategy, 1)
                if closed > 0:
                    strategy_positions_count[strategy] -= closed
                else:
                    logger.warning(
                        f"Could not close positions for {strategy}, skipping signal"
                    )
                    continue

            # Check trade limiter
            can_trade, reason = self.trade_limiter.can_trade_symbol(symbol)
            if not can_trade:
                logger.warning(f"⛔ Skipping {symbol}: {reason}")
                continue

            # Execute trade
            result = await self.execute_trade(trading_signal)
            if result:
                executed += 1
                available_slots -= 1
                strategy_positions_count[strategy] = (
                    strategy_positions_count.get(strategy, 0) + 1
                )

                # Log successful execution with market context
                if best_strategy:
                    if strategy == best_strategy:
                        logger.info(
                            f"✅ Executed {strategy} trade (market recommended)"
                        )
                    else:
                        logger.info(
                            f"✅ Executed {strategy} trade (fallback from {best_strategy})"
                        )

        if executed > 0:
            logger.info(f"Executed {executed} trades this scan")
        elif total_signals > 0:
            logger.info("No trades executed despite signals (position/trade limits)")
        else:
            logger.info("No trading opportunities found")

    def _calculate_features(self, symbol: str, market_data: list) -> dict:
        """Calculate technical features from market data"""
        try:
            if not market_data or len(market_data) < 20:
                return {
                    "price_drop": 0,
                    "rsi": 50,
                    "volume_ratio": 1,
                    "distance_from_support": 0,
                    "btc_correlation": 0,
                    "market_regime": 1
                    if self.current_regime == MarketRegime.NORMAL
                    else 0,
                }

            # Calculate price drop from 20-bar high
            closes = [d["close"] for d in market_data[-20:]]
            highs = [d["high"] for d in market_data[-20:]]
            current_price = closes[-1]
            high_20 = max(highs)
            price_drop = (
                ((current_price - high_20) / high_20) * 100 if high_20 > 0 else 0
            )

            # Calculate RSI (14 period)
            rsi = self._calculate_rsi(closes[-15:])

            # Calculate volume ratio
            volumes = [d["volume"] for d in market_data[-20:]]
            avg_volume = (
                sum(volumes[:-1]) / len(volumes[:-1]) if len(volumes) > 1 else 1
            )
            current_volume = volumes[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

            # Calculate distance from support (use 20-bar low as support)
            lows = [d["low"] for d in market_data[-20:]]
            support = min(lows)
            distance_from_support = (
                ((current_price - support) / support) * 100 if support > 0 else 0
            )

            # BTC correlation would need BTC data - for now use 0
            btc_correlation = 0

            # Market regime as numeric
            regime_value = 0
            if self.current_regime == MarketRegime.NORMAL:
                regime_value = 1
            elif self.current_regime == MarketRegime.GREED:
                regime_value = 2
            elif self.current_regime == MarketRegime.PANIC:
                regime_value = -1

            return {
                "price_drop": round(price_drop, 2),
                "rsi": round(rsi, 2),
                "volume_ratio": round(volume_ratio, 2),
                "distance_from_support": round(distance_from_support, 2),
                "btc_correlation": btc_correlation,
                "market_regime": regime_value,
            }
        except Exception as e:
            logger.debug(f"Error calculating features: {e}")
            return {
                "price_drop": 0,
                "rsi": 50,
                "volume_ratio": 1,
                "distance_from_support": 0,
                "btc_correlation": 0,
                "market_regime": 0,
            }

    def _calculate_rsi(self, prices: list, period: int = 14) -> float:
        """Calculate RSI from price list"""
        if len(prices) < 2:
            return 50.0

        gains = []
        losses = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        avg_gain = sum(gains) / len(gains) if gains else 0
        avg_loss = sum(losses) / len(losses) if losses else 0

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    async def update_heartbeat(self):
        """Update system heartbeat to show service is running"""
        try:
            # Only update heartbeat once per minute to avoid excessive DB writes
            current_time = datetime.now(timezone.utc)
            if (current_time - self.last_heartbeat_time).seconds < 60:
                return

            # Update heartbeat with current system status
            heartbeat_data = {
                "service_name": "paper_trading_engine",
                "last_heartbeat": current_time.isoformat(),
                "status": "running",
                "metadata": {
                    "symbols_monitored": len(self.symbols)
                    if hasattr(self, "symbols")
                    else 0,
                    "positions_open": len(self.paper_trader.positions),
                    "market_regime": self.current_regime.name
                    if hasattr(self, "current_regime") and self.current_regime
                    else "UNKNOWN",
                    "balance": float(self.paper_trader.balance),
                    "scan_interval": self.config.get("scan_interval", 60),
                },
            }

            # Upsert to ensure we update existing record or create new one
            self.supabase.client.table("system_heartbeat").upsert(
                heartbeat_data, on_conflict="service_name"
            ).execute()

            self.last_heartbeat_time = current_time
            logger.debug("Heartbeat updated successfully")

        except Exception as e:
            # Silent fail - don't let heartbeat errors disrupt trading
            logger.debug(f"Failed to update heartbeat: {e}")

    async def log_scan(
        self,
        symbol: str,
        strategy: str,
        decision: str,
        reason: str,
        confidence: float = 0.0,
        metadata: dict = None,
        market_data: list = None,
    ):
        """Log scan attempt to scan_history table for ML/Shadow analysis"""
        try:
            # Calculate features from market data if provided
            features = (
                self._calculate_features(symbol, market_data)
                if market_data
                else {
                    "price_drop": metadata.get("drop_pct", 0) if metadata else 0,
                    "rsi": 50,
                    "volume_ratio": 1,
                    "distance_from_support": 0,
                    "btc_correlation": 0,
                    "market_regime": 1
                    if self.current_regime == MarketRegime.NORMAL
                    else 0,
                }
            )

            # Get BTC price if available
            btc_price = 0.0
            if hasattr(self, "_btc_price"):
                btc_price = self._btc_price

            scan_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "symbol": symbol,
                "strategy_name": strategy,
                "decision": decision,
                "reason": reason,
                "market_regime": self.current_regime.name
                if self.current_regime
                else "UNKNOWN",
                "confidence_score": confidence,
                "metadata": metadata or {},
                "features": features,
                "btc_price": btc_price,
            }

            # Add to buffer instead of direct insert - instant and non-blocking
            await self.scan_buffer.add_scan(scan_data)

        except Exception as e:
            # Don't let logging errors stop trading
            logger.error(f"Could not log scan for {symbol}: {e}")

    async def execute_trade(self, trading_signal: Dict) -> bool:
        """Execute a trade based on signal"""
        try:
            symbol = trading_signal["symbol"]
            strategy = trading_signal.get("strategy", "unknown")

            # CRITICAL: Check database for existing positions (not just in-memory)
            db = SupabaseClient()

            # Check if we already have an open position for this symbol
            existing = (
                db.client.table("paper_trades")
                .select("trade_group_id, strategy")
                .eq("symbol", symbol)
                .eq("status", "FILLED")
                .is_("exit_price", "null")
                .execute()
            )

            if existing.data:
                # Group by trade_group_id to count unique positions
                unique_groups = set(trade["trade_group_id"] for trade in existing.data)
                if unique_groups:
                    logger.warning(
                        f"⚠️ Database shows {len(unique_groups)} open position(s) for {symbol}, skipping new signal"
                    )
                    return False

            # Check strategy position count in database
            strategy_result = (
                db.client.table("paper_trades")
                .select("trade_group_id")
                .eq("strategy", strategy.upper())
                .eq("status", "FILLED")
                .is_("exit_price", "null")
                .execute()
            )

            # Count unique trade groups for this strategy
            if strategy_result.data:
                unique_strategy_groups = set(
                    trade["trade_group_id"] for trade in strategy_result.data
                )
                strategy_count = len(unique_strategy_groups)

                if strategy_count >= 50:
                    logger.error(
                        f"❌ {strategy} has {strategy_count} positions in database (limit: 50), skipping"
                    )
                    return False
                else:
                    logger.debug(
                        f"{strategy} has {strategy_count}/50 positions in database"
                    )

            # Calculate position size
            position_size = self.config["position_size"]

            # Adjust for regime if needed
            if hasattr(self, "regime_detector"):
                regime = self.regime_detector.get_market_regime()
                if regime == MarketRegime.CAUTION:
                    position_size *= 0.5

            # Execute trade (using async method)
            logger.info(f"[BUILD:20250826-194500] Executing trade for {symbol}")
            result = await self.paper_trader.open_position(
                symbol=symbol,
                usd_amount=position_size,
                market_price=trading_signal["current_price"],
                strategy=strategy,
            )

            # Log what type result is to debug Railway cache issue
            logger.info(
                f"[BUILD:20250826-194500] Result type: {type(result)}, value: {result}"
            )

            # Extra defensive check for Railway environment
            if not isinstance(result, dict):
                logger.error(
                    f"CRITICAL: open_position returned {type(result)} instead of dict!"
                )
                logger.error(f"Result value: {result}")
                logger.error(f"Paper trader class: {type(self.paper_trader)}")
                return False

            if result.get("success"):
                logger.info(
                    f"✅ Opened {strategy} position: {symbol} @ ${trading_signal['current_price']:.4f}"
                )

                # Track position timestamp for market transitions
                self.position_timestamps[symbol] = datetime.now(timezone.utc)

                # Notification handled by SimplePaperTraderV2 based on config

                return True

            return False

        except Exception as e:
            # Better error handling - check if trading_signal is valid
            symbol = "UNKNOWN"
            try:
                if isinstance(trading_signal, dict) and "symbol" in trading_signal:
                    symbol = trading_signal["symbol"]
                else:
                    logger.error(
                        f"Invalid trading_signal type: {type(trading_signal)}, value: {trading_signal}"
                    )
            except Exception:
                pass

            logger.error(f"Error executing trade for {symbol}: {e}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False

    async def check_exits(self):
        """Check if any positions should be closed"""
        # Gather current prices for all positions
        current_prices = {}
        for symbol in list(self.active_positions.keys()):
            try:
                # Get current price
                data = await self.data_fetcher.get_recent_data(
                    symbol=symbol, timeframe="1m", hours=1
                )

                if data:
                    current_prices[symbol] = data[-1]["close"]
            except Exception as e:
                logger.debug(f"Could not get price for {symbol}: {e}")
                continue

        # Check and close positions with exit conditions
        if current_prices:
            closed_trades = await self.paper_trader.check_and_close_positions(
                current_prices=current_prices,
                max_hold_hours=self.config["max_position_duration_hours"],
            )

            for trade in closed_trades:
                logger.info(
                    f"📊 Closed {trade.symbol}: {trade.exit_reason} "
                    f"P&L: ${trade.pnl_usd:.2f}"
                )

                # Clean up position timestamp
                if trade.symbol in self.position_timestamps:
                    del self.position_timestamps[trade.symbol]

                # Update trade limiter based on exit
                if trade.exit_reason == "stop_loss":
                    self.trade_limiter.record_stop_loss(trade.symbol)
                else:
                    # Record successful trade for potential reset
                    # Get take profit target from position if available
                    take_profit_target = 0.10  # Default 10%, could get from position
                    self.trade_limiter.record_successful_trade(
                        trade.symbol,
                        trade.exit_reason,
                        trade.pnl_percent if hasattr(trade, "pnl_percent") else None,
                        take_profit_target,
                    )

                # Log outcome for research
                try:
                    self.supabase.client.table("trade_logs").insert(
                        {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "symbol": trade.symbol,
                            "strategy_name": trade.strategy,
                            "action": "CLOSE",
                            "price": trade.exit_price,
                            "quantity": trade.amount,
                            "position_size": trade.entry_price * trade.amount,
                            "pnl": trade.pnl_usd,
                            "exit_reason": trade.exit_reason,
                            "ml_confidence": None,  # No ML
                            "hold_duration_hours": (trade.exit_time - trade.entry_time).total_seconds() / 3600,
                        }
                    ).execute()
                except Exception as e:
                    logger.debug(f"Could not log trade: {e}")

                # Notification handled by SimplePaperTraderV2 based on config

    async def run(self):
        """Main trading loop"""
        logger.info("Starting simplified paper trading loop...")

        while not self.shutdown:
            try:
                # Check kill switch
                if not self.config_loader.is_trading_enabled():
                    logger.warning(
                        "Trading is globally disabled via kill switch. Waiting..."
                    )
                    await asyncio.sleep(60)  # Check every minute
                    continue
                # Update heartbeat to show service is running
                await self.update_heartbeat()

                # Scan for new opportunities
                await self.scan_for_opportunities()

                # Check exits for existing positions
                await self.check_exits()

                # Show portfolio status
                stats = self.paper_trader.get_portfolio_stats()
                logger.info(
                    f"Portfolio: Balance ${stats['balance']:.2f}, "
                    f"Positions: {stats['positions']}, "
                    f"P&L: ${stats['total_pnl']:.2f}"
                )

                # Show trade limiter status if active
                limiter_stats = self.trade_limiter.get_limiter_stats()
                if (
                    limiter_stats["symbols_on_cooldown"]
                    or limiter_stats["symbols_banned"]
                ):
                    logger.warning(
                        f"Trade Limiter Active: "
                        f"{len(limiter_stats['symbols_on_cooldown'])} cooldowns, "
                        f"{len(limiter_stats['symbols_banned'])} bans"
                    )

                # Performance metrics are automatically saved by SimplePaperTraderV2
                # when trades are closed, so no need to manually insert here

                # Wait before next scan
                await asyncio.sleep(self.config["scan_interval"])

            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(60)

    def handle_shutdown(self, signum, frame):
        """Handle shutdown signal"""
        logger.info("Shutdown signal received, closing positions...")
        self.shutdown = True

        # Force flush any pending scans before shutdown
        if hasattr(self, "scan_buffer"):
            asyncio.create_task(self.scan_buffer.force_flush())


async def main():
    """Main entry point"""
    system = SimplifiedPaperTradingSystem()

    # Setup signal handlers
    sig_handler.signal(sig_handler.SIGINT, system.handle_shutdown)
    sig_handler.signal(sig_handler.SIGTERM, system.handle_shutdown)

    # Start dashboard if not on Railway
    if not os.environ.get("RAILWAY_ENVIRONMENT"):
        # Run dashboard locally
        import socket
        import threading

        # Check if port is available
        port_available = True
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", 8080))
            except OSError:
                port_available = False
                logger.warning(
                    "Port 8080 is already in use - dashboard may be running in another process"
                )

        if port_available:
            from live_dashboard import app

            def run_dashboard():
                app.run(host="0.0.0.0", port=8080, debug=False)

            dashboard_thread = threading.Thread(target=run_dashboard)
            dashboard_thread.daemon = True
            dashboard_thread.start()
            logger.info("📊 Dashboard running at http://localhost:8080")
        else:
            logger.info("📊 Dashboard already running at http://localhost:8080")

    # Run trading system
    try:
        await system.run()
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        # Force flush any remaining scans before exit
        if hasattr(system, "scan_buffer"):
            await system.scan_buffer.force_flush()
            logger.info(
                f"Total scans logged: {system.scan_buffer.total_scans_logged} "
                f"in {system.scan_buffer.total_batches_sent} batches"
            )

        # Save final state
        logger.info("Final portfolio state:")
        final_stats = system.paper_trader.get_portfolio_stats()
        logger.info(
            f"Balance: ${final_stats['balance']:.2f}, "
            f"Total P&L: ${final_stats['total_pnl']:.2f}, "
            f"Win Rate: {final_stats.get('win_rate', 0):.1f}%"
        )


if __name__ == "__main__":
    asyncio.run(main())
