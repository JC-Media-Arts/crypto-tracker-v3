#!/usr/bin/env python3
"""
Simplified Paper Trading System - NO ML, NO Shadow Testing
Pure rule-based trading for complete independence
Designed to run 24/7 on Railway without any ML dependencies
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from loguru import logger
import signal as sig_handler

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

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
            initial_balance=1000.0, max_positions=50
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

        # Simple rule-based configuration (NO ML)
        self.config = {
            "ml_enabled": False,  # ALWAYS FALSE
            "shadow_enabled": False,  # ALWAYS FALSE
            "base_position_usd": 50.0,
            "max_open_positions": 30,
            # Simplified thresholds (30% lower than original for more signals)
            "dca_drop_threshold": -3.5,  # Was -5.0
            "swing_breakout_threshold": 2.1,  # Was 3.0
            "channel_position_threshold": 0.35,
            # Basic risk management
            "min_confidence": 0.45,  # Lower threshold for rule-based
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

        # Track active positions
        self.active_positions = self.paper_trader.positions

        # Shutdown flag
        self.shutdown = False

        logger.info("=" * 80)
        logger.info("🚀 SIMPLIFIED PAPER TRADING SYSTEM")
        logger.info("   Mode: Rule-Based Only (NO ML, NO Shadow)")
        logger.info(f"   Balance: ${self.paper_trader.balance:.2f}")
        logger.info(f"   Position Size: ${self.config['position_size']}")
        logger.info(f"   Max Positions: {self.paper_trader.max_positions}")
        logger.info(f"   DCA Threshold: {self.config['dca_drop_threshold']}%")
        logger.info(f"   Swing Threshold: {self.config['swing_breakout_threshold']}%")
        logger.info(
            f"   Channel Threshold: {self.config['channel_position_threshold']}"
        )
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

    async def scan_for_opportunities(self):
        """
        Scan for trading opportunities using ONLY rule-based strategies
        NO ML predictions, NO shadow logging
        """
        symbols = self.get_symbols()

        # Skip symbols we already have positions in
        symbols_with_positions = set(self.active_positions.keys())
        available_symbols = [s for s in symbols if s not in symbols_with_positions]

        if not available_symbols:
            logger.info("All symbols have active positions")
            return

        logger.info(f"Scanning {len(available_symbols)} symbols for opportunities...")

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

        # Fetch BTC price for correlations
        if "BTC" in market_data:
            btc_data = market_data["BTC"]
            if btc_data and len(btc_data) > 0:
                self._btc_price = btc_data[-1]["close"]
            else:
                self._btc_price = 0.0
        else:
            self._btc_price = 0.0

        # Scan each strategy with SIMPLE RULES ONLY
        signals = []

        for symbol, data in market_data.items():
            try:
                current_price = data[-1]["close"] if data else 0

                # Check each strategy type and log ALL scans
                # DCA
                dca_signal = self.simple_rules.check_dca_setup(symbol, data)
                if dca_signal and dca_signal.get("signal"):
                    dca_signal["should_trade"] = True
                    dca_signal["strategy"] = "DCA"
                    # Ensure we have current_price in all signals
                    if "current_price" not in dca_signal:
                        dca_signal["current_price"] = dca_signal.get(
                            "price", current_price
                        )
                    signals.append(dca_signal)
                    logger.info(
                        f"📊 DCA Signal: {symbol} - drop {dca_signal.get('drop_pct', 0):.1f}% "
                        f"(confidence: {dca_signal['confidence']:.2f})"
                    )
                    # Log positive scan
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
                    # Log negative scan
                    await self.log_scan(
                        symbol,
                        "DCA",
                        "SKIP",
                        "No signal",
                        confidence=0.0,
                        market_data=data,
                    )

                # Swing
                swing_signal = self.simple_rules.check_swing_setup(symbol, data)
                if swing_signal and swing_signal.get("signal"):
                    swing_signal["should_trade"] = True
                    swing_signal["strategy"] = "SWING"
                    # Ensure we have current_price
                    if "current_price" not in swing_signal:
                        swing_signal["current_price"] = swing_signal.get(
                            "price", current_price
                        )
                    signals.append(swing_signal)
                    logger.info(
                        f"📊 Swing Signal: {symbol} - breakout {swing_signal.get('breakout_pct', 0):.1f}% "
                        f"(confidence: {swing_signal['confidence']:.2f})"
                    )
                    # Log positive scan
                    await self.log_scan(
                        symbol,
                        "SWING",
                        "BUY",
                        "Signal detected",
                        confidence=swing_signal["confidence"],
                        metadata={"breakout_pct": swing_signal.get("breakout_pct", 0)},
                        market_data=data,
                    )
                else:
                    # Log negative scan
                    await self.log_scan(
                        symbol,
                        "SWING",
                        "SKIP",
                        "No signal",
                        confidence=0.0,
                        market_data=data,
                    )

                # Channel
                channel_signal = self.simple_rules.check_channel_setup(symbol, data)
                if channel_signal and channel_signal.get("signal"):
                    channel_signal["should_trade"] = True
                    channel_signal["strategy"] = "CHANNEL"
                    # Ensure we have current_price
                    if "current_price" not in channel_signal:
                        channel_signal["current_price"] = channel_signal.get(
                            "price", current_price
                        )
                    signals.append(channel_signal)
                    logger.info(
                        f"📊 Channel Signal: {symbol} - position {channel_signal.get('position', 0):.2f} "
                        f"(confidence: {channel_signal['confidence']:.2f})"
                    )
                    # Log positive scan
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
                    # Log negative scan
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

        # Sort by confidence and take best signals
        signals.sort(key=lambda x: x.get("confidence", 0), reverse=True)

        # Execute top signals (respecting position limits)
        available_slots = self.paper_trader.max_positions - len(self.active_positions)
        signals_to_take = signals[:available_slots]

        for trading_signal in signals_to_take:
            if trading_signal["confidence"] >= self.config["min_confidence"]:
                await self.execute_trade(trading_signal)

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

    async def execute_trade(self, trading_signal: Dict):
        """Execute a trade based on signal"""
        try:
            symbol = trading_signal["symbol"]
            strategy = trading_signal.get("strategy", "unknown")
            confidence = trading_signal.get("confidence", 0.5)

            # Calculate position size
            position_size = self.config["position_size"]

            # Adjust for regime if needed
            if hasattr(self, "regime_detector"):
                regime = self.regime_detector.get_market_regime()
                if regime == MarketRegime.CAUTION:
                    position_size *= 0.5

            # Execute trade (using async method)
            success = await self.paper_trader.open_position(
                symbol=symbol,
                usd_amount=position_size,
                market_price=trading_signal["current_price"],
                strategy=strategy,
            )

            if success:
                logger.info(
                    f"✅ Opened {strategy} position: {symbol} @ ${trading_signal['current_price']:.4f}"
                )

                # Send Slack notification
                if self.notifier:
                    try:
                        await self.notifier.notify_position_opened(
                            symbol=symbol,
                            strategy=strategy,
                            entry_price=trading_signal["current_price"],
                            position_size=position_size,
                            confidence=confidence,
                        )
                    except Exception as e:
                        logger.debug(f"Could not send notification: {e}")

        except Exception as e:
            logger.error(f"Error executing trade for {trading_signal['symbol']}: {e}")

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
