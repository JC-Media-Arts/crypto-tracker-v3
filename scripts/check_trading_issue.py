"""Check why no new trades are opening."""
import os
from datetime import datetime, timedelta, timezone
from supabase import create_client
from dotenv import load_dotenv
import pytz

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

pst = pytz.timezone('America/Los_Angeles')
now_utc = datetime.now(timezone.utc)
now_pst = now_utc.astimezone(pst)

print("="*80)
print("TRADING ISSUE INVESTIGATION")
print(f"Current Time: {now_pst.strftime('%Y-%m-%d %I:%M %p PST')}")
print("="*80)

# Get recent BUY trades
cutoff = now_utc - timedelta(hours=24)
response = supabase.table('paper_trades').select('*').eq(
    'side', 'BUY'
).gte('created_at', cutoff.isoformat()).order('created_at', desc=True).execute()

if response.data:
    trades = response.data
    
    # Find most recent BUY
    if trades:
        last_buy = trades[0]
        last_buy_utc = datetime.fromisoformat(last_buy['created_at'].replace('Z', '+00:00'))
        last_buy_pst = last_buy_utc.astimezone(pst)
        hours_since = (now_utc - last_buy_utc).total_seconds() / 3600
        
        print(f"\n🔴 PROBLEM IDENTIFIED:")
        print(f"   Last NEW position opened: {last_buy_pst.strftime('%Y-%m-%d %I:%M %p PST')}")
        print(f"   That was {hours_since:.1f} hours ago!")
        print(f"   Symbol: {last_buy['symbol']}, Strategy: {last_buy['strategy_name']}")
        
        if hours_since > 6:
            print(f"\n   ⚠️ NO NEW TRADES IN {hours_since:.0f} HOURS!")
    
    # Check for recent position closes
    print(f"\n📊 POSITION ACTIVITY (Last 6 hours):")
    
    cutoff_6h = now_utc - timedelta(hours=6)
    
    # Get all trades in last 6 hours
    response = supabase.table('paper_trades').select('*').gte(
        'created_at', cutoff_6h.isoformat()
    ).order('created_at', desc=True).execute()
    
    if response.data:
        recent = response.data
        recent_buys = [t for t in recent if t['side'] == 'BUY']
        recent_sells = [t for t in recent if t['side'] == 'SELL']
        
        print(f"   New positions opened: {len(recent_buys)}")
        print(f"   Positions closed: {len(recent_sells)}")
        
        if len(recent_buys) == 0:
            print(f"\n   ❌ NO NEW POSITIONS IN LAST 6 HOURS")
            print(f"   But {len(recent_sells)} positions were CLOSED")
            print(f"   System is only exiting, not entering new trades!")

# Check current open positions
print(f"\n📈 OPEN POSITIONS CHECK:")
response = supabase.rpc('get_open_positions').execute()

if response.data:
    open_positions = response.data
    print(f"   Current open positions: {len(open_positions)}")
    
    # Check against max positions
    with open('configs/paper_trading_config_unified.json', 'r') as f:
        import json
        config = json.load(f)
        max_positions = config['position_management']['max_positions_total']
        print(f"   Max positions allowed: {max_positions}")
        
        if len(open_positions) >= max_positions:
            print(f"\n   🚫 AT POSITION LIMIT! Cannot open new trades!")
        elif len(open_positions) > 40:
            print(f"\n   ⚠️ Near position limit ({len(open_positions)}/{max_positions})")
else:
    # Fallback if RPC doesn't exist
    print("   (Cannot determine open positions)")

# Check if strategies are finding signals
print(f"\n🔍 CHECKING FOR SIGNALS:")
cutoff = now_utc - timedelta(hours=1)
response = supabase.table('scan_history').select('strategy_name, timestamp').gte(
    'timestamp', cutoff.isoformat()
).execute()

if response.data:
    scans = response.data
    by_strategy = {}
    for scan in scans:
        strategy = scan['strategy_name']
        by_strategy[strategy] = by_strategy.get(strategy, 0) + 1
    
    print(f"   Scans in last hour:")
    for strategy in ['DCA', 'CHANNEL', 'SWING']:
        count = by_strategy.get(strategy, 0)
        print(f"     {strategy}: {count} scans")
        
    if sum(by_strategy.values()) == 0:
        print(f"\n   ❌ NO SCANS RECORDED - Service may be stuck!")
else:
    print(f"   No scan data available")

print("\n" + "="*80)
print("LIKELY CAUSES:")
print("="*80)
print("""
1. ✅ Service is running (heartbeat active)
2. ❌ No new BUY trades for 30+ hours
3. ✅ SELL trades are happening (positions closing)

Possible issues:
- At or near position limit (check dashboard)
- Strategies not finding entry signals
- Market conditions not favorable
- Config issue preventing new entries
""")
