"""Check all recent trades and compare with dashboard view."""
import os
from datetime import datetime, timedelta, timezone
from supabase import create_client
from dotenv import load_dotenv
import pytz

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Convert to PST for dashboard comparison
pst = pytz.timezone('America/Los_Angeles')

print("="*80)
print("ALL RECENT TRADES ANALYSIS")
print(f"Current Time UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Current Time PST: {datetime.now(pst).strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)

# Get ALL trades from last 48 hours
cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
response = supabase.table('paper_trades').select('*').gte(
    'created_at', cutoff.isoformat()
).order('created_at', desc=True).execute()

if response.data:
    trades = response.data
    print(f"\nTotal trades in last 48 hours: {len(trades)}")
    
    # Group by side
    buys = [t for t in trades if t['side'] == 'BUY']
    sells = [t for t in trades if t['side'] == 'SELL']
    
    print(f"BUY orders: {len(buys)}")
    print(f"SELL orders: {len(sells)}")
    
    # Show last 20 BUY trades (new positions)
    print("\n📈 LAST 20 BUY TRADES (New Positions):")
    print("-" * 60)
    for trade in buys[:20]:
        # Convert to PST for dashboard comparison
        utc_time = datetime.fromisoformat(trade['created_at'].replace('Z', '+00:00'))
        pst_time = utc_time.astimezone(pst)
        
        print(f"{pst_time.strftime('%m/%d %I:%M %p')} PST | {trade['strategy_name']:8} | {trade['symbol']:8} | ${trade['price']:.4f}")
    
    # Check for trades after 08/27 6:16 PM PST
    cutoff_pst = pst.localize(datetime(2024, 8, 27, 18, 16))
    recent_buys = []
    
    for trade in buys:
        utc_time = datetime.fromisoformat(trade['created_at'].replace('Z', '+00:00'))
        pst_time = utc_time.astimezone(pst)
        if pst_time > cutoff_pst:
            recent_buys.append(trade)
    
    print(f"\n⚠️ BUY trades after 08/27 06:16 PM PST: {len(recent_buys)}")
    
    if len(recent_buys) == 0:
        print("\n❌ NO NEW POSITIONS OPENED since 08/27 06:16 PM PST")
        print("   This confirms your dashboard observation!")
        
        # Check when last buy was
        if buys:
            last_buy = buys[0]
            last_buy_utc = datetime.fromisoformat(last_buy['created_at'].replace('Z', '+00:00'))
            last_buy_pst = last_buy_utc.astimezone(pst)
            hours_ago = (datetime.now(timezone.utc) - last_buy_utc).total_seconds() / 3600
            
            print(f"\n   Last BUY was: {last_buy_pst.strftime('%m/%d %I:%M %p')} PST")
            print(f"   Symbol: {last_buy['symbol']}, Strategy: {last_buy['strategy_name']}")
            print(f"   That was {hours_ago:.1f} hours ago!")
    
    # Check SELL trades (exits)
    print("\n📉 RECENT SELL TRADES (Last 10):")
    print("-" * 60)
    for trade in sells[:10]:
        utc_time = datetime.fromisoformat(trade['created_at'].replace('Z', '+00:00'))
        pst_time = utc_time.astimezone(pst)
        print(f"{pst_time.strftime('%m/%d %I:%M %p')} PST | {trade['strategy_name']:8} | {trade['symbol']:8} | Exit: {trade.get('exit_reason', 'unknown')}")
    
else:
    print("No trades found in last 48 hours")

# Check if trading is enabled
print("\n⚙️ CHECKING CONFIGURATION:")
with open('configs/paper_trading_config_unified.json', 'r') as f:
    import json
    config = json.load(f)
    print(f"  Trading Enabled: {config['global_settings']['trading_enabled']}")
    print(f"  DCA Enabled: {config['strategies']['DCA']['enabled']}")
    print(f"  CHANNEL Enabled: {config['strategies']['CHANNEL']['enabled']}")
    print(f"  SWING Enabled: {config['strategies']['SWING']['enabled']}")

# Check system heartbeat
print("\n💓 SYSTEM STATUS:")
response = supabase.table('system_heartbeat').select('*').eq(
    'service_name', 'paper_trading_engine'
).order('last_heartbeat', desc=True).limit(1).execute()

if response.data:
    heartbeat = response.data[0]
    last_beat = datetime.fromisoformat(heartbeat['last_heartbeat'].replace('Z', '+00:00'))
    minutes_ago = (datetime.now(timezone.utc) - last_beat).total_seconds() / 60
    
    if minutes_ago < 10:
        print(f"  ✅ Service is ACTIVE (last heartbeat: {minutes_ago:.1f} min ago)")
    else:
        print(f"  ⚠️ Service may be stuck (last heartbeat: {minutes_ago:.1f} min ago)")
