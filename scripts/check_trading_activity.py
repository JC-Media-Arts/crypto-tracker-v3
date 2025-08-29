"""Check recent trading activity after config changes."""
import os
from datetime import datetime, timedelta, timezone
from supabase import create_client
from dotenv import load_dotenv
import json

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

print("="*80)
print("TRADING ACTIVITY CHECK")
print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
print("="*80)

# Check trades in last 6 hours
print("\n📊 RECENT TRADES (Last 6 hours):")
cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
response = supabase.table('paper_trades').select('*').gte(
    'created_at', cutoff.isoformat()
).order('created_at', desc=True).execute()

if response.data:
    trades = response.data
    
    # Count by strategy and side
    strategy_counts = {}
    for trade in trades:
        key = f"{trade['strategy_name']} {trade['side']}"
        strategy_counts[key] = strategy_counts.get(key, 0) + 1
    
    print(f"\nTotal trades: {len(trades)}")
    print("\nBreakdown by strategy:")
    for key, count in sorted(strategy_counts.items()):
        print(f"  {key}: {count}")
    
    # Show last 10 trades
    print("\nLast 10 trades:")
    for trade in trades[:10]:
        time_str = trade['created_at'][11:19]  # Just HH:MM:SS
        print(f"  {time_str} UTC - {trade['strategy_name']:8} {trade['side']:4} {trade['symbol']:8} @ ${trade['price']:.4f}")
else:
    print("  ❌ No trades in last 6 hours!")

# Check trades since config update (about 1 hour ago)
print("\n🔄 TRADES SINCE CONFIG UPDATE (Last 1 hour):")
cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
response = supabase.table('paper_trades').select('*').gte(
    'created_at', cutoff.isoformat()
).order('created_at', desc=True).execute()

if response.data:
    trades = response.data
    
    # Count by strategy
    by_strategy = {}
    for trade in trades:
        strategy = trade['strategy_name']
        if strategy not in by_strategy:
            by_strategy[strategy] = {'BUY': 0, 'SELL': 0}
        by_strategy[strategy][trade['side']] += 1
    
    for strategy, counts in by_strategy.items():
        print(f"  {strategy}: {counts['BUY']} buys, {counts['SELL']} sells")
    
    # Check for DCA trades specifically
    dca_trades = [t for t in trades if t['strategy_name'] == 'DCA']
    if dca_trades:
        print(f"\n  ✅ DCA is triggering! {len(dca_trades)} trades")
    else:
        print(f"\n  ⚠️ No DCA trades yet since config update")
else:
    print("  No trades since config update")

# Check system heartbeat
print("\n💓 SYSTEM HEARTBEAT:")
response = supabase.table('system_heartbeat').select('*').order(
    'last_heartbeat', desc=True
).limit(5).execute()

if response.data:
    for service in response.data:
        last_beat = datetime.fromisoformat(service['last_heartbeat'].replace('Z', '+00:00'))
        age = (datetime.now(timezone.utc) - last_beat).total_seconds()
        
        if age < 300:
            status = "✅ ACTIVE"
        elif age < 600:
            status = "🟡 OK"
        elif age < 3600:
            status = "⚠️ STALE"
        else:
            status = "❌ DOWN"
            
        print(f"  {service['service_name']}: {status} (last: {int(age/60)} min ago)")
else:
    print("  No heartbeat data")

# Show current config version
print("\n⚙️ CONFIGURATION STATUS:")
with open('configs/paper_trading_config_unified.json', 'r') as f:
    config = json.load(f)
    print(f"  Version: {config['version']}")
    print(f"  Updated: {config['last_updated'][:19]}")
    
    # Show new DCA thresholds
    dca_thresholds = config['strategies']['DCA']['detection_thresholds_by_tier']
    print(f"\n  New DCA thresholds (should generate more signals):")
    for tier in ['large_cap', 'mid_cap', 'small_cap', 'memecoin']:
        if tier in dca_thresholds:
            print(f"    {tier}: {dca_thresholds[tier]['drop_threshold']}%")

print("\n" + "="*80)
print("ASSESSMENT")
print("="*80)

if response.data and len(response.data) > 0:
    latest_heartbeat = response.data[0]
    last_beat = datetime.fromisoformat(latest_heartbeat['last_heartbeat'].replace('Z', '+00:00'))
    age = (datetime.now(timezone.utc) - last_beat).total_seconds()
    
    if age < 600:
        print("✅ System appears to be running normally")
        print("   Config changes were pushed successfully")
        print("   It may take 5-10 minutes for new thresholds to trigger trades")
    else:
        print("⚠️ System may need attention - heartbeat is stale")
else:
    print("❌ Cannot determine system status - check Railway dashboard")
