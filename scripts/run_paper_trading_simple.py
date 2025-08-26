#!/usr/bin/env python3
"""
Market-Aware Paper Trading System with Intelligent Strategy Prioritization
Prioritizes strategies based on market analysis and manages positions intelligently
Version: 2.3.2 - Reduce logging to avoid Railway 500 logs/sec limit
BUILD_ID: 20250826-201500
"""

import asyncio
import os

# Force disable ML and Shadow Testing
os.environ["ML_ENABLED"] = "false"
os.environ["SHADOW_ENABLED"] = "false"

import sys  # noqa: E402
from pathlib import Path  # noqa: E402
from datetime import datetime  # noqa: E402
from typing import Dict, List  # noqa: E402
from loguru import logger  # noqa: E402
import signal as sig_handler  # noqa: E402

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

# Import configuration
from configs.paper_trading_config import PAPER_TRADING_CONFIG  # noqa: E402

from src.data.hybrid_fetcher import HybridDataFetcher  # noqa: E402
from src.trading.simple_paper_trader_v2 import SimplePaperTraderV2  # noqa: E402
from src.config.settings import Settings  # noqa: E402
from src.data.supabase_client import SupabaseClient  # noqa: E402
from src.notifications.paper_trading_notifier import PaperTradingNotifier  # noqa: E402

