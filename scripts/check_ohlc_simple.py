#!/usr/bin/env python3
"""Simple check of OHLC data availability."""

import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def check_ohlc_data():
    """Check OHLC data availability."""
    
    client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    
    print("Checking OHLC data in Supabase...")
    print("=" * 60)
    
    # Check BTC data without timeframe (likely 1h)
    print("Checking BTC data (no timeframe specified)...")
    btc_response = client.table("ohlc_data") \
        .select("timestamp") \
        .eq("symbol", "BTC") \
        .is_("timeframe", "null") \
        .order("timestamp", desc=True) \
        .limit(10) \
        .execute()
    
    if btc_response.data:
        print(f"Found {len(btc_response.data)} recent BTC records without timeframe")
        latest = btc_response.data[0]['timestamp']
        oldest = btc_response.data[-1]['timestamp']
        print(f"Sample range: {oldest} to {latest}")
        
        # Calculate interval
        if len(btc_response.data) > 1:
            t1 = datetime.fromisoformat(btc_response.data[0]['timestamp'].replace('Z', '+00:00'))
            t2 = datetime.fromisoformat(btc_response.data[1]['timestamp'].replace('Z', '+00:00'))
            interval = abs((t1 - t2).total_seconds() / 60)
            print(f"Interval: {interval} minutes (likely {'1h' if interval == 60 else 'unknown'})")
    
    # Check BTC data with 1h timeframe
    print("\nChecking BTC data with '1h' timeframe...")
    btc_1h = client.table("ohlc_data") \
        .select("timestamp") \
        .eq("symbol", "BTC") \
        .eq("timeframe", "1h") \
        .order("timestamp", desc=True) \
        .limit(10) \
        .execute()
    
    if btc_1h.data:
        print(f"Found {len(btc_1h.data)} recent BTC 1h records")
        latest = btc_1h.data[0]['timestamp']
        oldest = btc_1h.data[-1]['timestamp']
        print(f"Sample range: {oldest} to {latest}")
    else:
        print("No BTC data with '1h' timeframe")
    
    # Check total BTC records (limited query)
    print("\nGetting BTC record count (limited to 1000)...")
    btc_count = client.table("ohlc_data") \
        .select("timestamp") \
        .eq("symbol", "BTC") \
        .limit(1000) \
        .execute()
    
    print(f"BTC records found: {len(btc_count.data)} (max 1000 shown)")
    
    # Get date range for BTC
    print("\nGetting BTC date range...")
    oldest_btc = client.table("ohlc_data") \
        .select("timestamp") \
        .eq("symbol", "BTC") \
        .order("timestamp") \
        .limit(1) \
        .execute()
    
    newest_btc = client.table("ohlc_data") \
        .select("timestamp") \
        .eq("symbol", "BTC") \
        .order("timestamp", desc=True) \
        .limit(1) \
        .execute()
    
    if oldest_btc.data and newest_btc.data:
        oldest_date = oldest_btc.data[0]['timestamp']
        newest_date = newest_btc.data[0]['timestamp']
        print(f"BTC date range: {oldest_date[:10]} to {newest_date[:10]}")
        
        # Calculate days of data
        old_dt = datetime.fromisoformat(oldest_date.replace('Z', '+00:00'))
        new_dt = datetime.fromisoformat(newest_date.replace('Z', '+00:00'))
        days = (new_dt - old_dt).days
        print(f"Days of data: {days}")
        print(f"Estimated 1h candles: {days * 24:,}")

if __name__ == "__main__":
    check_ohlc_data()
