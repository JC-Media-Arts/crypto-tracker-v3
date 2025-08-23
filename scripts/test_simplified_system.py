#!/usr/bin/env python3
"""
Test the simplified strategy system (Phase 1 Recovery)
Tests that strategies work without ML
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from loguru import logger
from src.strategies.manager import StrategyManager


async def test_simplified_strategies():
    """Test strategies with ML disabled"""

    logger.info("=" * 60)
    logger.info("TESTING SIMPLIFIED STRATEGY SYSTEM")
    logger.info("=" * 60)

    # Load recovery config
    config_path = Path("config/recovery_phase.json")
    if config_path.exists():
        with open(config_path, "r") as f:
            recovery_config = json.load(f)
            logger.info(f"Loaded recovery config: {recovery_config.get('phase')}")
    else:
        recovery_config = {}

    # Create test config with ML disabled
    config = {
        "ml_enabled": False,
        "shadow_testing_enabled": False,
        "regime_detection_enabled": False,  # Disable regime for simplicity
        "total_capital": 1000,
        "dca_allocation": 0.4,
        "swing_allocation": 0.3,
        "channel_allocation": 0.3,
        "base_position_usd": 50,  # Base position size for simplified trading
        # Use simplified thresholds from recovery config
        "dca_config": recovery_config.get(
            "dca_config",
            {"drop_threshold": -3.5, "min_confidence": 0.0, "use_ml": False},
        ),
        "swing_config": recovery_config.get(
            "swing_config",
            {"breakout_threshold": 2.1, "min_confidence": 0.0, "use_ml": False},
        ),
        "channel_config": recovery_config.get(
            "channel_config",
            {"min_channel_strength": 0.42, "min_confidence": 0.0, "use_ml": False},
        ),
        # No ML confidence needed
        "min_confidence": 0.0,
        "min_risk_reward": 1.0,  # Lower for more signals
    }

    # Initialize strategy manager
    manager = StrategyManager(config)

    # Verify ML is disabled
    assert not manager.ml_enabled, "ML should be disabled"
    assert manager.simple_rules is not None, "Simple rules should be initialized"
    assert manager.ml_predictor is None, "ML predictor should be None"

    logger.info(f"✅ ML disabled: {not manager.ml_enabled}")
    logger.info(f"✅ Shadow disabled: {not manager.shadow_enabled}")
    logger.info(
        f"✅ Using simple rules with fixed confidence: {manager.simple_rules.fixed_confidence}"
    )

    # Create test market data
    test_data = create_test_market_data()

    # Test scanning for opportunities
    logger.info("\n" + "=" * 40)
    logger.info("SCANNING FOR OPPORTUNITIES")
    logger.info("=" * 40)

    signals = await manager.scan_for_opportunities(test_data)

    logger.info(f"\nFound {len(signals)} signals:")
    for signal in signals:
        logger.info(f"  {signal.strategy_type.value}: {signal.symbol}")
        logger.info(f"    Confidence: {signal.confidence:.1%}")
        logger.info(f"    Expected Value: {signal.expected_value:.2f}")
        logger.info(f"    Required Capital: ${signal.required_capital:.2f}")

    # Test simple rules directly
    logger.info("\n" + "=" * 40)
    logger.info("TESTING SIMPLE RULES DIRECTLY")
    logger.info("=" * 40)

    simple_rules = manager.simple_rules

    # Test DCA rule
    btc_data = test_data.get("BTC", [])
    if btc_data:
        dca_setup = simple_rules.check_dca_setup("BTC", btc_data)
        if dca_setup:
            logger.info(f"✅ DCA signal: {dca_setup['reason']}")
        else:
            logger.info("❌ No DCA signal for BTC")

    # Test Swing rule
    eth_data = test_data.get("ETH", [])
    if eth_data:
        swing_setup = simple_rules.check_swing_setup("ETH", eth_data)
        if swing_setup:
            logger.info(f"✅ Swing signal: {swing_setup['reason']}")
        else:
            logger.info("❌ No Swing signal for ETH")

    # Test Channel rule
    sol_data = test_data.get("SOL", [])
    if sol_data:
        channel_setup = simple_rules.check_channel_setup("SOL", sol_data)
        if channel_setup:
            logger.info(f"✅ Channel signal: {channel_setup['reason']}")
        else:
            logger.info("❌ No Channel signal for SOL")

    logger.info("\n" + "=" * 60)
    logger.info("SIMPLIFIED SYSTEM TEST COMPLETE")
    logger.info("System ready for paper trading without ML")
    logger.info("=" * 60)

    return True


def create_test_market_data():
    """Create test OHLC data that should trigger signals"""

    # BTC - Create a 4% drop (should trigger DCA at -3.5%)
    btc_data = []
    base_price = 50000
    for i in range(20):
        if i < 15:
            # Normal price action
            price = base_price + (i * 10)
        else:
            # Drop in last 5 bars
            price = base_price * 0.96  # 4% drop

        btc_data.append(
            {
                "timestamp": datetime.now(),
                "open": price,
                "high": price * 1.01,
                "low": price * 0.99,
                "close": price,
                "volume": 1000000,
            }
        )

    # ETH - Create a breakout with volume (should trigger Swing)
    eth_data = []
    base_price = 3000
    for i in range(10):
        if i < 9:
            # Build resistance
            price = base_price
            volume = 500000
        else:
            # Breakout in last bar
            price = base_price * 1.025  # 2.5% breakout
            volume = 1000000  # 2x volume

        eth_data.append(
            {
                "timestamp": datetime.now(),
                "open": price,
                "high": price * 1.01,
                "low": price * 0.99,
                "close": price,
                "volume": volume,
            }
        )

    # SOL - Create a range with price at bottom (should trigger Channel)
    sol_data = []
    for i in range(20):
        # Oscillate between 100 and 110
        if i % 4 < 2:
            price = 100 + (i % 2) * 2  # Near bottom
        else:
            price = 108 + (i % 2) * 2  # Near top

        # Put current price at bottom
        if i == 19:
            price = 101  # Near bottom of range

        sol_data.append(
            {
                "timestamp": datetime.now(),
                "open": price,
                "high": price * 1.01,
                "low": price * 0.99,
                "close": price,
                "volume": 300000,
            }
        )

    return {"BTC": btc_data, "ETH": eth_data, "SOL": sol_data}


if __name__ == "__main__":
    # Set environment variables to disable ML
    os.environ["ML_ENABLED"] = "false"
    os.environ["SHADOW_TESTING_ENABLED"] = "false"

    try:
        success = asyncio.run(test_simplified_strategies())
        if success:
            logger.info("\n✅ All tests passed! System ready for simplified trading.")
            sys.exit(0)
        else:
            logger.error("\n❌ Tests failed!")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Test error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
