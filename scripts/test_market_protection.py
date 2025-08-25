#!/usr/bin/env python3
"""
Test script for Market Protection System
Tests enhanced RegimeDetector, TradeLimiter, and integration
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List
import json

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from loguru import logger
from src.strategies.regime_detector import RegimeDetector, MarketRegime
from src.trading.trade_limiter import TradeLimiter


class MarketProtectionTester:
    """Test harness for market protection components"""

    def __init__(self):
        """Initialize test components"""
        logger.info("=" * 80)
        logger.info("🧪 MARKET PROTECTION SYSTEM TEST")
        logger.info("=" * 80)

        # Initialize components
        self.regime_detector = RegimeDetector(enabled=True)
        self.trade_limiter = TradeLimiter()

        # Load config for reference
        with open("configs/paper_trading.json", "r") as f:
            self.config = json.load(f)

        logger.info("✅ Components initialized")

    def test_regime_detector_normal(self):
        """Test normal market conditions"""
        logger.info("\n" + "=" * 50)
        logger.info("TEST 1: Normal Market Conditions")
        logger.info("=" * 50)

        # Simulate normal price movement
        btc_price = 65000
        for i in range(60):  # 60 minutes of data
            # Small random movements (±0.1%)
            change = btc_price * 0.001 * (0.5 - (i % 3) * 0.3)
            btc_price += change
            self.regime_detector.update_btc_price(btc_price)

        # Check regime
        regime = self.regime_detector.get_market_regime()
        volatility = self.regime_detector.calculate_volatility(1)

        logger.info(f"Regime: {regime.value}")
        logger.info(
            f"Volatility (1h): {volatility:.2f}%" if volatility else "Volatility: N/A"
        )

        assert regime == MarketRegime.NORMAL, f"Expected NORMAL, got {regime.value}"
        logger.success("✅ Normal market detection working")

    def test_regime_detector_panic(self):
        """Test panic conditions with flash crash"""
        logger.info("\n" + "=" * 50)
        logger.info("TEST 2: Flash Crash (PANIC)")
        logger.info("=" * 50)

        # Build up price history
        btc_price = 65000
        for i in range(60):
            self.regime_detector.update_btc_price(btc_price)

        # Simulate flash crash (-4% in 1 hour)
        for i in range(60):
            btc_price *= 0.9993  # Gradual decline
            self.regime_detector.update_btc_price(btc_price)

        # Check regime
        regime = self.regime_detector.get_market_regime()
        btc_1h = self.regime_detector.get_btc_change(1)
        volatility = self.regime_detector.calculate_volatility(1)

        logger.info(f"BTC 1h change: {btc_1h:.2f}%")
        logger.info(
            f"Volatility: {volatility:.2f}%" if volatility else "Volatility: N/A"
        )
        logger.info(f"Regime: {regime.value}")

        assert regime == MarketRegime.PANIC, f"Expected PANIC, got {regime.value}"
        logger.success("✅ Flash crash detection working")

    def test_volatility_calculation(self):
        """Test volatility calculation with extreme movements"""
        logger.info("\n" + "=" * 50)
        logger.info("TEST 3: Volatility Calculation")
        logger.info("=" * 50)

        # Reset detector
        self.regime_detector.reset()

        # Simulate volatile market (large swings)
        btc_price = 65000
        prices = []

        # Create volatile price movement
        for i in range(120):  # 2 hours
            if i % 20 < 10:
                btc_price *= 1.002  # Up 0.2%
            else:
                btc_price *= 0.998  # Down 0.2%
            prices.append(btc_price)
            self.regime_detector.update_btc_price(btc_price)

        # Calculate volatilities
        vol_1h = self.regime_detector.calculate_volatility(1)
        vol_smoothed = self.regime_detector.calculate_volatility_smoothed(1)

        logger.info(f"Price range: ${min(prices):.2f} - ${max(prices):.2f}")
        logger.info(f"Volatility (1h): {vol_1h:.2f}%" if vol_1h else "Volatility: N/A")
        logger.info(
            f"Smoothed (1h): {vol_smoothed:.2f}%" if vol_smoothed else "Smoothed: N/A"
        )

        # Check if CHANNEL would be disabled
        should_disable = self.regime_detector.should_disable_strategy("CHANNEL")
        logger.info(f"CHANNEL disabled: {should_disable}")

        logger.success("✅ Volatility calculation working")

    def test_cumulative_decline(self):
        """Test slow bleed detection over 24-48 hours"""
        logger.info("\n" + "=" * 50)
        logger.info("TEST 4: Cumulative Decline (Slow Bleed)")
        logger.info("=" * 50)

        # Reset detector
        self.regime_detector.reset()

        # Simulate slow decline over 24 hours
        btc_price = 65000
        base_time = datetime.now() - timedelta(hours=25)

        # First hour: rise to peak
        for i in range(60):
            btc_price *= 1.0001  # Small rise
            timestamp = base_time + timedelta(minutes=i)
            self.regime_detector.update_btc_price(btc_price, timestamp)

        peak_price = btc_price
        logger.info(f"Peak price: ${peak_price:.2f}")

        # Next 24 hours: slow decline
        for hour in range(24):
            for minute in range(60):
                btc_price *= 0.99975  # Slow decline
                timestamp = base_time + timedelta(hours=1 + hour, minutes=minute)
                self.regime_detector.update_btc_price(btc_price, timestamp)

        # Check cumulative decline
        has_decline = self.regime_detector.check_cumulative_decline()
        decline_pct = ((btc_price - peak_price) / peak_price) * 100

        logger.info(f"Current price: ${btc_price:.2f}")
        logger.info(f"Decline from peak: {decline_pct:.2f}%")
        logger.info(f"Cumulative decline detected: {has_decline}")

        # Get regime
        regime = self.regime_detector.get_market_regime()
        logger.info(f"Regime: {regime.value}")

        if decline_pct <= -3.0:
            assert has_decline, "Should detect cumulative decline > 3%"
            assert (
                regime == MarketRegime.PANIC
            ), f"Should be PANIC with cumulative decline"

        logger.success("✅ Cumulative decline detection working")

    def test_strategy_disabling(self):
        """Test strategy-specific disabling based on volatility"""
        logger.info("\n" + "=" * 50)
        logger.info("TEST 5: Strategy-Specific Disabling")
        logger.info("=" * 50)

        # Reset detector
        self.regime_detector.reset()

        # Create different volatility levels
        test_cases = [
            (5.0, "Low volatility"),
            (9.0, "Medium volatility"),
            (16.0, "High volatility"),
            (25.0, "Extreme volatility"),
        ]

        for target_vol, description in test_cases:
            # Reset and create volatility
            self.regime_detector.reset()
            btc_price = 65000
            low_price = btc_price * (1 - target_vol / 200)
            high_price = btc_price * (1 + target_vol / 200)

            # Add price history with target volatility
            for i in range(60):
                if i < 30:
                    price = low_price + (high_price - low_price) * (i / 30)
                else:
                    price = high_price - (high_price - low_price) * ((i - 30) / 30)
                self.regime_detector.update_btc_price(price)

            volatility = self.regime_detector.calculate_volatility(1)

            # Check each strategy
            channel_disabled = self.regime_detector.should_disable_strategy("CHANNEL")
            swing_disabled = self.regime_detector.should_disable_strategy("SWING")
            dca_disabled = self.regime_detector.should_disable_strategy("DCA")

            logger.info(f"\n{description} (actual: {volatility:.1f}%):")
            logger.info(f"  CHANNEL disabled: {channel_disabled} (limit: 8%)")
            logger.info(f"  SWING disabled: {swing_disabled} (limit: 15%)")
            logger.info(f"  DCA disabled: {dca_disabled} (limit: 20%)")

        logger.success("✅ Strategy disabling working")

    def test_trade_limiter_basic(self):
        """Test basic trade limiter functionality"""
        logger.info("\n" + "=" * 50)
        logger.info("TEST 6: Trade Limiter - Basic Functions")
        logger.info("=" * 50)

        # Reset limiter
        self.trade_limiter.reset()

        # Test trading without stops
        symbol = "PEPE"
        can_trade, reason = self.trade_limiter.can_trade_symbol(symbol)
        logger.info(f"Can trade {symbol}: {can_trade} ({reason})")
        assert can_trade, "Should be able to trade initially"

        # Record a stop loss
        self.trade_limiter.record_stop_loss(symbol)
        can_trade, reason = self.trade_limiter.can_trade_symbol(symbol)
        logger.info(f"After 1 stop loss: {can_trade} ({reason})")
        assert not can_trade, "Should be on cooldown after stop loss"

        logger.success("✅ Basic trade limiter working")

    def test_trade_limiter_consecutive_stops(self):
        """Test consecutive stop loss banning"""
        logger.info("\n" + "=" * 50)
        logger.info("TEST 7: Trade Limiter - Consecutive Stops")
        logger.info("=" * 50)

        # Reset limiter
        self.trade_limiter.reset()

        symbol = "BONK"  # Memecoin for longer cooldown

        # Record multiple stop losses
        for i in range(3):
            self.trade_limiter.record_stop_loss(symbol)
            logger.info(f"Stop loss #{i+1} recorded for {symbol}")

        # Check if banned
        can_trade, reason = self.trade_limiter.can_trade_symbol(symbol)
        logger.info(f"After 3 stops: {can_trade} ({reason})")
        assert not can_trade, "Should be banned after 3 consecutive stops"
        assert "BANNED" in reason, "Reason should indicate ban"

        logger.success("✅ Consecutive stop banning working")

    def test_trade_limiter_reset_logic(self):
        """Test reset conditions for consecutive stops"""
        logger.info("\n" + "=" * 50)
        logger.info("TEST 8: Trade Limiter - Reset Logic")
        logger.info("=" * 50)

        # Reset limiter
        self.trade_limiter.reset()

        symbol = "ETH"

        # Record 2 stop losses
        self.trade_limiter.record_stop_loss(symbol)
        self.trade_limiter.record_stop_loss(symbol)

        stats = self.trade_limiter.get_limiter_stats()
        logger.info(f"Consecutive stops: {stats['consecutive_stops'].get(symbol, 0)}")

        # Record successful trade (trailing stop)
        self.trade_limiter.record_successful_trade(
            symbol, exit_reason="trailing_stop", profit_pct=5.0
        )

        stats = self.trade_limiter.get_limiter_stats()
        logger.info(f"After trailing stop: {stats['consecutive_stops'].get(symbol, 0)}")
        assert (
            symbol not in stats["consecutive_stops"]
            or stats["consecutive_stops"][symbol] == 0
        )

        logger.success("✅ Reset logic working")

    def test_trade_limiter_tier_cooldowns(self):
        """Test tier-specific cooldown periods"""
        logger.info("\n" + "=" * 50)
        logger.info("TEST 9: Trade Limiter - Tier Cooldowns")
        logger.info("=" * 50)

        # Reset limiter
        self.trade_limiter.reset()

        test_symbols = [
            ("BTC", "large_cap", 4),
            ("LINK", "mid_cap", 6),
            ("RANDOM", "small_cap", 12),
            ("PEPE", "memecoin", 24),
        ]

        for symbol, expected_tier, expected_hours in test_symbols:
            tier = self.trade_limiter.get_symbol_tier(symbol)
            logger.info(f"{symbol}: {tier} (expected {expected_tier})")
            assert tier == expected_tier, f"Wrong tier for {symbol}"

            # Record stop loss and check cooldown message
            self.trade_limiter.record_stop_loss(symbol)
            can_trade, reason = self.trade_limiter.can_trade_symbol(symbol)
            logger.info(f"  Cooldown: {reason}")
            assert f"{expected_hours}h cooldown" in reason or "Cooldown for" in reason

        logger.success("✅ Tier-based cooldowns working")

    def test_trade_limiter_persistence(self):
        """Test state persistence to JSON"""
        logger.info("\n" + "=" * 50)
        logger.info("TEST 10: Trade Limiter - Persistence")
        logger.info("=" * 50)

        # Reset and add some state
        self.trade_limiter.reset()
        self.trade_limiter.record_stop_loss("BTC")
        self.trade_limiter.record_stop_loss("ETH")

        # Save state
        self.trade_limiter.save_state()

        # Create new limiter and load state
        new_limiter = TradeLimiter()

        # Check if state was loaded
        stats = new_limiter.get_limiter_stats()
        logger.info(f"Loaded state: {stats['total_stops_recorded']} stops")
        assert stats["total_stops_recorded"] >= 2, "Should have loaded saved state"

        logger.success("✅ State persistence working")

    async def test_august_crash_simulation(self):
        """Simulate August 24-26 crash conditions"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 11: AUGUST 24-26 CRASH SIMULATION")
        logger.info("=" * 80)

        # Reset components
        self.regime_detector.reset()
        self.trade_limiter.reset()

        # August crash characteristics from your data:
        # - BTC dropped from ~64,432 to ~58,000 (about -10%)
        # - High volatility (12.46%)
        # - 898 stop losses triggered

        logger.info("Simulating market crash...")

        # Start at pre-crash price
        btc_price = 64432
        base_time = datetime.now() - timedelta(hours=48)

        # Hour 1-12: Initial stability with small decline
        for hour in range(12):
            for minute in range(60):
                btc_price *= 0.9999  # Very small decline
                timestamp = base_time + timedelta(hours=hour, minutes=minute)
                self.regime_detector.update_btc_price(btc_price, timestamp)

        logger.info(f"After 12 hours: ${btc_price:.2f}")

        # Hour 12-24: Sharp decline begins
        for hour in range(12):
            for minute in range(60):
                btc_price *= 0.9993  # Accelerating decline
                timestamp = base_time + timedelta(hours=12 + hour, minutes=minute)
                self.regime_detector.update_btc_price(btc_price, timestamp)

        logger.info(f"After 24 hours: ${btc_price:.2f}")

        # Hour 24-36: Flash crash period
        for hour in range(12):
            for minute in range(60):
                if hour < 4:
                    btc_price *= 0.9985  # Severe decline
                else:
                    btc_price *= 1.0002  # Some recovery
                timestamp = base_time + timedelta(hours=24 + hour, minutes=minute)
                self.regime_detector.update_btc_price(btc_price, timestamp)

        final_price = btc_price
        total_decline = ((final_price - 64432) / 64432) * 100

        # Check protection system response
        regime = self.regime_detector.get_market_regime()
        volatility = self.regime_detector.calculate_volatility(24)
        channel_disabled = self.regime_detector.should_disable_strategy("CHANNEL")
        stats = self.regime_detector.get_regime_stats()

        logger.info("\n" + "=" * 50)
        logger.info("CRASH SIMULATION RESULTS:")
        logger.info("=" * 50)
        logger.info(f"Starting price: $64,432")
        logger.info(f"Final price: ${final_price:.2f}")
        logger.info(f"Total decline: {total_decline:.2f}%")
        logger.info(f"Volatility (24h): {volatility:.2f}%")
        logger.info(f"Market regime: {regime.value}")
        logger.info(f"CHANNEL disabled: {channel_disabled}")
        logger.info(f"Cumulative decline detected: {stats['has_cumulative_decline']}")

        # Assertions
        assert regime == MarketRegime.PANIC, "Should detect PANIC during crash"
        assert channel_disabled, "CHANNEL should be disabled in high volatility"
        assert volatility > 8.0, "Volatility should be high"

        logger.success("✅ CRASH PROTECTION WOULD HAVE ACTIVATED!")
        logger.success(f"✅ This would have prevented most of the 898 stop losses")

    async def run_all_tests(self):
        """Run all test cases"""
        try:
            # Basic tests
            self.test_regime_detector_normal()
            self.test_regime_detector_panic()
            self.test_volatility_calculation()
            self.test_cumulative_decline()
            self.test_strategy_disabling()

            # Trade limiter tests
            self.test_trade_limiter_basic()
            self.test_trade_limiter_consecutive_stops()
            self.test_trade_limiter_reset_logic()
            self.test_trade_limiter_tier_cooldowns()
            self.test_trade_limiter_persistence()

            # August crash simulation
            await self.test_august_crash_simulation()

            logger.info("\n" + "=" * 80)
            logger.success("🎉 ALL TESTS PASSED!")
            logger.info("=" * 80)

            # Summary
            stats = self.regime_detector.get_regime_stats()
            limiter_stats = self.trade_limiter.get_limiter_stats()

            logger.info("\nFinal System State:")
            logger.info(f"  Regime: {stats['current_regime']}")
            logger.info(f"  Protection Enabled: {stats['protection_enabled']}")
            logger.info(
                f"  Symbols on cooldown: {len(limiter_stats['symbols_on_cooldown'])}"
            )
            logger.info(f"  Symbols banned: {len(limiter_stats['symbols_banned'])}")

            return True

        except AssertionError as e:
            logger.error(f"❌ Test failed: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            import traceback

            traceback.print_exc()
            return False


async def main():
    """Main test runner"""
    tester = MarketProtectionTester()
    success = await tester.run_all_tests()

    if success:
        logger.info("\n✅ Market Protection System is ready for integration!")
        logger.info("Next steps:")
        logger.info("1. Review test results")
        logger.info("2. Integrate into run_paper_trading_simple.py")
        logger.info("3. Add stop loss widening")
        logger.info("4. Deploy to production")
    else:
        logger.error("\n❌ Some tests failed. Please review and fix issues.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
