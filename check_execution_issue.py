#!/usr/bin/env python3
"""Check why only DCA is executing trades"""

from src.data.supabase_client import SupabaseClient
from datetime import datetime, timedelta, timezone

db = SupabaseClient()

print("="*60)
print("INVESTIGATING: Why only DCA executes trades")
print("="*60)

# Get all trades
trades = db.client.table('paper_trades').select('*').eq('side', 'BUY').order('created_at', desc=True).execute()

print("\nAll BUY trades in database:")
print("-"*40)
for trade in trades.data:
    print(f"{trade['symbol']:6} | {trade['strategy_name']:10} | {trade['created_at'][:19]}")

# Check if paper trader is running
print("\n" + "="*60)
print("HYPOTHESIS 1: Paper trader only listens to DCA?")
print("-"*40)

# Look for any SWING or CHANNEL decisions that were TAKE
yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
swing_takes = db.client.table('scan_history').select('*').eq('strategy_name', 'SWING').eq('decision', 'TAKE').gte('timestamp', yesterday).execute()
channel_takes = db.client.table('scan_history').select('*').eq('strategy_name', 'CHANNEL').eq('decision', 'TAKE').gte('timestamp', yesterday).execute()
dca_takes = db.client.table('scan_history').select('*').eq('strategy_name', 'DCA').eq('decision', 'TAKE').gte('timestamp', yesterday).execute()

print(f"TAKE decisions in last 24h:")
print(f"  DCA:     {len(dca_takes.data)} TAKE decisions")
print(f"  SWING:   {len(swing_takes.data)} TAKE decisions")
print(f"  CHANNEL: {len(channel_takes.data)} TAKE decisions")

if len(swing_takes.data) > 0:
    print("\n⚠️ SWING had TAKE decisions but no trades executed!")
    print("Sample SWING TAKE:")
    take = swing_takes.data[0]
    print(f"  Symbol: {take['symbol']}")
    print(f"  Time: {take['timestamp'][:19]}")
    
if len(channel_takes.data) > 0:
    print("\n⚠️ CHANNEL had TAKE decisions but no trades executed!")

print("\n" + "="*60)
print("HYPOTHESIS 2: Strategies not finding good setups?")
print("-"*40)

# Check the most recent scans for each strategy
for strategy in ['DCA', 'SWING', 'CHANNEL']:
    recent = db.client.table('scan_history').select('decision').eq('strategy_name', strategy).order('timestamp', desc=True).limit(100).execute()
    if recent.data:
        decisions = {}
        for scan in recent.data:
            d = scan.get('decision', 'UNKNOWN')
            decisions[d] = decisions.get(d, 0) + 1
        print(f"\n{strategy} (last 100 scans):")
        for decision, count in sorted(decisions.items()):
            print(f"  {decision:10} : {count}")

print("\n" + "="*60)
print("CONCLUSION:")
if len(dca_takes.data) > len(swing_takes.data) + len(channel_takes.data):
    print("✅ DCA is finding more opportunities in current market")
elif len(swing_takes.data) > 0 or len(channel_takes.data) > 0:
    print("❌ Paper trader may not be listening to SWING/CHANNEL signals")
else:
    print("⚠️ All strategies are struggling to find good setups")
