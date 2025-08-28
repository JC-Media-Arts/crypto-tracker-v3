#!/usr/bin/env python3
"""
Debug config loading to see why exit params aren't matching
"""

import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.config_loader import ConfigLoader


def main():
    # Initialize config loader
    config_loader = ConfigLoader()
    
    # Test symbols from the dashboard
    test_symbols = [
        ("STRK", "CHANNEL", "mid_cap"),
        ("DASH", "CHANNEL", "mid_cap"),
        ("SNX", "CHANNEL", "mid_cap"),
        ("MOG", "CHANNEL", "memecoin"),
        ("WIF", "CHANNEL", "memecoin"),
    ]
    
    print("=" * 80)
    print("CONFIG LOADING DEBUG")
    print("=" * 80)
    
    # Check config version
    config = config_loader.load()
    print(f"\nConfig version: {config.get('version', 'unknown')}")
    print(f"Config path: {config_loader.config_path}")
    print(f"Config last updated: {config.get('last_updated', 'unknown')}")
    
    print("\n" + "-" * 40)
    print("TESTING GET_EXIT_PARAMS:")
    print("-" * 40)
    
    for symbol, strategy, expected_tier in test_symbols:
        # Get tier
        actual_tier = config_loader.get_tier_config(symbol)
        
        # Get exit params
        exit_params = config_loader.get_exit_params(strategy, symbol)
        
        print(f"\n{symbol} ({strategy}):")
        print(f"  Expected tier: {expected_tier}")
        print(f"  Actual tier: {actual_tier}")
        print(f"  Exit params returned:")
        print(f"    Take Profit: {exit_params['take_profit'] * 100:.1f}%")
        print(f"    Stop Loss: {exit_params['stop_loss'] * 100:.1f}%")
        
        # Check if matches expected
        if actual_tier != expected_tier:
            print(f"  ⚠️  TIER MISMATCH!")
        
        # Get expected exits directly from config
        strategy_config = config_loader.get_strategy_config(strategy)
        expected_exits = strategy_config.get("exits_by_tier", {}).get(expected_tier, {})
        if expected_exits:
            expected_tp = expected_exits.get("take_profit", 0) * 100
            expected_sl = expected_exits.get("stop_loss", 0) * 100
            actual_tp = exit_params['take_profit'] * 100
            actual_sl = exit_params['stop_loss'] * 100
            
            if abs(actual_tp - expected_tp) > 0.1 or abs(actual_sl - expected_sl) > 0.1:
                print(f"  ⚠️  EXIT PARAMS MISMATCH!")
                print(f"    Expected: TP={expected_tp:.1f}%, SL={expected_sl:.1f}%")
    
    # Debug the actual config structure
    print("\n" + "=" * 80)
    print("CHANNEL STRATEGY CONFIG:")
    print("-" * 40)
    channel_config = config_loader.get_strategy_config("CHANNEL")
    print(f"Enabled: {channel_config.get('enabled', False)}")
    print("\nExits by tier:")
    exits_by_tier = channel_config.get("exits_by_tier", {})
    for tier, exits in exits_by_tier.items():
        tp = exits.get("take_profit", 0) * 100
        sl = exits.get("stop_loss", 0) * 100
        print(f"  {tier}: TP={tp:.1f}%, SL={sl:.1f}%")


if __name__ == "__main__":
    main()
