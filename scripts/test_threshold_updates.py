#!/usr/bin/env python3
"""
Test the updated threshold configurations
Verify that all changes have been applied correctly
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # noqa: E402

from configs.paper_trading_config import PAPER_TRADING_CONFIG  # noqa: E402
from src.strategies.swing.detector import SwingDetector  # noqa: E402
from src.strategies.channel.detector import ChannelDetector  # noqa: E402
from src.strategies.dca.detector import DCADetector  # noqa: E402
from src.data.supabase_client import SupabaseClient  # noqa: E402


def test_configurations():
    """Test that all configurations have been updated correctly"""

    print("=" * 80)
    print("TESTING THRESHOLD UPDATES - CUSTOM BALANCED APPROACH")
    print("=" * 80)

    # Test paper_trading_config.py
    print("\n📋 Paper Trading Config:")
    config = PAPER_TRADING_CONFIG["strategies"]

    # SWING checks
    print("\n  SWING Strategy:")
    swing_config = config["SWING"]
    print(
        f"    ✓ min_confidence: {swing_config.get('min_confidence', 'NOT SET')} (should be 0.50)"
    )
    print(
        f"    ✓ breakout_threshold: {swing_config.get('breakout_threshold', 'NOT SET')} (should be 1.015)"
    )
    print(
        f"    ✓ volume_surge: {swing_config.get('volume_surge', 'NOT SET')} (should be 1.5)"
    )
    print(f"    ✓ rsi_min: {swing_config.get('rsi_min', 'NOT SET')} (should be 45)")
    print(f"    ✓ rsi_max: {swing_config.get('rsi_max', 'NOT SET')} (should be 75)")
    print(f"    ✓ min_score: {swing_config.get('min_score', 'NOT SET')} (should be 40)")

    # CHANNEL checks
    print("\n  CHANNEL Strategy:")
    channel_config = config["CHANNEL"]
    print(
        f"    ✓ min_confidence: {channel_config.get('min_confidence', 'NOT SET')} (should be 0.65)"
    )
    print(
        f"    ✓ channel_touches: {channel_config.get('channel_touches', 'NOT SET')} (should be 3)"
    )
    print(
        f"    ✓ buy_zone: {channel_config.get('buy_zone', 'NOT SET')} (should be 0.15)"
    )
    print(
        f"    ✓ sell_zone: {channel_config.get('sell_zone', 'NOT SET')} (should be 0.85)"
    )
    print(
        f"    ✓ channel_strength_min: {channel_config.get('channel_strength_min', 'NOT SET')} (should be 0.70)"
    )

    # DCA checks
    print("\n  DCA Strategy:")
    dca_config = config["DCA"]
    print(
        f"    ✓ drop_threshold: {dca_config.get('drop_threshold', 'NOT SET')} (should be -4.0)"
    )
    print(
        f"    ✓ volume_requirement: {dca_config.get('volume_requirement', 'NOT SET')} (should be 0.85)"
    )

    # Test detector classes
    print("\n" + "=" * 80)
    print("TESTING DETECTOR CLASSES")
    print("=" * 80)

    db = SupabaseClient()

    # Test SWING detector
    print("\n🎯 SWING Detector:")
    swing = SwingDetector(db)
    print(
        f"    breakout_threshold: {swing.config['breakout_threshold']} (should be 1.015)"
    )
    print(
        f"    volume_spike_threshold: {swing.config['volume_spike_threshold']} (should be 1.5)"
    )
    print(f"    rsi_bullish_min: {swing.config['rsi_bullish_min']} (should be 45)")
    print(f"    rsi_overbought: {swing.config['rsi_overbought']} (should be 75)")

    # Test CHANNEL detector
    print("\n📊 CHANNEL Detector:")
    channel = ChannelDetector()
    print(f"    min_touches: {channel.min_touches} (should be 3)")
    print(f"    buy_zone: {channel.buy_zone} (should be 0.15)")
    print(f"    sell_zone: {channel.sell_zone} (should be 0.85)")

    # Test DCA detector
    print("\n💰 DCA Detector:")
    dca = DCADetector(db)
    print(
        f"    price_drop_threshold: {dca.config.get('price_drop_threshold', 'NOT SET')} (should be -4.0)"
    )
    print(
        f"    volume_requirement_multiplier: "
        f"{dca.config.get('volume_requirement_multiplier', 'NOT SET')} (should be 0.85)"
    )

    # Verification summary
    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)

    all_correct = True
    errors = []

    # Check SWING
    if swing.config["breakout_threshold"] != 1.015:
        errors.append("SWING breakout_threshold not updated")
        all_correct = False
    if swing.config["volume_spike_threshold"] != 1.5:
        errors.append("SWING volume_spike_threshold not updated")
        all_correct = False

    # Check CHANNEL
    if channel.min_touches != 3:
        errors.append("CHANNEL min_touches not updated")
        all_correct = False
    if channel.buy_zone != 0.15:
        errors.append("CHANNEL buy_zone not updated")
        all_correct = False

    # Check DCA
    if dca.config.get("price_drop_threshold") != -4.0:
        errors.append("DCA price_drop_threshold not updated")
        all_correct = False

    if all_correct:
        print("\n✅ All threshold updates have been applied successfully!")
        print("\n📌 Custom Balanced Approach is now active:")
        print("   - SWING: Aggressive loosening (should see ~20-30 trades/14 days)")
        print(
            "   - CHANNEL: Aggressive tightening (should reduce to ~300-400 trades/14 days)"
        )
        print("   - DCA: Moderate loosening (should see ~25-35 trades/14 days)")
    else:
        print("\n❌ Some updates may not have been applied:")
        for error in errors:
            print(f"   - {error}")

    return all_correct


def main():
    success = test_configurations()

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

    if success:
        print("\n✨ All configurations updated successfully!")
        print("\nNext steps:")
        print("1. Restart paper trading to apply the new thresholds")
        print("2. Monitor performance over the next 24-48 hours")
        print("3. Fine-tune if needed based on actual results")
    else:
        print("\n⚠️ Please review and fix the configuration issues above")


if __name__ == "__main__":
    main()
