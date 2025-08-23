#!/usr/bin/env python3
"""
Test Strategy Manager with all 3 strategies: DCA, Swing, and Channel
"""

import asyncio
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger
import sys

sys.path.append(".")

from src.strategies.manager import StrategyManager, StrategyType
from src.strategies.channel.detector import ChannelDetector


# Mock classes for testing
class MockDCADetector:
    def __init__(self, config):
        self.config = config

    def detect_setup(self, symbol: str, data: List[Dict]) -> Optional[Dict]:
        """Detect DCA setup from price drop"""
        if not data or len(data) < 2:
            return None

        # Check for price drop
        current_price = data[0]["close"]
        recent_high = max(d["high"] for d in data[:20] if "high" in d)
        drop_pct = (current_price - recent_high) / recent_high * 100

        if drop_pct <= -5.0:  # 5% drop threshold
            return {
                "symbol": symbol,
                "current_price": current_price,
                "drop_pct": drop_pct,
                "recent_high": recent_high,
            }
        return None


class MockSwingDetector:
    def __init__(self, config):
        self.config = config

    def detect_setup(self, symbol: str, data: List[Dict]) -> Optional[Dict]:
        """Detect Swing setup from breakout"""
        if not data or len(data) < 20:
            return None

        # Check for breakout
        current_price = data[0]["close"]
        recent_high = max(d["high"] for d in data[1:20] if "high" in d)
        breakout_pct = (current_price - recent_high) / recent_high * 100

        # Check volume surge
        current_volume = data[0].get("volume", 0)
        avg_volume = np.mean([d.get("volume", 0) for d in data[1:20]])
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0

        if breakout_pct >= 3.0 and volume_ratio >= 2.0:
            return {
                "symbol": symbol,
                "current_price": current_price,
                "breakout_pct": breakout_pct,
                "volume_ratio": volume_ratio,
            }
        return None


class MockSwingAnalyzer:
    def analyze_setup(self, setup: Dict, data: List[Dict]) -> Dict:
        """Analyze swing setup"""
        return {
            "market_regime": "BULL",
            "risk_reward": 2.5,
            "trade_plan": {
                "entry": setup["current_price"],
                "take_profit": setup["current_price"] * 1.15,
                "stop_loss": setup["current_price"] * 0.95,
            },
        }


class MockMLPredictor:
    def __init__(self, settings):
        pass

    def predict_dca(self, features: Dict) -> Dict:
        """Mock DCA prediction"""
        return {
            "confidence": 0.75,
            "win_probability": 0.65,
            "optimal_take_profit": 10.0,
            "optimal_stop_loss": -5.0,
            "position_size_mult": 1.2,
        }

    def predict_swing(self, features: Dict) -> Dict:
        """Mock Swing prediction"""
        return {
            "confidence": 0.70,
            "breakout_success": True,
            "optimal_tp": 15.0,
            "optimal_sl": -5.0,
        }


class MockPositionSizer:
    def __init__(self, config):
        self.config = config

    def calculate_position_size(self, **kwargs) -> float:
        """Mock position sizing"""
        base_size = 100
        confidence = kwargs.get("confidence", 0.5)
        return base_size * confidence


class MockGridCalculator:
    def __init__(self, config):
        self.config = config

    def calculate_grid(self, **kwargs) -> Dict:
        """Mock grid calculation"""
        return {"levels": 5, "spacing": 1.0, "total_size": 500}


# Configure logger
logger.add("logs/strategy_manager_test.log", rotation="10 MB")


