"""Check the actual balance and position situation."""
import os
from supabase import create_client
from dotenv import load_dotenv
import json

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

print("="*80)
print("BALANCE AND POSITION CHECK")
print("="*80)

# 1. Config values
print("\n1. CONFIGURED VALUES:")
with open('configs/paper_trading_config_unified.json', 'r') as f:
    config = json.load(f)
    initial_balance = config['global_settings']['initial_balance']
    print(f"   Initial Balance: ${initial_balance:,.2f}")

# 2. Count actual positions
print("\n2. ACTUAL POSITIONS IN DATABASE:")
all_trades = supabase.table('paper_trades').select('trade_group_id, side, symbol, price, amount, strategy_name').execute()

if all_trades.data:
    # Group by trade_group_id
    groups = {}
    for trade in all_trades.data:
        group_id = trade['trade_group_id']
        if group_id not in groups:
            groups[group_id] = {'buys': [], 'sells': [], 'strategy': trade.get('strategy_name', 'unknown')}
        
        if trade['side'] == 'BUY':
            groups[group_id]['buys'].append(trade)
        else:
            groups[group_id]['sells'].append(trade)
    
    # Count open positions by strategy
    open_by_strategy = {'DCA': 0, 'CHANNEL': 0, 'SWING': 0}
    total_open = 0
    total_value = 0
    
    for group_id, group in groups.items():
        if len(group['buys']) > 0 and len(group['sells']) == 0:
            total_open += 1
            strategy = group['buys'][0].get('strategy_name', 'unknown')
            if strategy in open_by_strategy:
                open_by_strategy[strategy] += 1
            
            # Calculate position value
            for buy in group['buys']:
                total_value += buy['price'] * buy['amount']
    
    print(f"   Total Open Positions: {total_open}")
    print(f"   - DCA: {open_by_strategy['DCA']}")
    print(f"   - CHANNEL: {open_by_strategy['CHANNEL']}")
    print(f"   - SWING: {open_by_strategy['SWING']}")
    print(f"   Total Value Locked: ${total_value:,.2f}")
    
    # 3. Calculate expected free balance
    print("\n3. BALANCE CALCULATION:")
    print(f"   Initial: ${initial_balance:,.2f}")
    print(f"   In Positions: ${total_value:,.2f}")
    expected_free = initial_balance - total_value
    print(f"   Expected Free Balance: ${expected_free:,.2f}")
    
    # 4. Check why system thinks it has only 2 positions
    print("\n4. SYSTEM SYNC ISSUE:")
    print(f"   System thinks: 2 open positions, $1,815 balance")
    print(f"   Reality: {total_open} open positions")
    print(f"   ❌ MAJOR SYNC PROBLEM - System is using wrong position count!")
    
    if total_open > 90:
        print(f"\n   ⚠️ With {total_open} positions, you're using ${total_open * 50:,.2f}")
        print(f"   This may be why no new trades are opening")

# 5. Check paper_performance table
print("\n5. PAPER_PERFORMANCE TABLE:")
try:
    response = supabase.table('paper_performance').select('*').limit(1).execute()
    if response.data:
        perf = response.data[0]
        print(f"   Total P&L: ${perf.get('total_pnl', 0):,.2f}")
        print(f"   Balance stored: ${perf.get('balance', 0):,.2f}")
except Exception as e:
    print(f"   Error accessing table: {e}")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print("The system is NOT properly tracking open positions!")
print("It needs to resync with the database to get correct counts.")