# Import only what we need from strategies - NO ML
from src.strategies.dca.detector import DCADetector  # noqa: E402
from src.strategies.swing.detector import SwingDetector  # noqa: E402
from src.strategies.channel.detector import ChannelDetector  # noqa: E402
from src.strategies.simple_rules import SimpleRules  # noqa: E402
from src.strategies.regime_detector import RegimeDetector, MarketRegime  # noqa: E402
from src.trading.trade_limiter import TradeLimiter  # noqa: E402


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
        self.paper_trader = SimplePaperTraderV2(
            initial_balance=1000.0,
            max_positions=150,  # Total max positions (50 per strategy × 3 strategies)
            max_positions_per_strategy=50,  # Max 50 positions per strategy
            config_path="configs/paper_trading.json",  # Load all thresholds from config
        )

        # Initialize notifier for system-level alerts
        self.notifier = None
        try:
            self.notifier = PaperTradingNotifier()
            logger.info("✅ Slack notifier initialized")
        except Exception as e:
            logger.warning(f"Could not initialize Slack notifier: {e}")

        # Initialize database
        self.supabase = SupabaseClient()

        # Load configuration from central source
        # Build config from PAPER_TRADING_CONFIG with backward compatibility
        self.config = {
            "ml_enabled": False,  # ALWAYS FALSE
            "shadow_enabled": False,  # ALWAYS FALSE
            "base_position_usd": 50.0,
            "max_open_positions": PAPER_TRADING_CONFIG.get("max_positions", 30),
            # Detection thresholds from central config
            "dca_drop_threshold": PAPER_TRADING_CONFIG["strategies"]["DCA"].get(
                "drop_threshold", -4.0
            ),
            "swing_breakout_threshold": PAPER_TRADING_CONFIG["strategies"]["SWING"].get(
                "breakout_threshold", 1.015
            ),
            "channel_position_threshold": PAPER_TRADING_CONFIG["strategies"][
                "CHANNEL"
            ].get("buy_zone", 0.15),
            # Volume and other thresholds
            "swing_volume_surge": PAPER_TRADING_CONFIG["strategies"]["SWING"].get(
                "volume_surge", 1.5
            ),
            "channel_touches": PAPER_TRADING_CONFIG["strategies"]["CHANNEL"].get(
                "channel_touches", 3
            ),
            # Basic risk management
            "min_confidence": 0.45,  # Lower threshold for rule-based (no ML)
            "scan_interval": 60,  # Scan every minute
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
        logger.info("   BUILD_ID: 20250826-201500 - Reduced logging for Railway")
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
            f"   Channel Buy Zone: {self.config['channel_position_threshold']} "
            f"(touches: {self.config['channel_touches']})"
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
            self.strategy_change_time = datetime.now()
            return

        logger.info(
            f"📊 Market shift detected: {self.last_best_strategy} → {new_best_strategy}"
        )

        # Check how long since strategy changed
        time_since_change = (
            datetime.now() - self.strategy_change_time
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
                datetime.now() - self.position_timestamps.get(symbol, datetime.now())
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
        self.strategy_change_time = datetime.now()

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
                    market_price=current_prices[symbol],
                    reason="POSITION_LIMIT_CLEANUP",
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
                        # Reduced logging to avoid Railway 500 logs/sec limit
                        pass
                        # logger.debug(f"📊 DCA Signal: {symbol} - drop {dca_signal.get('drop_pct', 0):.1f}%")
                        # await self.log_scan(symbol, "DCA", "BUY", "Signal detected",
                        #     confidence=dca_signal["confidence"],
                        #     metadata={"drop_pct": dca_signal.get("drop_pct", 0)},
                        #     market_data=data)
                    else:
                        # Skip logging for NO signal to reduce log volume
                        pass
                        # await self.log_scan(symbol, "DCA", "SKIP", "No signal", confidence=0.0, market_data=data)

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
                        # Reduced logging to avoid Railway 500 logs/sec limit
                        pass
                        # logger.debug(
                        #     f"📊 Swing Signal: {symbol} - breakout {swing_signal.get('breakout_pct', 0):.1f}%"
                        # )
                        # await self.log_scan(symbol, "SWING", "BUY", "Signal detected",
                        #     confidence=swing_signal["confidence"],
                        #     metadata={"breakout_pct": swing_signal.get("breakout_pct", 0)},
                        #     market_data=data)
                    else:
                        # Skip logging for NO signal to reduce log volume
                        pass
                        # await self.log_scan(symbol, "SWING", "SKIP", "No signal", confidence=0.0, market_data=data)

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
                        # Reduced logging to avoid Railway 500 logs/sec limit
                        pass
                        # logger.debug(f"📊 Channel Signal: {symbol} - position {channel_signal.get('position', 0):.2f}")
                        # await self.log_scan(symbol, "CHANNEL", "BUY", "Signal detected",
                        #     confidence=channel_signal["confidence"],
                        #     metadata={"position": channel_signal.get("position", 0)},
                        #     market_data=data)
                    else:
                        # Skip logging for NO signal to reduce log volume
                        pass
                        # await self.log_scan(symbol, "CHANNEL", "SKIP", "No signal", confidence=0.0, market_data=data)

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

            if trading_signal["confidence"] >= self.config["min_confidence"]:
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
            logger.info("No trades executed despite signals (confidence/limits)")
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
            from datetime import datetime, timezone

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

            # Insert to scan_history
            self.supabase.client.table("scan_history").insert(scan_data).execute()

        except Exception as e:
            # Don't let logging errors stop trading
            logger.error(f"Could not log scan for {symbol}: {e}")
            logger.debug(f"Full scan data: {scan_data}")

    async def execute_trade(self, trading_signal: Dict) -> bool:
        """Execute a trade based on signal"""
        try:
            symbol = trading_signal["symbol"]
            strategy = trading_signal.get("strategy", "unknown")

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
                self.position_timestamps[symbol] = datetime.now()

                # Send Slack notification
                if self.notifier:
                    try:
                        await self.notifier.notify_position_opened(
                            symbol=symbol,
                            strategy=strategy,
                            entry_price=trading_signal["current_price"],
                            position_size=position_size,
                        )
                    except Exception as e:
                        logger.debug(f"Could not send notification: {e}")

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
                    f"P&L: ${trade.pnl:.2f}"
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
                            "timestamp": datetime.now().isoformat(),
                            "symbol": trade.symbol,
                            "strategy_name": trade.strategy,
                            "action": "CLOSE",
                            "price": trade.exit_price,
                            "quantity": trade.amount,
                            "position_size": trade.entry_value,
                            "pnl": trade.pnl,
                            "exit_reason": trade.exit_reason,
                            "ml_confidence": None,  # No ML
                            "hold_duration_hours": trade.hold_duration_hours,
                        }
                    ).execute()
                except Exception as e:
                    logger.debug(f"Could not log trade: {e}")

                # Send notification
                if self.notifier:
                    await self.notifier.send_trade_closed(
                        symbol=trade.symbol,
                        strategy=trade.strategy,
                        pnl=trade.pnl,
                        exit_reason=trade.exit_reason,
                    )

    async def run(self):
        """Main trading loop"""
        logger.info("Starting simplified paper trading loop...")

        while not self.shutdown:
            try:
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
