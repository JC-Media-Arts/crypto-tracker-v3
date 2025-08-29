#!/usr/bin/env python3
"""
Check if Freqtrade on Railway is logging scans to database
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client

def check_freqtrade_scans():
    """Check scan_history table for recent Freqtrade entries"""
    
    # Initialize Supabase client
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    if not supabase_url or not supabase_key:
        print("❌ SUPABASE_URL and SUPABASE_KEY must be set in environment")
        return
    
    client = create_client(supabase_url, supabase_key)
    
    print("=" * 60)
    print("🔍 Checking Freqtrade Scan Logging on Railway")
    print("=" * 60)
    
    # Check for recent scans (last 15 minutes)
    fifteen_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    
    try:
        # Get recent CHANNEL strategy scans
        channel_response = client.table("scan_history") \
            .select("*") \
            .eq("strategy_name", "CHANNEL") \
            .gte("timestamp", fifteen_min_ago) \
            .order("timestamp", desc=True) \
            .limit(20) \
            .execute()
        
        if channel_response.data:
            print(f"\n✅ Found {len(channel_response.data)} CHANNEL scans in last 15 minutes!")
            print("\nLatest CHANNEL scans from Freqtrade:")
            print("-" * 60)
            
            for scan in channel_response.data[:10]:
                timestamp = scan['timestamp']
                symbol = scan['symbol']
                decision = scan['decision']
                features = scan.get('features', '{}')
                
                # Parse timestamp for readability
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                time_str = dt.strftime('%H:%M:%S')
                
                print(f"  {time_str} | {symbol:6} | {decision:6} | Features: {features[:50]}...")
        else:
            print("\n⚠️ No CHANNEL scans found in last 15 minutes")
            
        # Get scan counts by strategy for last hour
        hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        
        print("\n" + "=" * 60)
        print("📊 Scan Statistics (Last Hour)")
        print("-" * 60)
        
        # Get all scans from last hour
        all_scans = client.table("scan_history") \
            .select("strategy_name, decision") \
            .gte("timestamp", hour_ago) \
            .execute()
        
        if all_scans.data:
            # Count by strategy
            strategy_counts = {}
            decision_counts = {}
            
            for scan in all_scans.data:
                strategy = scan.get('strategy_name', 'UNKNOWN')
                decision = scan.get('decision', 'UNKNOWN')
                
                strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
                decision_counts[f"{strategy}_{decision}"] = decision_counts.get(f"{strategy}_{decision}", 0) + 1
            
            print("\nScans by Strategy:")
            for strategy, count in sorted(strategy_counts.items()):
                print(f"  {strategy:10} : {count:5} scans")
                
            print("\nCHANNEL Strategy Decisions:")
            for key, count in sorted(decision_counts.items()):
                if key.startswith("CHANNEL_"):
                    decision = key.replace("CHANNEL_", "")
                    print(f"  {decision:10} : {count:5} scans")
        
        # Check unique symbols scanned
        symbol_response = client.table("scan_history") \
            .select("symbol") \
            .eq("strategy_name", "CHANNEL") \
            .gte("timestamp", hour_ago) \
            .execute()
        
        if symbol_response.data:
            unique_symbols = set(scan['symbol'] for scan in symbol_response.data)
            print(f"\nUnique symbols scanned: {len(unique_symbols)}")
            print(f"Symbols: {', '.join(sorted(unique_symbols)[:20])}")
            
        # Get total count
        total_response = client.table("scan_history") \
            .select("*", count="exact") \
            .execute()
        
        total_count = total_response.count if hasattr(total_response, 'count') else len(total_response.data)
        print(f"\n📈 Total scans in database: {total_count:,}")
        
        # Check if scans are still coming in
        one_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        recent_check = client.table("scan_history") \
            .select("*") \
            .eq("strategy_name", "CHANNEL") \
            .gte("timestamp", one_min_ago) \
            .execute()
        
        if recent_check.data:
            print(f"\n🟢 LIVE: {len(recent_check.data)} scans in last minute - Freqtrade is actively scanning!")
        else:
            print("\n🟡 No scans in last minute - Freqtrade may be between scan cycles")
            
    except Exception as e:
        print(f"❌ Error checking scan_history: {e}")

if __name__ == "__main__":
    check_freqtrade_scans()
