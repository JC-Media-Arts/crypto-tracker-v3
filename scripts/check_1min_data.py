#!/usr/bin/env python3
"""
Check 1-minute OHLC data status and size.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

# Load environment variables
load_dotenv()


def get_db_connection():
    """Get direct PostgreSQL connection from Supabase URL."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    # Parse the database URL from Supabase URL
    # Supabase URL format: https://xxxxx.supabase.co
    # Database URL format: postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres

    # For direct connection, we'll use the Supabase Python client approach
    # But first, let's try a simpler approach with SQL queries
    return None


def main():
    """Check 1-minute data directly."""

    sys.path.append(str(Path(__file__).parent.parent))
    from src.data.supabase_client import SupabaseClient
    from loguru import logger

    logger.info("Checking 1-minute OHLC data...")
    supabase = SupabaseClient()

    print("\n" + "=" * 80)
    print("🕐 1-MINUTE DATA INVESTIGATION")
    print("=" * 80)

    # First, let's check if any 1-minute data exists at all
    print("\n📊 Checking for 1-minute data existence...")
    print("-" * 60)

    # Try different variations of 1-minute timeframe labels
    timeframe_variations = ["1min", "1m", "1", "1minute"]

    for tf in timeframe_variations:
        try:
            # Just check if any rows exist
            result = (
                supabase.client.table("ohlc_data")
                .select("timestamp", count="exact")
                .eq("timeframe", tf)
                .limit(1)
                .execute()
            )

            count = result.count if hasattr(result, "count") else 0

            if count > 0:
                print(f"\n✅ Found {count:,} rows with timeframe='{tf}'")

                # Get date range with smaller queries
                print(f"   Getting date range (this may take a moment)...")

                # Get oldest - use a different approach
                try:
                    # Try to get just the oldest timestamp
                    oldest_result = (
                        supabase.client.table("ohlc_data")
                        .select("timestamp")
                        .eq("timeframe", tf)
                        .order("timestamp")
                        .limit(1)
                        .execute()
                    )

                    if oldest_result.data:
                        oldest = oldest_result.data[0]["timestamp"]
                        print(f"   Oldest: {oldest[:19]}")
                except Exception as e:
                    print(f"   Could not get oldest: {str(e)[:50]}")

                # Get newest
                try:
                    newest_result = (
                        supabase.client.table("ohlc_data")
                        .select("timestamp")
                        .eq("timeframe", tf)
                        .order("timestamp", desc=True)
                        .limit(1)
                        .execute()
                    )

                    if newest_result.data:
                        newest = newest_result.data[0]["timestamp"]
                        print(f"   Newest: {newest[:19]}")

                        # Calculate retention period
                        newest_dt = datetime.fromisoformat(
                            newest.replace("Z", "+00:00")
                        )
                        if oldest_result.data:
                            oldest_dt = datetime.fromisoformat(
                                oldest.replace("Z", "+00:00")
                            )
                            retention_days = (newest_dt - oldest_dt).days
                            print(f"   Retention: {retention_days} days of data")
                except Exception as e:
                    print(f"   Could not get newest: {str(e)[:50]}")

                # Estimate storage size
                row_size_bytes = 150  # Approximate
                size_mb = (count * row_size_bytes) / (1024 * 1024)
                size_gb = size_mb / 1024

                print(f"   Estimated size: {size_mb:.1f} MB ({size_gb:.2f} GB)")

                # Check data distribution
                print(f"\n   Checking data distribution...")

                # Get count for last 7 days
                try:
                    week_ago = (
                        datetime.now(timezone.utc) - timedelta(days=7)
                    ).isoformat()
                    recent_result = (
                        supabase.client.table("ohlc_data")
                        .select("timestamp", count="exact")
                        .eq("timeframe", tf)
                        .gte("timestamp", week_ago)
                        .limit(1)
                        .execute()
                    )

                    recent_count = (
                        recent_result.count if hasattr(recent_result, "count") else 0
                    )
                    print(f"   Last 7 days: {recent_count:,} rows")

                    if recent_count > 0:
                        daily_rate = recent_count / 7
                        print(f"   Daily growth: ~{daily_rate:.0f} rows/day")
                        print(
                            f"   Monthly projection: ~{daily_rate * 30:,.0f} new rows"
                        )
                except Exception as e:
                    print(f"   Could not check recent data: {str(e)[:50]}")

                # Get count for last 30 days
                try:
                    month_ago = (
                        datetime.now(timezone.utc) - timedelta(days=30)
                    ).isoformat()
                    month_result = (
                        supabase.client.table("ohlc_data")
                        .select("timestamp", count="exact")
                        .eq("timeframe", tf)
                        .gte("timestamp", month_ago)
                        .limit(1)
                        .execute()
                    )

                    month_count = (
                        month_result.count if hasattr(month_result, "count") else 0
                    )
                    print(f"   Last 30 days: {month_count:,} rows")
                except Exception as e:
                    print(f"   Could not check monthly data: {str(e)[:50]}")

            else:
                print(f"   No data found for timeframe='{tf}'")

        except Exception as e:
            error_msg = str(e)
            if "JSON could not be generated" in error_msg:
                print(f"\n⚠️  Timeframe '{tf}': Table too large, queries timing out")
                print("   This suggests significant data exists but can't be counted")
            elif "does not exist" not in error_msg:
                print(f"\n❌ Error checking '{tf}': {error_msg[:100]}")

    # Check if we're actually collecting 1-minute data currently
    print("\n" + "=" * 80)
    print("📡 CURRENT 1-MINUTE DATA COLLECTION:")
    print("-" * 60)

    # Check recent data to see if we're actively collecting
    try:
        one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

        for tf in ["1min", "1m"]:
            result = (
                supabase.client.table("ohlc_data")
                .select("symbol", count="exact")
                .eq("timeframe", tf)
                .gte("timestamp", one_hour_ago)
                .limit(1)
                .execute()
            )

            count = result.count if hasattr(result, "count") else 0
            if count > 0:
                print(f"\n✅ Actively collecting {tf} data: {count} rows in last hour")

                # Get unique symbols
                symbols_result = (
                    supabase.client.table("ohlc_data")
                    .select("symbol")
                    .eq("timeframe", tf)
                    .gte("timestamp", one_hour_ago)
                    .execute()
                )

                if symbols_result.data:
                    unique_symbols = set(row["symbol"] for row in symbols_result.data)
                    print(f"   Symbols being collected: {len(unique_symbols)}")
                    if len(unique_symbols) <= 10:
                        print(f"   Symbols: {', '.join(sorted(unique_symbols))}")
                break
        else:
            print("\n⚠️  No 1-minute data collected in the last hour")
            print("   Either collection is stopped or using different timeframe label")
    except Exception as e:
        print(f"\n❌ Could not check recent collection: {str(e)[:100]}")

    # Recommendations
    print("\n" + "=" * 80)
    print("💡 FINDINGS & RECOMMENDATIONS:")
    print("=" * 80)

    print(
        """
1. **1-MINUTE DATA STATUS**:
   - If queries are timing out, you likely have millions of rows
   - This is the highest frequency data and biggest storage consumer
   - Probably not being actively collected (WebSocket focused on 15m)

2. **RETENTION POLICY FOR 1-MIN**:
   - Currently: KEEPING EVERYTHING (no cleanup)
   - Recommended: Keep only 7-30 days maximum
   - Reason: 1-min data is rarely needed beyond recent periods

3. **IMMEDIATE ACTIONS**:
   a) If 1-min data exists and is old:
      DELETE FROM ohlc_data
      WHERE timeframe IN ('1min', '1m', '1')
      AND timestamp < NOW() - INTERVAL '7 days';

   b) If not collecting 1-min currently:
      - Consider if you really need it
      - 15-minute data is sufficient for most strategies

   c) Create index if missing:
      CREATE INDEX idx_ohlc_timeframe_time
      ON ohlc_data(timeframe, timestamp DESC);

4. **STORAGE IMPACT**:
   - 90 symbols × 1440 minutes/day = 129,600 rows/day
   - At 150 bytes/row = ~20 MB/day = ~600 MB/month
   - This adds up to 7+ GB/year for just 1-minute data!
    """
    )


if __name__ == "__main__":
    main()
