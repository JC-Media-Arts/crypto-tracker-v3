#!/usr/bin/env python3
"""
Quick script to check if Freqtrade is making trades
"""
import os
from datetime import datetime, timezone, timedelta
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

# Initialize Supabase client
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

print("🔍 Checking Freqtrade Trading Activity...")
print("=" * 60)

# Check recent scan history
recent_time = datetime.now(timezone.utc) - timedelta(minutes=10)
scan_response = supabase.table("scan_history").select("*").gte("timestamp", recent_time.isoformat()).execute()

if scan_response.data:
    print(f"✅ Found {len(scan_response.data)} scans in last 10 minutes")
    
    # Count by decision
    decisions = {}
    for scan in scan_response.data:
        decision = scan.get('decision', 'UNKNOWN')
        decisions[decision] = decisions.get(decision, 0) + 1
    
    print("\nScan Decisions:")
    for decision, count in decisions.items():
        print(f"  {decision}: {count}")
else:
    print("❌ No scans found in last 10 minutes")

print("\n" + "=" * 60)

# Check for recent Freqtrade trades
trades_response = supabase.table("freqtrade_trades").select("*").gte("open_date", recent_time.isoformat()).execute()

if trades_response.data:
    print(f"✅ Found {len(trades_response.data)} trades opened in last 10 minutes:")
    for trade in trades_response.data[:5]:  # Show first 5
        print(f"  - {trade['pair']}: ${trade['amount']:.2f} at {trade['open_rate']}")
        print(f"    Status: {trade['status']}")
else:
    print("⚠️  No Freqtrade trades found in last 10 minutes")
    print("\nPossible reasons:")
    print("  1. Strategy is being cautious (waiting for better signals)")
    print("  2. All signals are being filtered by risk management")
    print("  3. Market conditions don't meet entry criteria")
    print("  4. Check Railway logs for more details")

print("\n" + "=" * 60)

# Check if scan logger is working now
latest_scan = supabase.table("scan_history").select("*").order("timestamp", desc=True).limit(1).execute()
if latest_scan.data:
    scan = latest_scan.data[0]
    print(f"✅ Latest scan: {scan['symbol']} - {scan['decision']} ({scan['timestamp']})")
    if len(scan['symbol']) > 10:
        print(f"✅ Long symbols working! ('{scan['symbol']}' is {len(scan['symbol'])} chars)")
