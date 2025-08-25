#!/usr/bin/env python3
"""Test script to verify threshold updates are working correctly"""

import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from configs.paper_trading_config import PAPER_TRADING_CONFIG
from src.strategies.simple_rules import SimpleRules
from loguru import logger


def test_threshold_loading():
    """Test that SimpleRules loads thresholds from config correctly"""

    # Create config dict like run_paper_trading_simple.py does
    config = {
        "ml_enabled": False,
        "shadow_enabled": False,
        "base_position_usd": 50.0,
        "max_open_positions": PAPER_TRADING_CONFIG.get("max_positions", 30),
        # Detection thresholds from central config
        "dca_drop_threshold": PAPER_TRADING_CONFIG["strategies"]["DCA"].get(
            "drop_threshold", -4.0
        ),
        "swing_breakout_threshold": PAPER_TRADING_CONFIG["strategies"]["SWING"].get(
            "breakout_threshold", 1.015
        ),
        "channel_position_threshold": PAPER_TRADING_CONFIG["strategies"]["CHANNEL"].get(
            "buy_zone", 0.15
        ),
        # Volume and other thresholds
        "swing_volume_surge": PAPER_TRADING_CONFIG["strategies"]["SWING"].get(
            "volume_surge", 1.5
        ),
        "channel_touches": PAPER_TRADING_CONFIG["strategies"]["CHANNEL"].get(
            "channel_touches", 3
        ),
        "min_confidence": 0.45,
        "scan_interval": 60,
        "position_size": 50.0,
        "max_position_duration_hours": 72,
    }

    # Initialize SimpleRules with config
    simple_rules = SimpleRules(config)

    print("\n" + "=" * 60)
    print("THRESHOLD VERIFICATION TEST")
    print("=" * 60)

    print("\n📋 Configuration Values from paper_trading_config.py:")
    print(
        f"  DCA drop_threshold: {PAPER_TRADING_CONFIG['strategies']['DCA']['drop_threshold']}%"
    )
    print(
        f"  SWING breakout_threshold: {PAPER_TRADING_CONFIG['strategies']['SWING']['breakout_threshold']}"
    )
    print(
        f"  SWING volume_surge: {PAPER_TRADING_CONFIG['strategies']['SWING']['volume_surge']}x"
    )
    print(
        f"  CHANNEL buy_zone: {PAPER_TRADING_CONFIG['strategies']['CHANNEL']['buy_zone']}"
    )
    print(
        f"  CHANNEL touches: {PAPER_TRADING_CONFIG['strategies']['CHANNEL']['channel_touches']}"
    )

    print("\n✅ SimpleRules Loaded Values:")
    print(f"  DCA drop_threshold: {simple_rules.dca_drop_threshold}%")
    print(f"  SWING breakout_threshold: {simple_rules.swing_breakout_threshold}")
    print(f"  SWING volume_surge: {simple_rules.swing_volume_surge}x")
    print(f"  CHANNEL position_threshold: {simple_rules.channel_position_threshold}")
    print(f"  CHANNEL touches: {simple_rules.channel_touches}")

    print("\n🔍 Verification Results:")

    # Verify DCA
    dca_match = (
        simple_rules.dca_drop_threshold
        == PAPER_TRADING_CONFIG["strategies"]["DCA"]["drop_threshold"]
    )
    print(f"  DCA: {'✅ MATCH' if dca_match else '❌ MISMATCH'}")

    # Verify SWING
    swing_breakout_match = (
        simple_rules.swing_breakout_threshold
        == PAPER_TRADING_CONFIG["strategies"]["SWING"]["breakout_threshold"]
    )
    swing_volume_match = (
        simple_rules.swing_volume_surge
        == PAPER_TRADING_CONFIG["strategies"]["SWING"]["volume_surge"]
    )
    print(f"  SWING breakout: {'✅ MATCH' if swing_breakout_match else '❌ MISMATCH'}")
    print(f"  SWING volume: {'✅ MATCH' if swing_volume_match else '❌ MISMATCH'}")

    # Verify CHANNEL
    channel_position_match = (
        simple_rules.channel_position_threshold
        == PAPER_TRADING_CONFIG["strategies"]["CHANNEL"]["buy_zone"]
    )
    channel_touches_match = (
        simple_rules.channel_touches
        == PAPER_TRADING_CONFIG["strategies"]["CHANNEL"]["channel_touches"]
    )
    print(
        f"  CHANNEL position: {'✅ MATCH' if channel_position_match else '❌ MISMATCH'}"
    )
    print(f"  CHANNEL touches: {'✅ MATCH' if channel_touches_match else '❌ MISMATCH'}")

    all_match = all(
        [
            dca_match,
            swing_breakout_match,
            swing_volume_match,
            channel_position_match,
            channel_touches_match,
        ]
    )

    print("\n" + "=" * 60)
    if all_match:
        print("✅ ALL THRESHOLDS MATCH! Configuration is unified.")
    else:
        print("❌ THRESHOLD MISMATCH DETECTED! Check configuration.")
    print("=" * 60)

    print("\n📊 Expected Strategy Behavior with These Thresholds:")
    print(
        f"  DCA: Will trigger when price drops {simple_rules.dca_drop_threshold}% from recent high"
    )
    print(
        f"  SWING: Will trigger on {(simple_rules.swing_breakout_threshold - 1) * 100:.1f}% breakout with {simple_rules.swing_volume_surge}x volume"
    )
    print(
        f"  CHANNEL: Will trigger when price is in bottom {simple_rules.channel_position_threshold * 100:.0f}% of range"
    )
    print()


if __name__ == "__main__":
    test_threshold_loading()
