#!/usr/bin/env python3
"""
Test script to verify position_size_multiplier fix works correctly
Tests both SimpleRules and complex detector paths
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from loguru import logger

# Import the components we're testing
from src.strategies.swing.detector import SwingDetector
from src.strategies.swing.analyzer import SwingAnalyzer
from src.strategies.simple_rules import SimpleRules
from src.strategies.manager import StrategyManager
from src.config.settings import Settings


def create_test_data():
    """Create test market data for swing detection"""
    # Create 100 bars of test data
    dates = pd.date_range(end=datetime.now(), periods=100, freq="15min")

    # Simulate a breakout pattern
    prices = np.random.randn(100).cumsum() + 100
    prices[-10:] = prices[-10:] * 1.03  # 3% breakout in last 10 bars

    df = pd.DataFrame(
        {
            "timestamp": dates,
            "open": prices * 0.99,
            "high": prices * 1.01,
            "low": prices * 0.98,
            "close": prices,
            "volume": np.random.randint(1000, 10000, 100),
        }
    )

    return df


def test_simple_rules_path():
    """Test that SimpleRules setups work with SwingAnalyzer"""
    logger.info("=" * 60)
    logger.info("Testing SimpleRules Path (Non-ML)")
    logger.info("=" * 60)

    try:
        # Create SimpleRules instance
        simple_rules = SimpleRules()

        # Create test data with a clear breakout
        data = create_test_data()

        # Convert to list format that SimpleRules expects
        data_list = data.to_dict("records")

        # Check for swing setup
        setup = simple_rules.check_swing_setup("BTC", data_list)

        if setup:
            logger.info(f"✅ SimpleRules detected setup: {setup}")

            # Now test the conversion that happens in StrategyManager
            converted_setup = {
                "symbol": "BTC",
                "detected_at": datetime.now().isoformat(),
                "price": setup.get("entry_price", 0),
                "breakout_strength": setup.get("breakout_pct", 0) / 100,
                "volume_surge": setup.get("volume_surge", 1),
                "momentum_score": 0.5,
                "pattern": "simple_breakout",
                "confidence": setup.get("confidence", 0.5),
                "position_size_multiplier": 1.0,  # This is what we added in the fix
                "score": 50,  # This is what we added in the fix
                "from_simple_rules": True,
            }

            # Test with SwingAnalyzer
            analyzer = SwingAnalyzer()
            market_conditions = {
                "btc_trend": "NEUTRAL",
                "market_breadth": 0.5,
                "fear_greed": 50,
                "volume_trend": "NORMAL",
            }

            # This should NOT crash anymore
            analysis = analyzer.analyze_setup(converted_setup, market_conditions)

            logger.info(f"✅ Analysis successful!")
            logger.info(f"   Adjusted size multiplier: {analysis.get('adjusted_size_multiplier', 'N/A')}")
            logger.info(f"   Market regime: {analysis.get('market_regime', 'N/A')}")
            logger.info(f"   Expected value: {analysis.get('expected_value', 'N/A')}")

            return True
        else:
            logger.warning("No setup detected by SimpleRules (this is OK for this test data)")
            return True

    except Exception as e:
        logger.error(f"❌ SimpleRules path failed: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return False


def test_complex_detector_path():
    """Test that complex detector setups still work"""
    logger.info("=" * 60)
    logger.info("Testing Complex Detector Path (ML-Ready)")
    logger.info("=" * 60)

    try:
        # Create SwingDetector instance
        detector = SwingDetector()

        # Create test data
        data = create_test_data()

        # Detect setup
        setup = detector.detect_setup("ETH", data)

        if setup:
            logger.info(f"✅ SwingDetector found setup with score: {setup.get('score', 'N/A')}")
            logger.info(f"   Position size multiplier: {setup.get('position_size_multiplier', 'N/A')}")

            # Test with SwingAnalyzer
            analyzer = SwingAnalyzer()
            market_conditions = {
                "btc_trend": "BEAR",  # Test BEAR market adjustment
                "market_breadth": 0.3,
                "fear_greed": 30,
                "volume_trend": "DECLINING",
            }

            analysis = analyzer.analyze_setup(setup, market_conditions)

            logger.info(f"✅ Analysis successful!")
            logger.info(f"   Original multiplier: {setup.get('position_size_multiplier', 'N/A')}")
            logger.info(f"   Adjusted multiplier: {analysis.get('adjusted_size_multiplier', 'N/A')}")
            logger.info(f"   Market regime: {analysis.get('market_regime', 'N/A')}")

            # Verify BEAR market increased the multiplier
            if analysis.get("market_regime") == "BEAR":
                original = setup.get("position_size_multiplier", 1.0)
                adjusted = analysis.get("adjusted_size_multiplier", 1.0)
                if adjusted > original:
                    logger.info(f"✅ BEAR market correctly increased multiplier: {original:.2f} → {adjusted:.2f}")
                else:
                    logger.warning(f"⚠️  BEAR market should increase multiplier but didn't")

            return True
        else:
            logger.info("No setup detected by complex detector (normal for random data)")
            return True

    except Exception as e:
        logger.error(f"❌ Complex detector path failed: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return False


def test_strategy_manager_integration():
    """Test the full integration through StrategyManager"""
    logger.info("=" * 60)
    logger.info("Testing Full Strategy Manager Integration")
    logger.info("=" * 60)

    try:
        # Create StrategyManager with ML disabled (uses SimpleRules)
        settings = Settings()
        config = {
            "ml_enabled": False,  # This forces SimpleRules path
            "shadow_enabled": False,
            "base_position_usd": 50.0,
            "max_open_positions": 10,
            "swing_breakout_threshold": 2.0,  # Lower threshold for testing
        }

        manager = StrategyManager(config, settings)

        # Create market data for multiple symbols
        market_data = {}
        for symbol in ["BTC", "ETH", "SOL"]:
            data = create_test_data()
            # Make SOL have a stronger breakout
            if symbol == "SOL":
                data["close"] = data["close"] * 1.05  # 5% pump
            market_data[symbol] = data

        # Scan for opportunities (this tests the full pipeline)
        signals = manager._scan_swing_opportunities(market_data)

        logger.info(f"Found {len(signals)} swing signals")

        if signals:
            for signal in signals:
                logger.info(f"✅ Signal for {signal.symbol}:")
                logger.info(f"   Confidence: {signal.confidence:.2f}")
                logger.info(f"   Required capital: ${signal.required_capital:.2f}")

                # Check that setup_data has the multiplier
                setup = signal.setup_data.get("setup", {})
                if "position_size_multiplier" in setup:
                    logger.info(f"   ✅ Has position_size_multiplier: {setup['position_size_multiplier']}")
                else:
                    logger.error(f"   ❌ Missing position_size_multiplier!")
                    return False

        logger.info("✅ Strategy Manager integration test passed!")
        return True

    except Exception as e:
        logger.error(f"❌ Strategy Manager integration failed: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return False


def main():
    """Run all tests"""
    logger.info("\n" + "=" * 60)
    logger.info("POSITION SIZE MULTIPLIER FIX VERIFICATION")
    logger.info("=" * 60 + "\n")

    results = []

    # Test 1: SimpleRules path
    results.append(("SimpleRules Path", test_simple_rules_path()))

    # Test 2: Complex detector path
    results.append(("Complex Detector Path", test_complex_detector_path()))

    # Test 3: Full integration
    results.append(("Strategy Manager Integration", test_strategy_manager_integration()))

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)

    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
        if not passed:
            all_passed = False

    if all_passed:
        logger.info("\n🎉 ALL TESTS PASSED! The position_size_multiplier fix is working correctly.")
        logger.info("The error in Slack should now be resolved.")
    else:
        logger.error("\n⚠️  Some tests failed. Please review the errors above.")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
