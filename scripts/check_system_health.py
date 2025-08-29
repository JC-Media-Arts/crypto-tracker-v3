"""Check system health and recent trading activity."""
import os
from datetime import datetime, timedelta, timezone
from supabase import create_client
from dotenv import load_dotenv
import json

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

print("="*80)
print("SYSTEM HEALTH CHECK")
print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
print("="*80)

# Check recent trades
print("\n1. RECENT PAPER TRADES (Last 2 hours):")
cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
response = supabase.table('paper_trades').select('*').gte(
    'created_at', cutoff.isoformat()
).order('created_at', desc=True).limit(10).execute()

if response.data:
    for trade in response.data[:5]:
        print(f"  {trade['created_at'][:19]} - {trade['strategy_name']} {trade['side']} {trade['symbol']} @ ${trade['price']:.4f}")
else:
    print("  No trades in last 2 hours")

# Check scan history
print("\n2. RECENT SCANS (Last 30 minutes):")
cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
response = supabase.table('scan_history').select('strategy_name, signal_detected, timestamp').gte(
    'timestamp', cutoff.isoformat()
).order('timestamp', desc=True).limit(100).execute()

if response.data:
    # Count by strategy
    strategy_counts = {}
    signal_counts = {}
    for scan in response.data:
        strategy = scan['strategy_name']
        strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
        if scan.get('signal_detected'):
            signal_counts[strategy] = signal_counts.get(strategy, 0) + 1
    
    for strategy in ['DCA', 'CHANNEL', 'SWING']:
        scans = strategy_counts.get(strategy, 0)
        signals = signal_counts.get(strategy, 0)
        print(f"  {strategy}: {scans} scans, {signals} signals detected")
else:
    print("  No scans in last 30 minutes - SERVICE MAY BE DOWN!")

# Check system heartbeat
print("\n3. SYSTEM HEARTBEAT:")
response = supabase.table('system_heartbeat').select('*').order(
    'last_heartbeat', desc=True
).limit(5).execute()

if response.data:
    for service in response.data:
        last_beat = datetime.fromisoformat(service['last_heartbeat'].replace('Z', '+00:00'))
        age = (datetime.now(timezone.utc) - last_beat).total_seconds()
        status = "✅ OK" if age < 600 else "⚠️ STALE" if age < 3600 else "❌ DOWN"
        print(f"  {service['service_name']}: {status} (last: {int(age)}s ago)")
else:
    print("  No heartbeat data found")

# Check config version
print("\n4. CONFIGURATION:")
with open('configs/paper_trading_config_unified.json', 'r') as f:
    config = json.load(f)
    print(f"  Version: {config['version']}")
    print(f"  Last Updated: {config['last_updated'][:19]}")
    print(f"  DCA Enabled: {config['strategies']['DCA']['enabled']}")
    print(f"  CHANNEL Enabled: {config['strategies']['CHANNEL']['enabled']}")
    print(f"  SWING Enabled: {config['strategies']['SWING']['enabled']}")

# Check for any errors in last hour
print("\n5. RECENT ERRORS:")
# This would check error logs if we had an errors table
print("  (Error logging not implemented in database)")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print("If no trades or scans are showing, the paper trading service may need restart.")
print("Check Railway dashboard for deployment status.")
