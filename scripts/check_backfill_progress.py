#!/usr/bin/env python3
"""
Check the progress of historical data backfill.
"""

import sys
import os
from datetime import datetime, timezone, timedelta

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.supabase_client import SupabaseClient
from src.data.polygon_client import PolygonWebSocketClient


def check_backfill_progress():
    """Check and display backfill progress for all symbols."""
    supabase = SupabaseClient()
    polygon = PolygonWebSocketClient()

    # Get all symbols we're tracking
    symbols = polygon._get_supported_symbols()[:10]  # Top 10 for now

    print("\n" + "=" * 80)
    print("HISTORICAL DATA BACKFILL PROGRESS")
    print("=" * 80)
    print(f"{'Symbol':<10} {'Records':<12} {'Date Range':<35} {'Duration'}")
    print("-" * 80)

    total_records = 0
    symbols_with_data = 0

    for symbol in symbols:
        # Get count and date range for each symbol
        response = supabase.client.table("price_data").select("*", count="exact").eq("symbol", symbol).execute()
        count = response.count

        if count > 0:
            # Get oldest timestamp
            response = (
                supabase.client.table("price_data")
                .select("timestamp")
                .eq("symbol", symbol)
                .order("timestamp", desc=False)
                .limit(1)
                .execute()
            )
            oldest = response.data[0]["timestamp"] if response.data else None

            # Get newest timestamp
            response = (
                supabase.client.table("price_data")
                .select("timestamp")
                .eq("symbol", symbol)
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )
            newest = response.data[0]["timestamp"] if response.data else None

            if oldest and newest:
                oldest_date = datetime.fromisoformat(oldest.replace("Z", "+00:00"))
                newest_date = datetime.fromisoformat(newest.replace("Z", "+00:00"))
                duration = newest_date - oldest_date

                date_range = f"{oldest_date.strftime('%Y-%m-%d')} to {newest_date.strftime('%Y-%m-%d')}"
                duration_str = f"{duration.days}d {duration.seconds//3600}h"

                print(f"{symbol:<10} {count:>11,} {date_range:<35} {duration_str}")
                total_records += count
                symbols_with_data += 1
        else:
            print(f"{symbol:<10} {'0':>11} {'No data':<35} -")

    print("-" * 80)
    print(f"TOTAL: {symbols_with_data}/{len(symbols)} symbols, {total_records:,} records")
    print("=" * 80)

    # Check if backfill is still running
    print("\nChecking backfill.log for recent activity...")
    try:
        with open("logs/backfill.log", "r") as f:
            lines = f.readlines()
            if lines:
                # Show last 5 lines
                print("\nLast 5 log entries:")
                for line in lines[-5:]:
                    print(f"  {line.strip()}")
    except FileNotFoundError:
        print("  No backfill.log found")

    print()


if __name__ == "__main__":
    check_backfill_progress()
