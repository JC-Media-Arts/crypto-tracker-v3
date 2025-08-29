#!/usr/bin/env python3
"""
Check if Freqtrade is logging scans to database
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_scan_logging():
    """Check scan_history table for recent entries"""
    
    # Initialize Supabase client
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    if not supabase_url or not supabase_key:
        print("❌ SUPABASE_URL and SUPABASE_KEY must be set in environment")
        return
    
    client = create_client(supabase_url, supabase_key)
    
    # Check for recent scans (last 5 minutes)
    five_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    
    try:
        # Get recent scans
        response = client.table("scan_history") \
            .select("*") \
            .gte("timestamp", five_min_ago) \
            .order("timestamp", desc=True) \
            .limit(10) \
            .execute()
        
        if response.data:
            print(f"✅ Found {len(response.data)} recent scans in database!")
            print("\nRecent scans:")
            for scan in response.data[:5]:
                print(f"  - {scan['timestamp']}: {scan['symbol']} - {scan.get('strategy_name', 'N/A')} - {scan['decision']}")
        else:
            print("⚠️ No scans found in last 5 minutes")
            
        # Get total count
        count_response = client.table("scan_history") \
            .select("*", count="exact") \
            .execute()
        
        total_count = count_response.count if hasattr(count_response, 'count') else len(count_response.data)
        print(f"\nTotal scans in database: {total_count}")
        
        # Check if scans are from Freqtrade (should have CHANNEL strategy)
        channel_response = client.table("scan_history") \
            .select("*") \
            .eq("strategy_name", "CHANNEL") \
            .gte("timestamp", five_min_ago) \
            .execute()
        
        if channel_response.data:
            print(f"✅ Found {len(channel_response.data)} CHANNEL strategy scans from Freqtrade!")
        else:
            print("⚠️ No CHANNEL strategy scans found - Freqtrade may not be logging yet")
            
    except Exception as e:
        print(f"❌ Error checking scan_history: {e}")

if __name__ == "__main__":
    check_scan_logging()
