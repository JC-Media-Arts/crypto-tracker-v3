#!/usr/bin/env python3
"""
Main Integration Script for Paper Trading
Connects all components: Data → Strategies → ML → Manager → Hummingbot
Based on MASTER_PLAN.md architecture
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
import aiohttp
from loguru import logger

sys.path.append(".")

from src.data.supabase_client import SupabaseClient
from src.strategies.manager import StrategyManager
from src.trading.trade_logger import TradeLogger
from src.config.settings import Settings

# Configure logging
logger.add("logs/paper_trading.log", rotation="10 MB", level="INFO")
logger.add("logs/paper_trading_debug.log", rotation="10 MB", level="DEBUG")


class PaperTradingSystem:
    """
    Main integration class that orchestrates the entire paper trading system
    """

    def __init__(self):
        logger.info("=" * 60)
        logger.info("CRYPTO ML PAPER TRADING SYSTEM")
        logger.info("Initializing all components...")
        logger.info("=" * 60)

        self.settings = Settings()
        self.supabase = SupabaseClient()

        # Initialize trade logger for outcome tracking
        self.trade_logger = TradeLogger(self.supabase.client)

        # Trading configuration from MASTER_PLAN.md
        self.config = {
            "total_capital": 1000,  # $1000 paper trading
            "dca_allocation": 0.4,  # 40% for DCA
            "swing_allocation": 0.3,  # 30% for Swing
            "channel_allocation": 0.3,  # 30% for Channel
            "reserve": 0.2,  # 20% reserve (built into allocations)
            "min_confidence": 0.60,
            "symbols": [
                # Tier 1: Core (20 coins)
                "BTC",
                "ETH",
                "SOL",
                "BNB",
                "XRP",
                "ADA",
                "AVAX",
                "DOGE",
                "DOT",
                "POL",
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
                # Tier 2: DeFi/Layer 2 (20 coins)
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
                # Tier 3: Trending/Memecoins (20 coins)
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
                # Tier 4: Solid Mid-Caps (39 coins - excluding BLUR which is in Tier 2)
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
            ],
            "dca_config": {
                "drop_threshold": -5.0,
                "min_volume_ratio": 1.5,
                "rsi_oversold": 30,
                "grid_levels": 5,
                "grid_spacing": 0.01,
                "take_profit": 10.0,
                "stop_loss": -8.0,
                "time_exit": 72,
            },
            "swing_config": {
                "breakout_threshold": 0.03,  # 3% from MASTER_PLAN
                "volume_surge": 2.0,
                "rsi_bullish_min": 60,
                "take_profit": 15.0,
                "stop_loss": -5.0,
                "trailing_stop": 7.0,
                "time_exit": 48,
            },
            "scan_interval": 300,  # 5 minutes
            "hummingbot_api_url": "http://localhost:8000",
        }

        # Initialize Strategy Manager with Supabase client for scan logging
        self.strategy_manager = StrategyManager(self.config, self.supabase.client)

        # Hummingbot API session
        self.api_session = None

        # Performance tracking
        self.start_time = datetime.now()
        self.total_trades = 0
        self.total_pnl = 0.0

        logger.info("System initialized successfully")
        logger.info(f"Monitoring {len(self.config['symbols'])} symbols")
        logger.info(f"Capital: ${self.config['total_capital']}")
        logger.info(f"Scan interval: {self.config['scan_interval']} seconds")

    async def fetch_market_data(self) -> Dict:
        """
        Fetch latest market data from Supabase
        """
        try:
            market_data = {}

            # Process symbols in batches to avoid timeouts
            batch_size = 10
            symbols = self.config["symbols"]

            for i in range(0, len(symbols), batch_size):
                batch = symbols[i : i + batch_size]

                for symbol in batch:
                    try:
                        # Fetch latest OHLC data for each symbol
                        query = (
                            self.supabase.client.table("ohlc_data")
                            .select("*")
                            .eq("symbol", symbol)
                            .order("timestamp", desc=True)
                            .limit(100)
                        )

                        response = query.execute()

                        if response.data:
                            # Calculate indicators
                            data = self._calculate_indicators(response.data)
                            market_data[symbol] = data
                    except Exception as e:
                        logger.warning(f"Error fetching data for {symbol}: {e}")
                        continue

            logger.debug(f"Fetched data for {len(market_data)} symbols")
            return market_data

        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
            return {}

    async def _analyze_near_misses(self, market_data: Dict) -> List[Dict]:
        """
        Analyze near misses - opportunities that almost triggered
        """
        near_misses = []

        try:
            for symbol, data in market_data.items():
                if not data or len(data) < 20:
                    continue

                latest = data[-1] if isinstance(data, list) else data
                current_price = latest.get("close", 0)

                # Check DCA near miss
                lookback_bars = min(16, len(data)) if isinstance(data, list) else 1
                if isinstance(data, list):
                    recent_data = data[-lookback_bars:]
                    high_4h = max(bar.get("high", 0) for bar in recent_data)
                else:
                    high_4h = latest.get("high", 0)

                drop_pct = (
                    ((current_price - high_4h) / high_4h) * 100 if high_4h > 0 else 0
                )

                # Near miss if drop is between -2% and -5%
                if -5.0 < drop_pct <= -2.0:
                    near_misses.append(
                        {
                            "symbol": symbol,
                            "strategy": "DCA",
                            "reason": f"Drop {drop_pct:.1f}% (need -5%)",
                            "distance": abs(drop_pct + 5.0),
                        }
                    )

                # Check Swing near miss (simplified)
                if isinstance(data, list) and len(data) >= 20:
                    highs = [bar.get("high", 0) for bar in data[-20:]]
                    period_high = max(highs[:-1])
                    breakout_pct = (
                        ((current_price - period_high) / period_high) * 100
                        if period_high > 0
                        else 0
                    )

                    # Near miss if breakout is between 0.5% and 2%
                    if 0.5 <= breakout_pct < 2.0:
                        near_misses.append(
                            {
                                "symbol": symbol,
                                "strategy": "Swing",
                                "reason": f"Breakout {breakout_pct:.1f}% (need 2%)",
                                "distance": abs(breakout_pct - 2.0),
                            }
                        )

            # Sort by distance (closest first)
            near_misses.sort(key=lambda x: x["distance"])

        except Exception as e:
            logger.debug(f"Error analyzing near misses: {e}")

        return near_misses[:5]  # Return top 5

    def _calculate_indicators(self, ohlc_data: List[Dict]) -> Dict:
        """
        Calculate technical indicators from OHLC data
        """
        if not ohlc_data:
            return {}

        latest = ohlc_data[0]

        # Calculate basic metrics
        prices = [d["close"] for d in ohlc_data]
        volumes = [d["volume"] for d in ohlc_data if d.get("volume")]

        # Price changes
        price_24h_ago = (
            prices[min(96, len(prices) - 1)] if len(prices) > 96 else prices[-1]
        )
        price_change_24h = (
            ((latest["close"] - price_24h_ago) / price_24h_ago * 100)
            if price_24h_ago
            else 0
        )

        # Volume ratio
        avg_volume = sum(volumes) / len(volumes) if volumes else 1
        current_volume = latest.get("volume", avg_volume)
        volume_ratio = current_volume / avg_volume if avg_volume else 1

        # Simple RSI calculation (simplified)
        gains = []
        losses = []
        for i in range(1, min(14, len(prices))):
            change = prices[i - 1] - prices[i]
            if change > 0:
                gains.append(change)
            else:
                losses.append(abs(change))

        avg_gain = sum(gains) / 14 if gains else 0
        avg_loss = sum(losses) / 14 if losses else 0
        rs = avg_gain / avg_loss if avg_loss else 100
        rsi = 100 - (100 / (1 + rs))

        # Moving averages
        sma_20 = sum(prices[:20]) / 20 if len(prices) >= 20 else latest["close"]
        sma_50 = sum(prices[:50]) / 50 if len(prices) >= 50 else latest["close"]
        sma_200 = sum(prices[:200]) / 200 if len(prices) >= 200 else latest["close"]

        return {
            "symbol": latest["symbol"],
            "current_price": latest["close"],
            "price_change_24h": price_change_24h,
            "rsi": rsi,
            "volume_ratio": volume_ratio,
            "high_24h": max(d["high"] for d in ohlc_data[:96])
            if len(ohlc_data) > 96
            else latest["high"],
            "low_24h": min(d["low"] for d in ohlc_data[:96])
            if len(ohlc_data) > 96
            else latest["low"],
            "sma_20": sma_20,
            "sma_50": sma_50,
            "sma_200": sma_200,
            "support_level": min(d["low"] for d in ohlc_data[:20])
            if len(ohlc_data) > 20
            else latest["low"],
            "resistance_level": max(d["high"] for d in ohlc_data[:20])
            if len(ohlc_data) > 20
            else latest["high"],
            "timestamp": latest["timestamp"],
        }

    async def check_hummingbot_connection(self) -> bool:
        """
        Check if Hummingbot API is accessible
        """
        try:
            if not self.api_session:
                self.api_session = aiohttp.ClientSession()

            async with self.api_session.get(
                f"{self.config['hummingbot_api_url']}/"
            ) as response:
                if response.status == 200:
                    logger.info("✅ Hummingbot API is accessible")
                    return True
                else:
                    logger.warning(
                        f"⚠️ Hummingbot API returned status {response.status}"
                    )
                    return False

        except Exception as e:
            logger.error(f"❌ Cannot connect to Hummingbot API: {e}")
            return False

    async def execute_via_hummingbot(self, signal) -> bool:
        """
        Execute trade through Hummingbot API
        """
        try:
            # This would be the actual API call to Hummingbot
            # For now, we'll simulate it
            logger.info(
                f"📤 Sending to Hummingbot: {signal.strategy_type.value} "
                f"for {signal.symbol} @ ${signal.setup_data.get('current_price', 0):.2f}"
            )

            # In production, this would be:
            # async with self.api_session.post(
            #     f"{self.config['hummingbot_api_url']}/strategies/start",
            #     json={
            #         'strategy': 'pure_market_making',
            #         'symbol': signal.symbol,
            #         'order_amount': signal.setup_data['position_size'],
            #         ...
            #     }
            # ) as response:
            #     return response.status == 200

            # Simulate success
            await asyncio.sleep(0.5)
            return True

        except Exception as e:
            logger.error(f"Error executing via Hummingbot: {e}")
            return False

    async def monitor_positions(self):
        """
        Monitor open positions and handle exits
        """
        while True:
            try:
                positions = self.strategy_manager.active_positions

                if positions:
                    logger.info(f"📊 Monitoring {len(positions)} open positions")

                    for symbol, signal in positions.items():
                        # Check exit conditions
                        # In production, this would check actual P&L from Hummingbot

                        # Simulate some exits for testing
                        if datetime.now() > signal.timestamp + timedelta(hours=1):
                            # Simulate a win/loss
                            is_win = signal.confidence > 0.65
                            pnl = 50 if is_win else -20

                            self.strategy_manager.update_performance(
                                symbol, pnl, is_win
                            )
                            self.total_pnl += pnl
                            self.total_trades += 1

                            logger.info(
                                f"📈 Position closed: {symbol} "
                                f"{'WIN' if is_win else 'LOSS'} ${pnl:+.2f}"
                            )

                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Error monitoring positions: {e}")
                await asyncio.sleep(60)

    async def run_trading_loop(self):
        """
        Main trading loop
        """
        logger.info("🚀 Starting main trading loop")

        while True:
            try:
                loop_start = datetime.now()

                # 1. Fetch market data
                logger.info("📡 Fetching market data...")
                market_data = await self.fetch_market_data()

                if not market_data:
                    logger.warning("No market data available, skipping cycle")
                    await asyncio.sleep(self.config["scan_interval"])
                    continue

                # 2. Scan for opportunities
                logger.info("🔍 Scanning for opportunities...")
                try:
                    signals = await self.strategy_manager.scan_for_opportunities(
                        market_data
                    )

                    # Track near misses for visibility
                    self.last_near_misses = await self._analyze_near_misses(market_data)

                except Exception as scan_error:
                    logger.error(f"Error in scan_for_opportunities: {scan_error}")
                    logger.error(f"Error type: {type(scan_error)}")
                    import traceback

                    logger.error(f"Traceback: {traceback.format_exc()}")
                    signals = []
                    self.last_near_misses = []

                # 3. Resolve conflicts
                if signals:
                    logger.info(f"⚔️ Resolving conflicts for {len(signals)} signals...")
                    resolved = self.strategy_manager.resolve_conflicts(signals)

                    # 4. Execute signals
                    if resolved:
                        logger.info(f"💼 Executing {len(resolved)} signals...")
                        results = await self.strategy_manager.execute_signals(resolved)

                        # 5. Send to Hummingbot
                        for signal in results["executed"]:
                            success = await self.execute_via_hummingbot(signal)
                            if success:
                                logger.info(
                                    f"✅ {signal.symbol} order sent to Hummingbot"
                                )
                            else:
                                logger.error(
                                    f"❌ Failed to send {signal.symbol} to Hummingbot"
                                )

                # 6. Display status
                self._display_status()

                # Wait for next cycle
                elapsed = (datetime.now() - loop_start).total_seconds()
                wait_time = max(0, self.config["scan_interval"] - elapsed)

                if wait_time > 0:
                    logger.info(f"⏰ Next scan in {wait_time:.0f} seconds...")
                    await asyncio.sleep(wait_time)

            except KeyboardInterrupt:
                logger.info("🛑 Shutdown requested")
                break
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(30)  # Wait before retry

    def _display_status(self):
        """
        Display current system status
        """
        status = self.strategy_manager.get_status()
        runtime = datetime.now() - self.start_time

        logger.info("=" * 50)
        logger.info("📊 SYSTEM STATUS")
        logger.info(f"Runtime: {runtime}")
        logger.info(f"Active Positions: {status['active_positions']}")
        logger.info(f"Total Trades: {self.total_trades}")
        logger.info(f"Total P&L: ${self.total_pnl:+.2f}")

        logger.info("💰 Capital Status:")
        cap = status["capital_allocation"]
        logger.info(
            f"  DCA: ${cap['dca_used']:.0f} used, ${cap['dca_available']:.0f} available"
        )
        logger.info(
            f"  Swing: ${cap['swing_used']:.0f} used, ${cap['swing_available']:.0f} available"
        )
        logger.info(
            f"  Channel: ${cap.get('channel_used', 0):.0f} used, ${cap.get('channel_available', self.config['total_capital'] * self.config.get('channel_allocation', 0.3)):.0f} available"
        )

        logger.info("📈 Performance:")
        for strategy in ["dca", "swing", "channel"]:
            perf = status["performance"].get(strategy, {"win_rate": 0, "total_pnl": 0})
            logger.info(
                f"  {strategy.upper()}: Win Rate {perf['win_rate']:.1%}, P&L ${perf['total_pnl']:+.2f}"
            )

        # Show near misses
        if hasattr(self, "last_near_misses") and self.last_near_misses:
            logger.info("🎯 Near Misses (Almost Triggered):")
            for miss in self.last_near_misses[:3]:  # Show top 3
                logger.info(
                    f"  {miss['symbol']} - {miss['strategy']} - {miss['reason']}"
                )

        logger.info("=" * 50)

    async def shutdown(self):
        """
        Graceful shutdown
        """
        logger.info("Shutting down paper trading system...")

        # Close API session
        if self.api_session:
            await self.api_session.close()

        # Final status
        self._display_status()

        logger.info("✅ Shutdown complete")

    async def main(self):
        """
        Main entry point
        """
        try:
            # Check Hummingbot connection
            hummingbot_ok = await self.check_hummingbot_connection()

            if not hummingbot_ok:
                logger.warning(
                    "⚠️ Hummingbot API not available - running in simulation mode"
                )

            # Start monitoring task
            monitor_task = asyncio.create_task(self.monitor_positions())

            # Run main trading loop
            await self.run_trading_loop()

            # Cancel monitoring
            monitor_task.cancel()

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            await self.shutdown()


async def run():
    """Run the paper trading system"""
    system = PaperTradingSystem()
    await system.main()


if __name__ == "__main__":
    logger.info("Starting Crypto ML Paper Trading System")
    logger.info("Press Ctrl+C to stop")

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("System stopped by user")
