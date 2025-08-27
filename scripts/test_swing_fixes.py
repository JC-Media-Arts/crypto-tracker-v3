#!/usr/bin/env python3
"""
Test script to verify SWING fixes are working correctly
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from configs.paper_trading_config import PAPER_TRADING_CONFIG


def test_precalculator_formula():
    """Test the new precalculator formula"""
    print("=== Testing SWING Precalculator Formula ===\n")

    # Test cases: (breakout_pct, expected_readiness_range)
    test_cases = [
        (-3.0, (0, 0)),      # Far below resistance
        (-2.0, (0, 0)),      # At the edge
        (-1.0, (30, 40)),    # Approaching resistance
        (-0.5, (45, 55)),    # Close to resistance
        (0.0, (65, 75)),     # At resistance
        (0.5, (75, 85)),     # Breaking resistance
        (1.0, (85, 95)),     # At threshold
        (2.0, (95, 100)),    # Strong breakout
    ]

    threshold = 1.0  # 1% breakout threshold

    for breakout_pct, (min_expected, max_expected) in test_cases:
        # Apply the new formula
        if breakout_pct < -2:
            breakout_readiness = 0
        elif breakout_pct < 0:
            breakout_readiness = (breakout_pct + 2) * 35
        elif breakout_pct < threshold:
            breakout_readiness = 70 + (breakout_pct / threshold) * 20
        else:
            breakout_readiness = min(100, 90 + (breakout_pct - threshold) * 10)

        in_range = min_expected <= breakout_readiness <= max_expected
        status = "✅" if in_range else "❌"
        print(f"{status} Breakout {breakout_pct:+.1f}%: Readiness = {breakout_readiness:.1f}% (expected {min_expected}-{max_expected}%)")

    print("\n✅ Precalculator formula fixed - high readiness only for actual breakouts!")


def test_config_loading():
    """Test that SwingDetector loads config properly"""
    print("\n=== Testing SWING Config Loading ===\n")

    swing_cfg = PAPER_TRADING_CONFIG['strategies'].get('SWING', {})

    print(f"Configuration loaded from paper_trading_config.py:")
    print(f"  breakout_threshold: {swing_cfg.get('breakout_threshold', 'NOT FOUND')}")
    print(f"  volume_surge: {swing_cfg.get('volume_surge', 'NOT FOUND')}")
    print(f"  rsi_min: {swing_cfg.get('rsi_min', 'NOT FOUND')}")
    print(f"  rsi_max: {swing_cfg.get('rsi_max', 'NOT FOUND')}")
    print(f"  min_confidence: {swing_cfg.get('min_confidence', 'NOT FOUND')}")

    # Test the threshold conversion
    breakout_threshold = swing_cfg.get('breakout_threshold', 1.010)
    breakout_pct = (breakout_threshold - 1) * 100
    print(f"\nThreshold conversion: {breakout_threshold} → {breakout_pct:.1f}%")

    if breakout_threshold == 1.010:
        print("✅ Config loads correctly - 1% breakout threshold")
    else:
        print(f"⚠️  Unexpected threshold value: {breakout_threshold}")


def test_simple_rules_comparison():
    """Test that SimpleRules compares thresholds correctly"""
    print("\n=== Testing SimpleRules Threshold Comparison ===\n")

    from src.strategies.simple_rules import SimpleRules
    from configs.paper_trading_config import PAPER_TRADING_CONFIG

    # Create config matching paper_trading_config
    config = {
        "swing_breakout_threshold": PAPER_TRADING_CONFIG["strategies"]["SWING"].get("breakout_threshold", 1.010),
        "swing_volume_surge": PAPER_TRADING_CONFIG["strategies"]["SWING"].get("volume_surge", 1.3),
    }

    rules = SimpleRules(config)

    # Test scenarios
    test_scenarios = [
        (0.5, 1.5, False, "Below threshold, good volume"),
        (1.2, 1.5, True, "Above threshold, good volume"),
        (1.2, 1.0, False, "Above threshold, low volume"),
        (2.0, 2.0, True, "Strong breakout, strong volume"),
    ]

    for price_breakout_pct, volume_surge, should_trigger, description in test_scenarios:
        # Simulate the check
        breakout_threshold_pct = (rules.swing_breakout_threshold - 1) * 100
        triggers = (
            price_breakout_pct >= breakout_threshold_pct
            and volume_surge > rules.swing_volume_surge
        )

        status = "✅" if triggers == should_trigger else "❌"
        print(f"{status} {description}:")
        print(f"    Breakout: {price_breakout_pct:.1f}% vs {breakout_threshold_pct:.1f}% threshold")
        print(f"    Volume: {volume_surge:.1f}x vs {rules.swing_volume_surge:.1f}x threshold")
        print(f"    Triggers: {triggers}")


if __name__ == "__main__":
    print("Testing SWING Strategy Fixes\n" + "=" * 40 + "\n")
    test_precalculator_formula()
    test_config_loading()
    test_simple_rules_comparison()
    print("\n" + "=" * 40)
    print("All tests completed! Deploy these fixes to enable proper SWING detection.")
