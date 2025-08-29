#!/usr/bin/env python3
"""
Test script to verify Freqtrade setup and CHANNEL strategy
"""

import os
import sys
import json
from datetime import datetime, timezone

# Add paths
sys.path.append(os.path.join(os.path.dirname(__file__), "user_data"))


def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")

    try:
        from config_bridge import ConfigBridge

        print("✓ ConfigBridge imported")
    except Exception as e:
        print(f"✗ ConfigBridge import failed: {e}")
        return False

    try:
        from scan_logger import ScanLogger

        print("✓ ScanLogger imported")
    except Exception as e:
        print(f"✗ ScanLogger import failed: {e}")
        return False

    try:
        from data.supabase_dataprovider import SupabaseDataProvider

        print("✓ SupabaseDataProvider imported")
    except Exception as e:
        print(f"✗ SupabaseDataProvider import failed: {e}")
        return False

    try:
        from strategies.ChannelStrategyV1 import ChannelStrategyV1

        print("✓ ChannelStrategyV1 imported")
    except Exception as e:
        print(f"✗ ChannelStrategyV1 import failed: {e}")
        return False

    return True


def test_config_bridge():
    """Test configuration bridge"""
    print("\nTesting ConfigBridge...")

    try:
        from config_bridge import ConfigBridge

        bridge = ConfigBridge()

        # Test loading thresholds
        thresholds = bridge.get_channel_thresholds()
        print(f"✓ Channel thresholds loaded: {thresholds}")

        # Test loading market cap tiers
        tiers = bridge.get_market_cap_tiers()
        print(f"✓ Market cap tiers loaded: {len(tiers)} tiers")

        # Test loading risk parameters
        risk = bridge.get_risk_parameters()
        print(f"✓ Risk parameters loaded: max_positions={risk['max_positions']}")

        return True

    except Exception as e:
        print(f"✗ ConfigBridge test failed: {e}")
        return False


def test_freqtrade_config():
    """Test Freqtrade configuration file"""
    print("\nTesting Freqtrade config...")

    config_path = os.path.join(os.path.dirname(__file__), "config", "config.json")

    try:
        with open(config_path, "r") as f:
            config = json.load(f)

        print(f"✓ Config loaded: {config['bot_name']}")
        print(f"✓ Strategy: {config['strategy']}")
        print(f"✓ Exchange: {config['exchange']['name']}")
        print(f"✓ Pairs: {len(config['exchange']['pair_whitelist'])} pairs")

        return True

    except Exception as e:
        print(f"✗ Config test failed: {e}")
        return False


def test_environment():
    """Test environment variables"""
    print("\nTesting environment...")

    required_vars = ["SUPABASE_URL", "SUPABASE_KEY"]
    missing = []

    for var in required_vars:
        if os.getenv(var):
            print(f"✓ {var} is set")
        else:
            print(f"✗ {var} is not set")
            missing.append(var)

    if missing:
        print(f"\nMissing environment variables: {', '.join(missing)}")
        print("Please set these in your .env file or environment")
        return False

    return True


def main():
    """Run all tests"""
    print("=" * 50)
    print("Freqtrade Setup Test")
    print("=" * 50)

    tests = [
        ("Imports", test_imports),
        ("Environment", test_environment),
        ("ConfigBridge", test_config_bridge),
        ("Freqtrade Config", test_freqtrade_config),
    ]

    results = []
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))

    print("\n" + "=" * 50)
    print("Test Results:")
    print("=" * 50)

    for name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{name}: {status}")

    all_passed = all(r for _, r in results)

    if all_passed:
        print("\n✅ All tests passed! Freqtrade setup is ready.")
        print("\nNext steps:")
        print("1. Set SUPABASE_URL and SUPABASE_KEY environment variables")
        print(
            "2. Run: freqtrade trade --config config/config.json --strategy ChannelStrategyV1"
        )
    else:
        print("\n❌ Some tests failed. Please fix the issues above.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
