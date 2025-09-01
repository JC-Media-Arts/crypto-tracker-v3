#!/usr/bin/env python3
"""
Quick check for scan_history issues
"""

import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Check all scans from today
today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

print("Checking scan_history table...")
print("="*50)

# Get total count
total = supabase.table("scan_history").select("id", count="exact").execute()
print(f"Total scans in database: {total.count if hasattr(total, 'count') else len(total.data)}")

# Get today's scans
today_scans = supabase.table("scan_history") \
    .select("*") \
    .gte("timestamp", today.isoformat()) \
    .order("timestamp", desc=True) \
    .limit(10) \
    .execute()

if today_scans.data:
    print(f"\nFound {len(today_scans.data)} scans from today")
    print("\nMost recent scans:")
    for scan in today_scans.data[:5]:
        print(f"  {scan['timestamp']}: {scan['symbol']} - {scan['decision']}")
else:
    print("\n❌ No scans found today")
    
    # Check last scan ever
    last_scan = supabase.table("scan_history") \
        .select("*") \
        .order("timestamp", desc=True) \
        .limit(1) \
        .execute()
    
    if last_scan.data:
        print(f"\nLast scan was: {last_scan.data[0]['timestamp']}")
        last_time = datetime.fromisoformat(last_scan.data[0]['timestamp'].replace('Z', '+00:00'))
        hours_ago = (datetime.now(timezone.utc) - last_time).total_seconds() / 3600
        print(f"That was {hours_ago:.1f} hours ago")
    else:
        print("\n❌ No scans ever recorded")
