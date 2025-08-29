"""Diagnose the balance and position count discrepancies."""
import os
from datetime import datetime, timezone
from supabase import create_client
from dotenv import load_dotenv
import json

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

print("="*80)
print("DIAGNOSING BALANCE AND POSITION ISSUES")
print("="*80)

# 1. Check config
print("\n1. CONFIGURATION:")
with open('configs/paper_trading_config_unified.json', 'r') as f:
    config = json.load(f)
    print(f"   Initial Balance (config): ${config['global_settings']['initial_balance']:,.2f}")
    print(f"   Position Size: ${config['position_management']['position_sizing']['sizing_modes']['fixed_dollar']['amount']}")
    print(f"   Max Positions: {config['position_management']['max_positions_total']}")

# 2. Check paper_performance table (where balance is stored)
print("\n2. PAPER_PERFORMANCE TABLE:")
response = supabase.table('paper_performance').select('*').order('created_at', desc=True).limit(1).execute()

if response.data:
    perf = response.data[0]
    print(f"   Total P&L: ${perf.get('total_pnl', 0):,.2f}")
    print(f"   Balance: ${perf.get('balance', 0):,.2f}")
    print(f"   Initial Balance: ${perf.get('initial_balance', 'NOT STORED'):,.2f}" if 'initial_balance' in perf else "   Initial Balance: NOT STORED IN TABLE")
    print(f"   Win Rate: {perf.get('win_rate', 0):.1%}")
    print(f"   Total Trades: {perf.get('total_trades', 0)}")

# 3. Count actual open positions
print("\n3. ACTUAL OPEN POSITIONS:")
response = supabase.table('paper_trades').select('trade_group_id, side, symbol, price, amount').execute()

if response.data:
    # Group by trade_group_id
    groups = {}
    for trade in response.data:
        group_id = trade['trade_group_id']
        if group_id not in groups:
            groups[group_id] = {'buys': [], 'sells': []}
        
        if trade['side'] == 'BUY':
            groups[group_id]['buys'].append(trade)
        else:
            groups[group_id]['sells'].append(trade)
    
    # Count open positions
    open_positions = []
    total_position_value = 0
    
    for group_id, group in groups.items():
        if len(group['buys']) > 0 and len(group['sells']) == 0:
            # This is an open position
            for buy in group['buys']:
                position_value = buy['price'] * buy['amount']
                total_position_value += position_value
                open_positions.append({
                    'symbol': buy['symbol'],
                    'value': position_value
                })
    
    print(f"   Open Positions: {len(open_positions)}")
    print(f"   Total Value in Positions: ${total_position_value:,.2f}")
    
    # Show position distribution
    if len(open_positions) > 0:
        avg_position = total_position_value / len(open_positions)
        print(f"   Average Position Size: ${avg_position:,.2f}")
        
        # If average is ~$50, positions are correct
        if 45 <= avg_position <= 55:
            print("   ✅ Position sizes look correct (~$50 each)")
        else:
            print(f"   ⚠️ Position sizes don't match expected $50")

# 4. Calculate what balance SHOULD be
print("\n4. BALANCE CALCULATION:")
print(f"   If initial balance = $10,000")
print(f"   And {len(open_positions)} positions × $50 = ${len(open_positions) * 50:,.2f} in positions")
print(f"   Free balance should be: ${10000 - (len(open_positions) * 50):,.2f}")

# 5. Check for state file
print("\n5. STATE PERSISTENCE:")
if os.path.exists('data/paper_trading_state.json'):
    with open('data/paper_trading_state.json', 'r') as f:
        state = json.load(f)
        print(f"   State file exists!")
        print(f"   Initial balance in state: ${state.get('initial_balance', 'NOT SET')}")
        print(f"   Current balance in state: ${state.get('balance', 'NOT SET')}")
else:
    print("   No state file found")

print("\n" + "="*80)
print("DIAGNOSIS COMPLETE")
print("="*80)
