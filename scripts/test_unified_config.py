#!/usr/bin/env python3
"""
Test script for the unified configuration system.
Tests that all components can load and use the new configuration properly.
"""

import sys
from pathlib import Path
import json
from loguru import logger

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config.config_loader import ConfigLoader
from src.trading.simple_paper_trader_v2 import SimplePaperTraderV2


def test_config_loader():
    """Test the ConfigLoader functionality"""
    print("\n" + "=" * 50)
    print("Testing ConfigLoader...")
    print("=" * 50)

    try:
        # Test singleton pattern
        loader1 = ConfigLoader()
        loader2 = ConfigLoader()
        assert loader1 is loader2, "❌ Singleton pattern not working"
        print("✅ Singleton pattern working")

        # Test loading config
        config = loader1.load()
        assert config is not None, "❌ Config is None"
        print("✅ Config loaded successfully")

        # Test version and structure
        assert "version" in config, "❌ Missing version field"
        print(f"✅ Config version: {config['version']}")

        # Test key sections exist
        required_sections = [
            "global_settings",
            "position_management",
            "strategies",
            "market_protection",
            "market_cap_tiers",
            "fees_and_slippage",
        ]
        for section in required_sections:
            assert section in config, f"❌ Missing section: {section}"
        print(f"✅ All {len(required_sections)} required sections present")

        # Test kill switch
        is_enabled = loader1.is_trading_enabled()
        print(f"✅ Trading enabled: {is_enabled}")

        # Test get method with dot notation
        initial_balance = loader1.get("global_settings.initial_balance")
        assert initial_balance is not None, "❌ Could not get initial_balance"
        print(f"✅ Initial balance: ${initial_balance:,.2f}")

        # Test strategy config
        dca_config = loader1.get_strategy_config("DCA")
        assert dca_config is not None, "❌ Could not get DCA config"
        assert "enabled" in dca_config, "❌ DCA config missing 'enabled' field"
        print(f"✅ DCA strategy enabled: {dca_config['enabled']}")

        # Test tier detection
        btc_tier = loader1.get_tier_config("BTC")
        assert btc_tier == "large_cap", f"❌ BTC tier wrong: {btc_tier}"
        print(f"✅ BTC tier: {btc_tier}")

        pepe_tier = loader1.get_tier_config("PEPE")
        assert pepe_tier == "memecoin", f"❌ PEPE tier wrong: {pepe_tier}"
        print(f"✅ PEPE tier: {pepe_tier}")

        # Test exit params
        dca_exits = loader1.get_exit_params("DCA", "BTC")
        assert "take_profit" in dca_exits, "❌ Missing take_profit in exits"
        assert "stop_loss" in dca_exits, "❌ Missing stop_loss in exits"
        print(
            f"✅ DCA/BTC exits: TP={dca_exits['take_profit']*100:.1f}%, SL={dca_exits['stop_loss']*100:.1f}%"
        )

        print("\n✅ ConfigLoader tests PASSED!")
        return True

    except Exception as e:
        print(f"\n❌ ConfigLoader test FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_paper_trader_integration():
    """Test SimplePaperTraderV2 with new config"""
    print("\n" + "=" * 50)
    print("Testing SimplePaperTraderV2 Integration...")
    print("=" * 50)

    try:
        # Initialize paper trader (without database)
        trader = SimplePaperTraderV2()

        # Check if config loaded
        assert trader.config is not None, "❌ Config not loaded in trader"
        print("✅ Config loaded in trader")

        # Check initial balance from config
        print(f"✅ Initial balance: ${trader.initial_balance:,.2f}")

        # Check position limits
        print(f"✅ Max positions total: {trader.max_positions}")
        print(f"✅ Max positions per strategy: {trader.max_positions_per_strategy}")

        # Test market cap tier detection
        btc_tier = trader.get_market_cap_tier("BTC")
        assert btc_tier == "large_cap", f"❌ BTC tier wrong in trader: {btc_tier}"
        print(f"✅ BTC tier detection working: {btc_tier}")

        # Test adaptive exits
        dca_exits = trader.get_adaptive_exits("BTC", "DCA")
        assert "take_profit" in dca_exits, "❌ Missing take_profit in trader exits"
        print(f"✅ DCA/BTC exits working: TP={dca_exits['take_profit']*100:.1f}%")

        # Test fee loading
        print(f"✅ Base fee rate: {trader.base_fee_rate*100:.2f}%")

        print("\n✅ SimplePaperTraderV2 integration tests PASSED!")
        return True

    except Exception as e:
        print(f"\n❌ SimplePaperTraderV2 test FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_config_values():
    """Test specific configuration values"""
    print("\n" + "=" * 50)
    print("Testing Configuration Values...")
    print("=" * 50)

    loader = ConfigLoader()
    config = loader.config

    # Global settings
    print("\n📊 Global Settings:")
    print(f"  Trading enabled: {config['global_settings']['trading_enabled']}")
    print(f"  Initial balance: ${config['global_settings']['initial_balance']:,.2f}")
    print(
        f"  Trading cycle: {config['global_settings']['trading_cycle_seconds']} seconds"
    )

    # Position management
    print("\n💰 Position Management:")
    print(
        f"  Max positions total: {config['position_management']['max_positions_total']}"
    )
    print(
        f"  Max per strategy: {config['position_management']['max_positions_per_strategy']}"
    )
    print(
        f"  Max per symbol: {config['position_management']['max_positions_per_symbol']}"
    )
    print(
        f"  Base position size: ${config['position_management']['position_sizing']['base_position_size_usd']}"
    )
    print(f"  Max hold hours: {config['position_management']['max_hold_hours']}")

    # Strategy status
    print("\n🎯 Strategy Status:")
    for strategy in ["DCA", "SWING", "CHANNEL"]:
        enabled = config["strategies"][strategy]["enabled"]
        status = "✅ ENABLED" if enabled else "❌ DISABLED"
        print(f"  {strategy}: {status}")

    # Market protection
    print("\n🛡️ Market Protection:")
    protection = config["market_protection"]
    print(f"  Protection enabled: {protection['enabled']}")
    print(
        f"  Panic threshold: {protection['enhanced_regime']['panic_threshold']*100:.0f}%"
    )
    print(f"  Trade limiter: {protection['trade_limiter']['enabled']}")
    print(f"  Stop widening: {protection['stop_widening']['enabled']}")

    # Fees
    print("\n💸 Fees & Slippage:")
    print(
        f"  Kraken taker fee: {config['fees_and_slippage']['exchange_fees']['kraken_taker']*100:.2f}%"
    )
    print(
        f"  Large cap slippage: {config['fees_and_slippage']['slippage_by_tier']['large_cap']*100:.2f}%"
    )

    return True


def main():
    """Run all tests"""
    print("\n" + "🚀" * 25)
    print("UNIFIED CONFIGURATION SYSTEM TEST")
    print("🚀" * 25)

    all_passed = True

    # Run tests
    all_passed = test_config_loader() and all_passed
    all_passed = test_paper_trader_integration() and all_passed
    all_passed = test_config_values() and all_passed

    # Summary
    print("\n" + "=" * 50)
    if all_passed:
        print("✅ ✅ ✅ ALL TESTS PASSED! ✅ ✅ ✅")
        print("\nThe unified configuration system is working correctly!")
        print("You can now proceed with updating the remaining scripts.")
    else:
        print("❌ ❌ ❌ SOME TESTS FAILED ❌ ❌ ❌")
        print("\nPlease fix the issues before proceeding.")
    print("=" * 50)


if __name__ == "__main__":
    main()
