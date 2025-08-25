#!/usr/bin/env python3
"""
Test script for PANIC regime Slack alerts
"""
import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategies.regime_detector import RegimeDetector, MarketRegime
from loguru import logger


def test_panic_alerts():
    """Test PANIC alert functionality"""

    print("\n" + "=" * 60)
    print("🧪 TESTING PANIC REGIME SLACK ALERTS")
    print("=" * 60)

    # Check if Slack webhook is configured
    webhook = os.getenv("SLACK_WEBHOOK_TRADES")
    if not webhook:
        print("\n⚠️  WARNING: SLACK_WEBHOOK_TRADES not configured")
        print("   Set the environment variable to enable Slack alerts:")
        print("   export SLACK_WEBHOOK_TRADES='your-webhook-url'")
        print("\n   Continuing with test (alerts will be logged only)...")
    else:
        print(f"\n✅ Slack webhook configured for #trades channel")

    # Initialize regime detector
    print("\n📊 Initializing Regime Detector...")
    detector = RegimeDetector(enabled=True)

    # Simulate normal market conditions
    print("\n📈 Simulating normal market conditions...")
    btc_price = 50000
    for i in range(60):
        detector.update_btc_price(btc_price)
        btc_price *= 1.0001  # Slight increase

    regime = detector.get_market_regime()
    print(f"   Current regime: {regime.value}")
    assert regime == MarketRegime.NORMAL, "Should be NORMAL regime"

    # Simulate flash crash (PANIC conditions)
    print("\n📉 Simulating flash crash...")
    print("   Dropping BTC by 12% in 1 hour...")

    # Drop price by 12% over next 60 minutes
    for i in range(60):
        btc_price *= 0.998  # ~12% drop over 60 iterations
        detector.update_btc_price(btc_price)

    # Check regime - should trigger PANIC
    regime = detector.get_market_regime()
    print(f"\n🚨 New regime: {regime.value}")

    if regime == MarketRegime.PANIC:
        print("✅ PANIC regime correctly triggered!")
        print("   Alert should have been sent to Slack (if configured)")
    else:
        print(f"❌ Expected PANIC but got {regime.value}")

    # Get regime stats
    stats = detector.get_regime_stats()
    print(f"\n📊 Regime Statistics:")
    print(f"   BTC 1h change: {stats.get('btc_1h_change', 0):.2f}%")
    print(f"   BTC 24h change: {stats.get('btc_24h_change', 0):.2f}%")
    print(f"   Volatility (24h): {stats.get('volatility_24h', 0):.2f}%")
    print(f"   Protection Enabled: {stats.get('protection_enabled', False)}")

    # Test high volatility (should disable CHANNEL)
    print("\n🌊 Testing high volatility scenario...")
    print("   Creating 10% volatility conditions...")

    # Reset with volatile price movements
    detector = RegimeDetector(enabled=True)
    btc_price = 50000

    # Create volatility by alternating price movements
    for i in range(120):
        if i % 4 < 2:
            btc_price *= 1.005  # Up 0.5%
        else:
            btc_price *= 0.995  # Down 0.5%
        detector.update_btc_price(btc_price)

    # Check if CHANNEL should be disabled
    should_disable = detector.should_disable_strategy("CHANNEL")
    volatility = detector.calculate_volatility(24)

    print(f"   Current volatility: {volatility:.2f}%")
    print(f"   CHANNEL disabled: {should_disable}")

    if should_disable and volatility >= 8.0:
        print("✅ CHANNEL strategy correctly disabled at high volatility!")
        print("   Alert should have been sent to Slack (if configured)")

    print("\n" + "=" * 60)
    print("✅ PANIC ALERT TEST COMPLETE")
    print("=" * 60)

    if webhook:
        print("\n📬 Check your #trades Slack channel for the test alerts!")
    else:
        print("\n⚠️  No alerts sent (SLACK_WEBHOOK_TRADES not configured)")
    print()


if __name__ == "__main__":
    test_panic_alerts()
