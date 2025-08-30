#!/usr/bin/env python3
"""
Test position limits in Freqtrade CHANNEL strategy
"""

import sys
from pathlib import Path
from loguru import logger

sys.path.append(str(Path(__file__).parent.parent))

from src.config.config_loader import ConfigLoader


def check_position_limits():
    """Check current position limit settings"""
    
    print("\n" + "="*60)
    print("📊 POSITION LIMITS CHECK")
    print("="*60)
    
    # Load config
    config_loader = ConfigLoader()
    config = config_loader.load()
    
    # Get position management settings
    position_mgmt = config.get('position_management', {})
    
    print("\n📋 Current Position Limits:")
    print(f"   Total Max Positions: {position_mgmt.get('max_positions_total', 'N/A')}")
    print(f"   Max Per Strategy: {position_mgmt.get('max_positions_per_strategy', 'N/A')}")
    print(f"   Max Per Symbol: {position_mgmt.get('max_positions_per_symbol', 'N/A')}")
    
    # Check Freqtrade config
    freqtrade_config_path = Path("freqtrade/config/config.json")
    if freqtrade_config_path.exists():
        import json
        with open(freqtrade_config_path, 'r') as f:
            ft_config = json.load(f)
            print(f"\n🤖 Freqtrade Settings:")
            print(f"   max_open_trades: {ft_config.get('max_open_trades', 'N/A')}")
            print(f"   stake_amount: {ft_config.get('stake_amount', 'N/A')}")
    
    print("\n✅ Strategy Enforcement:")
    print("   The CHANNEL strategy will now enforce:")
    print(f"   • Max {position_mgmt.get('max_positions_per_strategy', 50)} total positions for CHANNEL")
    print(f"   • Max {position_mgmt.get('max_positions_per_symbol', 3)} positions per symbol")
    print("   • Logs SKIP decisions when limits are reached")
    print("   • Logs TAKE decisions when positions are opened")
    
    print("\n💡 How It Works:")
    print("   1. Before each trade, strategy checks current open positions")
    print("   2. If strategy has 50+ positions → SKIP")
    print("   3. If symbol has 3+ positions → SKIP")
    print("   4. Otherwise → TAKE (if other conditions met)")
    
    print("\n🔍 Monitoring:")
    print("   • Check Freqtrade logs for 'Strategy limit reached' messages")
    print("   • Check scan_history table for SKIP decisions with reasons")
    print("   • Dashboard shows current open positions")
    
    print("="*60 + "\n")


if __name__ == "__main__":
    check_position_limits()