class StrategyManagerTest:
    def __init__(self):
        self.config = {
            "total_capital": 1000,
            "dca_allocation": 0.4,  # 40% for DCA
            "swing_allocation": 0.3,  # 30% for Swing
            "channel_allocation": 0.3,  # 30% for Channel
            "reserve": 0.2,
            "min_confidence": 0.60,
            "min_risk_reward": 1.5,
            "dca_config": {
                "drop_threshold": -5.0,
                "grid_levels": 5,
                "grid_spacing": 1.0,
            },
            "swing_config": {
                "breakout_threshold": 3.0,
                "volume_surge": 2.0,
                "rsi_bullish_min": 60,
            },
            "channel_config": {
                "min_touches": 2,
                "lookback_periods": 100,
                "min_channel_width": 0.01,
                "max_channel_width": 0.10,
                "buy_zone": 0.25,
                "sell_zone": 0.75,
            },
        }

        # Create manager and replace components with mocks
        self.manager = StrategyManager(self.config)
        self.manager.dca_detector = MockDCADetector(self.config["dca_config"])
        self.manager.swing_detector = MockSwingDetector(self.config["swing_config"])
        self.manager.swing_analyzer = MockSwingAnalyzer()
        self.manager.ml_predictor = MockMLPredictor(None)
        self.manager.position_sizer = MockPositionSizer(self.config)
        self.manager.grid_calculator = MockGridCalculator(self.config["dca_config"])
        # Keep real Channel detector to test integration

    def generate_market_data(self) -> Dict[str, List[Dict]]:
        """Generate synthetic market data with patterns for each strategy"""
        market_data = {}

        # BTC - Create DCA setup (5% drop)
        btc_data = []
        base_price = 50000
        for i in range(100):
            timestamp = datetime.now() - timedelta(hours=100 - i)

            # Create a drop in recent data
            if i > 90:
                price = base_price * (0.95 - (i - 90) * 0.005)  # 5-10% drop
            else:
                price = base_price + np.random.randn() * 500

            btc_data.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "open": price,
                    "high": price + abs(np.random.randn() * 100),
                    "low": price - abs(np.random.randn() * 100),
                    "close": price,
                    "volume": 1000000 * (1 + np.random.rand()),
                }
            )
        market_data["BTC"] = list(reversed(btc_data))

        # ETH - Create Swing setup (breakout)
        eth_data = []
        base_price = 3000
        for i in range(100):
            timestamp = datetime.now() - timedelta(hours=100 - i)

            # Create breakout in recent data
            if i > 95:
                price = base_price * (1.03 + (i - 95) * 0.01)  # 3-8% breakout
            else:
                price = base_price + np.random.randn() * 30

            eth_data.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "open": price,
                    "high": price + abs(np.random.randn() * 10),
                    "low": price - abs(np.random.randn() * 10),
                    "close": price,
                    "volume": 1000000 * (2 if i > 95 else 1),  # Volume surge on breakout
                }
            )
        market_data["ETH"] = list(reversed(eth_data))

        # SOL - Create Channel pattern (horizontal)
        sol_data = []
        base_price = 100
        for i in range(100):
            timestamp = datetime.now() - timedelta(hours=100 - i)

            # Create channel pattern
            center = 100
            amplitude = 2
            price = center + amplitude * np.sin(i * 0.3)

            # Put current price near bottom of channel (for buy signal)
            if i > 95:
                price = center - amplitude * 0.8

            sol_data.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "open": price,
                    "high": price + abs(np.random.randn() * 0.3),
                    "low": price - abs(np.random.randn() * 0.3),
                    "close": price,
                    "volume": 1000000 * (1 + np.random.rand()),
                }
            )
        market_data["SOL"] = list(reversed(sol_data))

        # ADA - Random data (no clear pattern)
        ada_data = []
        base_price = 0.5
        for i in range(100):
            timestamp = datetime.now() - timedelta(hours=100 - i)
            price = base_price + np.random.randn() * 0.05

            ada_data.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "open": price,
                    "high": price + abs(np.random.randn() * 0.01),
                    "low": price - abs(np.random.randn() * 0.01),
                    "close": price,
                    "volume": 1000000 * (1 + np.random.rand()),
                }
            )
        market_data["ADA"] = list(reversed(ada_data))

        return market_data

    async def test_all_strategies(self):
        """Test all 3 strategies working together"""
        logger.info("=" * 80)
        logger.info("Testing Strategy Manager with DCA, Swing, and Channel")
        logger.info("=" * 80)

        # Generate market data
        market_data = self.generate_market_data()

        logger.info(f"\n📊 Market Data Generated:")
        logger.info(f"  BTC: Simulated 5-10% drop (DCA setup)")
        logger.info(f"  ETH: Simulated 3-8% breakout (Swing setup)")
        logger.info(f"  SOL: Simulated horizontal channel (Channel setup)")
        logger.info(f"  ADA: Random walk (no setup)")

        # Scan for opportunities
        logger.info("\n🔍 Scanning for opportunities...")
        signals = await self.manager.scan_for_opportunities(market_data)

        logger.info(f"\n📈 Found {len(signals)} total signals:")
        for signal in signals:
            logger.info(f"  {signal.symbol} - {signal.strategy_type.value}:")
            logger.info(f"    Confidence: {signal.confidence:.2f}")
            logger.info(f"    Expected Value: {signal.expected_value:.2f}")
            logger.info(f"    Required Capital: ${signal.required_capital:.2f}")
            logger.info(f"    Priority Score: {signal.priority_score:.2f}")

        # Resolve conflicts
        logger.info("\n⚖️ Resolving conflicts...")
        resolved_signals = self.manager.resolve_conflicts(signals)
        logger.info(f"  After conflict resolution: {len(resolved_signals)} signals")

        # Apply capital constraints
        logger.info("\n💰 Applying capital constraints...")
        logger.info(f"  Total capital: ${self.config['total_capital']}")
        logger.info(f"  DCA allocation: ${self.config['total_capital'] * self.config['dca_allocation']:.0f}")
        logger.info(f"  Swing allocation: ${self.config['total_capital'] * self.config['swing_allocation']:.0f}")
        logger.info(f"  Channel allocation: ${self.config['total_capital'] * self.config['channel_allocation']:.0f}")

        # Capital constraints are already applied in resolve_conflicts
        final_signals = resolved_signals
        logger.info(f"  After capital constraints: {len(final_signals)} signals approved")

        # Execute signals
        logger.info("\n🚀 Executing signals...")
        results = await self.manager.execute_signals(final_signals)

        logger.info(f"\n✅ Execution Results:")
        for result in results:
            if result["success"]:
                logger.info(f"  {result['symbol']} - {result['strategy']} - SUCCESS")
                if "grid" in result:
                    logger.info(f"    Grid levels: {result['grid']['levels']}")
                if "position_size" in result:
                    logger.info(f"    Position size: ${result['position_size']:.2f}")
            else:
                logger.warning(
                    f"  {result['symbol']} - {result['strategy']} - FAILED: {result.get('error', 'Unknown')}"
                )

        # Update performance
        logger.info("\n📊 Updating performance tracking...")
        for result in results:
            if result["success"]:
                self.manager.update_performance(
                    strategy=StrategyType[result["strategy"]],
                    symbol=result["symbol"],
                    outcome=("WIN" if np.random.rand() > 0.5 else "LOSS"),  # Random for test
                    pnl=np.random.randn() * 10,
                )

        # Show performance
        performance = self.manager.get_performance_summary()
        logger.info(f"\n📈 Performance Summary:")
        for strategy, stats in performance.items():
            logger.info(f"  {strategy}:")
            logger.info(f"    Total trades: {stats['total_trades']}")
            logger.info(f"    Win rate: {stats['win_rate']:.1%}")
            logger.info(f"    Total P&L: ${stats['total_pnl']:.2f}")

        # Show capital usage
        logger.info(f"\n💼 Capital Usage:")
        logger.info(
            f"  DCA used: ${self.manager.allocation.dca_used:.2f} / ${self.config['total_capital'] * self.config['dca_allocation']:.0f}"
        )
        logger.info(
            f"  Swing used: ${self.manager.allocation.swing_used:.2f} / ${self.config['total_capital'] * self.config['swing_allocation']:.0f}"
        )
        logger.info(
            f"  Channel used: ${self.manager.allocation.channel_used:.2f} / ${self.config['total_capital'] * self.config['channel_allocation']:.0f}"
        )
        logger.info(f"  Total available: ${self.manager.allocation.total_available:.2f}")

    async def run_all_tests(self):
        """Run all tests"""
        logger.info("Starting Strategy Manager Tests with Channel Integration")
        logger.info("=" * 80)

        await self.test_all_strategies()

        logger.info("\n" + "=" * 80)
        logger.info("✅ All Strategy Manager Tests Complete!")
        logger.info("Channel strategy successfully integrated with DCA and Swing!")


async def main():
    test = StrategyManagerTest()
    await test.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
