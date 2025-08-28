#!/usr/bin/env python3
"""
Test that all updated scripts can properly load the unified configuration.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))


def test_regime_detector():
    """Test RegimeDetector can load config"""
    print("\nTesting RegimeDetector...")
    try:
        from src.strategies.regime_detector import RegimeDetector

        detector = RegimeDetector()
        assert detector.config is not None, "Config not loaded"
        assert detector.market_protection is not None, "Market protection not loaded"
        print(
            f"✅ RegimeDetector loaded config version: {detector.config.get('version', 'unknown')}"
        )
        print(
            f"   Market protection enabled: {detector.market_protection.get('enabled', False)}"
        )
        return True
    except Exception as e:
        print(f"❌ RegimeDetector failed: {e}")
        return False


def test_trade_limiter():
    """Test TradeLimiter can load config"""
    print("\nTesting TradeLimiter...")
    try:
        from src.trading.trade_limiter import TradeLimiter

        limiter = TradeLimiter()
        assert limiter.config is not None, "Config not loaded"
        assert limiter.market_protection is not None, "Market protection not loaded"
        print(
            f"✅ TradeLimiter loaded config version: {limiter.config.get('version', 'unknown')}"
        )
        print(f"   Max consecutive stops: {limiter.max_consecutive_stops}")
        print(f"   Cooldown hours: {limiter.cooldown_hours}")
        return True
    except Exception as e:
        print(f"❌ TradeLimiter failed: {e}")
        return False


def test_strategy_precalculator():
    """Test StrategyPreCalculator can load config"""
    print("\nTesting StrategyPreCalculator...")
    try:
        from scripts.strategy_precalculator import StrategyPreCalculator

        calc = StrategyPreCalculator()
        # Check that simple_rules has the config
        assert calc.simple_rules is not None, "SimpleRules not initialized"
        assert calc.simple_rules.config is not None, "Config not loaded in SimpleRules"
        print(f"✅ StrategyPreCalculator loaded config")
        print(f"   DCA threshold: {calc.simple_rules.config['dca_drop_threshold']}")
        print(
            f"   SWING threshold: {calc.simple_rules.config['swing_breakout_threshold']}"
        )
        print(
            f"   CHANNEL buy zone: {calc.simple_rules.config['channel_position_threshold']}"
        )
        return True
    except Exception as e:
        print(f"❌ StrategyPreCalculator failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    print("=" * 50)
    print("TESTING UPDATED SCRIPTS WITH UNIFIED CONFIG")
    print("=" * 50)

    all_passed = True

    # Test each updated component
    all_passed = test_regime_detector() and all_passed
    all_passed = test_trade_limiter() and all_passed
    all_passed = test_strategy_precalculator() and all_passed

    print("\n" + "=" * 50)
    if all_passed:
        print("✅ ALL SCRIPTS SUCCESSFULLY USING UNIFIED CONFIG!")
    else:
        print("❌ SOME SCRIPTS FAILED TO LOAD CONFIG")
    print("=" * 50)

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
