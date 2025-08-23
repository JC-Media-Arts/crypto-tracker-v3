#!/usr/bin/env python3
"""
Test script for Market Regime Detector (Circuit Breaker)
"""

import asyncio
from datetime import datetime, timedelta
from loguru import logger
import sys

sys.path.append(".")

from src.strategies.regime_detector import RegimeDetector, MarketRegime

# Configure logger
logger.add("logs/regime_detector_test.log", rotation="10 MB")


class RegimeDetectorTest:
    def __init__(self):
        self.detector = RegimeDetector(enabled=True)

    def test_normal_market(self):
        """Test normal market conditions"""
        logger.info("\n" + "=" * 60)
        logger.info("Testing NORMAL Market Conditions")
        logger.info("=" * 60)

        # Simulate normal price movement (small changes)
        base_price = 100000
        now = datetime.now()

        for i in range(60):  # 1 hour of data
            price = base_price + (i * 10)  # Slight upward trend
            timestamp = now - timedelta(minutes=60 - i)
            self.detector.update_btc_price(price, timestamp)

        regime = self.detector.get_market_regime()
        stats = self.detector.get_regime_stats()

        logger.info(f"Regime: {regime.value}")
        if stats["btc_1h_change"] is not None:
            logger.info(f"BTC 1h change: {stats['btc_1h_change']:.2f}%")
        else:
            logger.info(f"BTC 1h change: N/A (insufficient data)")
        logger.info(f"Position multiplier: {stats['position_multiplier']}")

        assert regime == MarketRegime.NORMAL, f"Expected NORMAL, got {regime}"
        logger.info("✅ Normal market test passed")

    def test_panic_market(self):
        """Test panic market conditions (flash crash)"""
        logger.info("\n" + "=" * 60)
        logger.info("Testing PANIC Market Conditions (Flash Crash)")
        logger.info("=" * 60)

        # Reset detector
        self.detector.reset()

        # Simulate flash crash (-4% in 1 hour)
        base_price = 100000
        now = datetime.now()

        # First 30 minutes: stable
        for i in range(30):
            price = base_price
            timestamp = now - timedelta(minutes=60 - i)
            self.detector.update_btc_price(price, timestamp)

        # Last 30 minutes: crash
        for i in range(30, 60):
            price = base_price * 0.96  # 4% drop
            timestamp = now - timedelta(minutes=60 - i)
            self.detector.update_btc_price(price, timestamp)

        regime = self.detector.get_market_regime()
        stats = self.detector.get_regime_stats()

        logger.info(f"Regime: {regime.value}")
        if stats["btc_1h_change"] is not None:
            logger.info(f"BTC 1h change: {stats['btc_1h_change']:.2f}%")
        else:
            logger.info(f"BTC 1h change: N/A (insufficient data)")
        logger.info(f"Position multiplier: {stats['position_multiplier']}")

        assert regime == MarketRegime.PANIC, f"Expected PANIC, got {regime}"
        assert stats["position_multiplier"] == 0.0, "Should stop all new trades"
        logger.info("✅ Panic market test passed")

    def test_caution_market(self):
        """Test caution market conditions"""
        logger.info("\n" + "=" * 60)
        logger.info("Testing CAUTION Market Conditions")
        logger.info("=" * 60)

        # Reset detector
        self.detector.reset()

        # Simulate moderate drop (-2.5% in 1 hour)
        base_price = 100000
        now = datetime.now()

        for i in range(60):
            if i < 30:
                price = base_price
            else:
                price = base_price * 0.975  # 2.5% drop
            timestamp = now - timedelta(minutes=60 - i)
            self.detector.update_btc_price(price, timestamp)

        regime = self.detector.get_market_regime()
        stats = self.detector.get_regime_stats()

        logger.info(f"Regime: {regime.value}")
        if stats["btc_1h_change"] is not None:
            logger.info(f"BTC 1h change: {stats['btc_1h_change']:.2f}%")
        else:
            logger.info(f"BTC 1h change: N/A (insufficient data)")
        logger.info(f"Position multiplier: {stats['position_multiplier']}")

        assert regime == MarketRegime.CAUTION, f"Expected CAUTION, got {regime}"
        assert stats["position_multiplier"] == 0.5, "Should reduce positions by 50%"
        logger.info("✅ Caution market test passed")

    def test_euphoria_market(self):
        """Test euphoria market conditions (FOMO)"""
        logger.info("\n" + "=" * 60)
        logger.info("Testing EUPHORIA Market Conditions (FOMO)")
        logger.info("=" * 60)

        # Reset detector
        self.detector.reset()

        # Simulate rapid rise (+4% in 1 hour)
        base_price = 100000
        now = datetime.now()

        for i in range(60):
            if i < 30:
                price = base_price
            else:
                price = base_price * 1.04  # 4% rise
            timestamp = now - timedelta(minutes=60 - i)
            self.detector.update_btc_price(price, timestamp)

        regime = self.detector.get_market_regime()
        stats = self.detector.get_regime_stats()

        logger.info(f"Regime: {regime.value}")
        if stats["btc_1h_change"] is not None:
            logger.info(f"BTC 1h change: {stats['btc_1h_change']:.2f}%")
        else:
            logger.info(f"BTC 1h change: N/A (insufficient data)")
        logger.info(f"Position multiplier: {stats['position_multiplier']}")

        assert regime == MarketRegime.EUPHORIA, f"Expected EUPHORIA, got {regime}"
        assert stats["position_multiplier"] == 0.7, "Should reduce positions by 30%"
        logger.info("✅ Euphoria market test passed")

    def test_4h_trigger(self):
        """Test 4-hour caution trigger"""
        logger.info("\n" + "=" * 60)
        logger.info("Testing 4-Hour CAUTION Trigger")
        logger.info("=" * 60)

        # Reset detector
        self.detector.reset()

        # Simulate slow bleed (-6% over 4 hours, but only -1% in last hour)
        base_price = 100000
        now = datetime.now()

        # Fill 4 hours of data
        for i in range(240):  # 4 hours * 60 minutes
            if i < 180:  # First 3 hours: drop 5%
                price = base_price * (1 - (i * 0.05 / 180))
            else:  # Last hour: recover slightly (so 1h change is small)
                price = base_price * 0.95 * (1 + ((i - 180) * 0.01 / 60))  # Recover 1%
            timestamp = now - timedelta(minutes=240 - i)
            self.detector.update_btc_price(price, timestamp)

        regime = self.detector.get_market_regime()
        stats = self.detector.get_regime_stats()

        logger.info(f"Regime: {regime.value}")
        if stats["btc_1h_change"] is not None:
            logger.info(f"BTC 1h change: {stats['btc_1h_change']:.2f}%")
        else:
            logger.info(f"BTC 1h change: N/A")
        if stats["btc_4h_change"] is not None:
            logger.info(f"BTC 4h change: {stats['btc_4h_change']:.2f}%")
        else:
            logger.info(f"BTC 4h change: N/A")
        logger.info(f"Position multiplier: {stats['position_multiplier']}")

        # Should trigger CAUTION due to 4h change even if 1h is small
        assert regime == MarketRegime.CAUTION, f"Expected CAUTION from 4h trigger, got {regime}"
        logger.info("✅ 4-hour trigger test passed")

    def test_disabled_mode(self):
        """Test that detector can be disabled"""
        logger.info("\n" + "=" * 60)
        logger.info("Testing Disabled Mode")
        logger.info("=" * 60)

        # Create disabled detector
        disabled_detector = RegimeDetector(enabled=False)

        # Add crash data
        disabled_detector.update_btc_price(100000)
        disabled_detector.update_btc_price(90000)  # 10% crash

        regime = disabled_detector.get_market_regime()
        multiplier = disabled_detector.get_position_multiplier()

        logger.info(f"Regime (disabled): {regime.value}")
        logger.info(f"Position multiplier (disabled): {multiplier}")

        assert regime == MarketRegime.NORMAL, "Disabled detector should always return NORMAL"
        assert multiplier == 1.0, "Disabled detector should not affect position sizing"
        logger.info("✅ Disabled mode test passed")

    def run_all_tests(self):
        """Run all tests"""
        logger.info("Starting Regime Detector Tests")
        logger.info("=" * 80)

        self.test_normal_market()
        self.test_panic_market()
        self.test_caution_market()
        self.test_euphoria_market()
        self.test_4h_trigger()
        self.test_disabled_mode()

        logger.info("\n" + "=" * 80)
        logger.info("✅ All Regime Detector Tests Passed!")
        logger.info("Circuit Breaker is ready to protect against flash crashes!")


def main():
    test = RegimeDetectorTest()
    test.run_all_tests()


if __name__ == "__main__":
    main()
