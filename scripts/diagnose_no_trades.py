"""Diagnose why no new trades are opening."""
import os
from datetime import datetime, timedelta, timezone
from supabase import create_client
from dotenv import load_dotenv
import pytz
import json

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

pst = pytz.timezone('America/Los_Angeles')
now_utc = datetime.now(timezone.utc)
now_pst = now_utc.astimezone(pst)

print("="*80)
print("DIAGNOSIS: Why No New Trades?")
print(f"Current Time: {now_pst.strftime('%Y-%m-%d %I:%M %p PST')}")
print("="*80)

# 1. Check last BUY trade
response = supabase.table('paper_trades').select('*').eq(
    'side', 'BUY'
).order('created_at', desc=True).limit(1).execute()

if response.data:
    last_buy = response.data[0]
    last_buy_utc = datetime.fromisoformat(last_buy['created_at'].replace('Z', '+00:00'))
    last_buy_pst = last_buy_utc.astimezone(pst)
    hours_since = (now_utc - last_buy_utc).total_seconds() / 3600
    
    print(f"\n1. LAST NEW POSITION:")
    print(f"   Time: {last_buy_pst.strftime('%m/%d %I:%M %p PST')} ({hours_since:.1f} hours ago)")
    print(f"   Symbol: {last_buy['symbol']}, Strategy: {last_buy['strategy_name']}")
    
    if hours_since > 24:
        print(f"   ⚠️ WARNING: No new positions in over 24 hours!")

# 2. Count open positions manually
print(f"\n2. OPEN POSITIONS COUNT:")

# Get all trades
all_trades = supabase.table('paper_trades').select('trade_group_id, side').execute()

if all_trades.data:
    # Group by trade_group_id
    groups = {}
    for trade in all_trades.data:
        group_id = trade['trade_group_id']
        if group_id not in groups:
            groups[group_id] = {'BUY': 0, 'SELL': 0}
        groups[group_id][trade['side']] += 1
    
    # Count open positions (groups with BUY but no SELL)
    open_positions = []
    for group_id, counts in groups.items():
        if counts['BUY'] > 0 and counts['SELL'] == 0:
            open_positions.append(group_id)
    
    print(f"   Open positions: {len(open_positions)}")
    
    # Check config limits
    with open('configs/paper_trading_config_unified.json', 'r') as f:
        config = json.load(f)
        max_total = config['position_management']['max_positions_total']
        max_per_strategy = config['position_management']['max_positions_per_strategy']
        
        print(f"   Max allowed: {max_total}")
        print(f"   Max per strategy: {max_per_strategy}")
        
        if len(open_positions) >= max_total:
            print(f"\n   🚫 AT POSITION LIMIT! This is why no new trades!")
            print(f"      Need to close {len(open_positions) - max_total + 1} positions to trade again")
        elif len(open_positions) >= max_total - 5:
            print(f"\n   ⚠️ NEAR LIMIT: Only {max_total - len(open_positions)} slots available")

# 3. Check recent activity
print(f"\n3. RECENT ACTIVITY (Last 6 hours):")
cutoff_6h = now_utc - timedelta(hours=6)
response = supabase.table('paper_trades').select('side, strategy_name').gte(
    'created_at', cutoff_6h.isoformat()
).execute()

if response.data:
    recent_buys = [t for t in response.data if t['side'] == 'BUY']
    recent_sells = [t for t in response.data if t['side'] == 'SELL']
    
    print(f"   New positions: {len(recent_buys)}")
    print(f"   Closed positions: {len(recent_sells)}")
    
    if len(recent_buys) == 0 and len(recent_sells) > 0:
        print(f"   📉 Only closing positions, not opening new ones!")

# 4. Check if service is scanning
print(f"\n4. SERVICE ACTIVITY:")
response = supabase.table('system_heartbeat').select('*').eq(
    'service_name', 'paper_trading_engine'
).order('last_heartbeat', desc=True).limit(1).execute()

if response.data:
    heartbeat = response.data[0]
    last_beat = datetime.fromisoformat(heartbeat['last_heartbeat'].replace('Z', '+00:00'))
    minutes_ago = (now_utc - last_beat).total_seconds() / 60
    
    if minutes_ago < 10:
        print(f"   ✅ Service running (heartbeat {minutes_ago:.1f} min ago)")
    else:
        print(f"   ⚠️ Service may be stuck (heartbeat {minutes_ago:.1f} min ago)")

print("\n" + "="*80)
print("DIAGNOSIS COMPLETE")
print("="*80)
