#!/usr/bin/env python3
"""
Simple test to verify Freqtrade will trigger trades with SimpleChannelStrategy
"""

import os
import sys
import json
from datetime import datetime

print("🔍 FREQTRADE LOCAL TEST")
print("="*50)

# Check if we're in the right directory
if not os.path.exists("freqtrade/config/config.json"):
    print("❌ Error: Must run from crypto-tracker-v3 directory")
    sys.exit(1)

# Load and check config
with open("freqtrade/config/config.json", "r") as f:
    config = json.load(f)

print(f"✅ Config loaded")
print(f"   Strategy: {config.get('strategy', 'NOT SET')}")
print(f"   Pairs: {len(config['exchange']['pair_whitelist'])} pairs")
print(f"   Wallet: ${config.get('dry_run_wallet', 0):,}")
print(f"   Stake: ${config.get('stake_amount', 0)}")
print(f"   Max trades: {config.get('max_open_trades', 0)}")

# Check if strategy file exists
strategy_name = config.get('strategy', 'SimpleChannelStrategy')
strategy_file = f"freqtrade/user_data/strategies/{strategy_name}.py"

if os.path.exists(strategy_file):
    print(f"✅ Strategy file exists: {strategy_file}")
    
    # Read strategy and check thresholds
    with open(strategy_file, "r") as f:
        content = f.read()
        if "channel_entry_threshold = 0.70" in content:
            print("✅ Entry threshold: 0.70 (loosened)")
        elif "channel_entry_threshold = 0.35" in content:
            print("❌ Entry threshold: 0.35 (too strict!)")
        
        if "rsi_min = 20" in content:
            print("✅ RSI range: 20-80 (widened)")
        elif "rsi_min = 32" in content:
            print("❌ RSI range: 32-65 (too narrow!)")
            
        if "use_volume_filter = False" in content or "NO VOLUME REQUIREMENT" in content:
            print("✅ Volume filter: Disabled")
        else:
            print("⚠️  Volume filter: May be enabled")
else:
    print(f"❌ Strategy file not found: {strategy_file}")

print("\n" + "="*50)
print("QUICK START COMMANDS:")
print("="*50)
print("""
1. Test with existing venv (fastest):
   cd freqtrade
   source venv/bin/activate
   freqtrade trade --config config/config.json --strategy SimpleChannelStrategy

2. Test with full data sync:
   ./test_local_trading.sh

3. Monitor trades:
   cd freqtrade
   tail -f user_data/logs/freqtrade_local_test.log | grep -E "BUY|SELL|signal"

4. Check if trades are triggering:
   - Look for "Entry signal found" in logs
   - Check tradesv3.local_test.sqlite for trades
   - If no trades after 5 minutes, thresholds may still be too strict
""")

print("\n⚠️  IMPORTANT: The strategy should trigger trades within 2-3 minutes")
print("   If not, we need to loosen thresholds even more!")
