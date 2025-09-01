#!/usr/bin/env python3
"""Check what OHLC data is available in Supabase."""

import os
import sys
from datetime import datetime, timezone
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def check_ohlc_data():
    """Check OHLC data availability in Supabase."""
    
    client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    
    print("Checking OHLC data in Supabase...")
    print("=" * 60)
    
    # Get unique symbols
    symbols_response = client.table("ohlc_data") \
        .select("symbol") \
        .execute()
    
    unique_symbols = set(row['symbol'] for row in symbols_response.data)
    print(f"Unique symbols: {len(unique_symbols)}")
    print(f"Symbols: {sorted(unique_symbols)[:10]}...")  # Show first 10
    
    # Check timeframes
    print("\n" + "=" * 60)
    print("Checking timeframes...")
    
    # Query for each timeframe
    timeframes = ['1m', '5m', '15m', '1h', '1d']
    
    for tf in timeframes:
        # Count records for this timeframe
        count_response = client.table("ohlc_data") \
            .select("symbol", count="exact") \
            .eq("timeframe", tf) \
            .limit(1) \
            .execute()
        
        count = count_response.count if hasattr(count_response, 'count') else 0
        
        if count > 0:
            # Get date range for this timeframe
            oldest = client.table("ohlc_data") \
                .select("timestamp") \
                .eq("timeframe", tf) \
                .order("timestamp") \
                .limit(1) \
                .execute()
            
            newest = client.table("ohlc_data") \
                .select("timestamp") \
                .eq("timeframe", tf) \
                .order("timestamp", desc=True) \
                .limit(1) \
                .execute()
            
            if oldest.data and newest.data:
                oldest_date = oldest.data[0]['timestamp']
                newest_date = newest.data[0]['timestamp']
                print(f"\n{tf} timeframe:")
                print(f"  Records: {count:,}")
                print(f"  Date range: {oldest_date[:10]} to {newest_date[:10]}")
        else:
            print(f"\n{tf} timeframe: No data")
    
    # Check data without timeframe column (legacy data)
    print("\n" + "=" * 60)
    print("Checking data without timeframe column...")
    
    no_tf_response = client.table("ohlc_data") \
        .select("symbol", count="exact") \
        .is_("timeframe", "null") \
        .limit(1) \
        .execute()
    
    no_tf_count = no_tf_response.count if hasattr(no_tf_response, 'count') else 0
    
    if no_tf_count > 0:
        print(f"Records without timeframe: {no_tf_count:,}")
        
        # Get date range
        oldest = client.table("ohlc_data") \
            .select("timestamp") \
            .is_("timeframe", "null") \
            .order("timestamp") \
            .limit(1) \
            .execute()
        
        newest = client.table("ohlc_data") \
            .select("timestamp") \
            .is_("timeframe", "null") \
            .order("timestamp", desc=True) \
            .limit(1) \
            .execute()
        
        if oldest.data and newest.data:
            oldest_date = oldest.data[0]['timestamp']
            newest_date = newest.data[0]['timestamp']
            print(f"Date range: {oldest_date[:10]} to {newest_date[:10]}")
            
            # Check a sample to determine interval
            sample = client.table("ohlc_data") \
                .select("timestamp") \
                .eq("symbol", "BTC") \
                .is_("timeframe", "null") \
                .order("timestamp") \
                .limit(100) \
                .execute()
            
            if len(sample.data) > 1:
                # Calculate average interval
                timestamps = [datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00')) 
                             for row in sample.data]
                intervals = [(timestamps[i+1] - timestamps[i]).total_seconds() / 60 
                            for i in range(len(timestamps)-1)]
                avg_interval = sum(intervals) / len(intervals)
                print(f"Average interval: {avg_interval:.1f} minutes (likely {guess_timeframe(avg_interval)})")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    # Get total records
    total_response = client.table("ohlc_data") \
        .select("symbol", count="exact") \
        .limit(1) \
        .execute()
    
    total_count = total_response.count if hasattr(total_response, 'count') else 0
    print(f"Total records in ohlc_data: {total_count:,}")
    
    # Recommendation
    print("\n" + "=" * 60)
    print("RECOMMENDATION")
    print("=" * 60)
    
    if no_tf_count > 0:
        print("You have data without timeframe specified (likely 1h data).")
        print("Update your sync script to handle NULL timeframe as 1h data.")
    
    print("\nFor Freqtrade backtesting, you need:")
    print("- 1h data (main timeframe) - for strategy analysis")
    print("- 5m or 15m data (detail timeframe) - for accurate backtesting")

def guess_timeframe(avg_minutes):
    """Guess timeframe based on average interval."""
    if avg_minutes < 2:
        return "1m"
    elif avg_minutes < 10:
        return "5m"
    elif avg_minutes < 30:
        return "15m"
    elif avg_minutes < 90:
        return "1h"
    else:
        return "1d"

if __name__ == "__main__":
    check_ohlc_data()
