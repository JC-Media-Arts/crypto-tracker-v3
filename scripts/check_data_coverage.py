#!/usr/bin/env python3
"""
Check data coverage for all symbols after backfill.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient

# Load environment variables
load_dotenv()


def check_data_coverage():
    """Check how much data we have for each symbol."""

    print("=" * 80)
    print("DATA COVERAGE CHECK")
    print("=" * 80)

    # Initialize Supabase client
    supabase = SupabaseClient()

    # Get summary statistics
    query = """
        SELECT
            symbol,
            COUNT(*) as record_count,
            MIN(timestamp) as earliest_date,
            MAX(timestamp) as latest_date,
            EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp)))/3600 as hours_covered
        FROM price_data
        GROUP BY symbol
        ORDER BY record_count DESC
        LIMIT 100
    """

    try:
        # Note: We can't run raw SQL directly, so let's use a different approach
        # Get all unique symbols first
        symbols_result = supabase.client.table("price_data").select("symbol").execute()

        if not symbols_result.data:
            print("No data found!")
            return

        # Get unique symbols
        symbols = list(set(row["symbol"] for row in symbols_result.data))
        print(f"\nTotal symbols with data: {len(symbols)}")

        # Check a few key symbols for detailed stats
        key_symbols = [
            "BTC",
            "ETH",
            "SOL",
            "ADA",
            "DOT",
            "AVAX",
            "LINK",
            "UNI",
            "ATOM",
            "NEAR",
        ]

        print("\n" + "-" * 80)
        print(f"{'Symbol':<10} {'Records':<12} {'Date Range':<40} {'Days':<10}")
        print("-" * 80)

        total_records = 0
        symbols_with_good_data = 0

        for symbol in key_symbols[:20]:  # Check top 20
            # Get count and date range for each symbol
            result = (
                supabase.client.table("price_data")
                .select("timestamp")
                .eq("symbol", symbol)
                .order("timestamp")
                .limit(1)
                .execute()
            )

            if result.data:
                earliest = result.data[0]["timestamp"]

                # Get latest
                result_latest = (
                    supabase.client.table("price_data")
                    .select("timestamp")
                    .eq("symbol", symbol)
                    .order("timestamp", desc=True)
                    .limit(1)
                    .execute()
                )

                if result_latest.data:
                    latest = result_latest.data[0]["timestamp"]

                    # Get count (approximate)
                    # Since we can't count directly, estimate based on date range
                    earliest_dt = datetime.fromisoformat(
                        earliest.replace("Z", "+00:00")
                    )
                    latest_dt = datetime.fromisoformat(latest.replace("Z", "+00:00"))
                    days = (latest_dt - earliest_dt).days
                    estimated_records = days * 1440  # Approximate minute bars

                    total_records += estimated_records
                    if days > 30:  # At least 30 days of data
                        symbols_with_good_data += 1

                    print(
                        f"{symbol:<10} {'~' + str(estimated_records):<11} {earliest[:10]} to {latest[:10]:<25} {days:<10}"
                    )

        print("-" * 80)
        print(f"\nSummary:")
        print(f"  Symbols with 30+ days of data: {symbols_with_good_data}")
        print(f"  Total estimated records: ~{total_records:,}")

        # Check if we have enough recent data for DCA detection
        print("\n" + "=" * 80)
        print("RECENT DATA CHECK (Last 24 hours)")
        print("-" * 80)

        yesterday = (datetime.now() - timedelta(hours=24)).isoformat()

        for symbol in ["BTC", "ETH", "SOL"]:
            result = (
                supabase.client.table("price_data")
                .select("timestamp, price")
                .eq("symbol", symbol)
                .gte("timestamp", yesterday)
                .order("timestamp", desc=True)
                .limit(100)
                .execute()
            )

            if result.data:
                record_count = len(result.data)
                latest_price = result.data[0]["price"]
                print(
                    f"{symbol}: {record_count} records in last 24h, Latest price: ${latest_price:.2f}"
                )
            else:
                print(f"{symbol}: No recent data")

    except Exception as e:
        print(f"Error checking data coverage: {e}")

    print("\n" + "=" * 80)
    print("DATA COVERAGE CHECK COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    check_data_coverage()
