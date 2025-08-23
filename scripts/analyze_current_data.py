#!/usr/bin/env python3
"""
Analyze current OHLC data without timeouts.
Uses chunked queries to avoid Supabase web UI limitations.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from loguru import logger


def main():
    """Analyze current data state."""

    logger.info("Analyzing current OHLC data state...")
    supabase = SupabaseClient()

    print("\n" + "=" * 80)
    print("📊 OHLC DATA ANALYSIS")
    print("=" * 80)

    # 1. Check 1-minute data (using head request to avoid timeout)
    print("\n🕐 1-MINUTE DATA:")
    print("-" * 60)

    try:
        # Try to get count using head request
        result = (
            supabase.client.table("ohlc_data")
            .select("*", count="exact", head=True)
            .eq("timeframe", "1m")
            .execute()
        )

        if hasattr(result, "count") and result.count is not None:
            print(f"Total 1m rows: {result.count:,}")
        else:
            print("Count unavailable (too large)")
    except Exception as e:
        print(f"Cannot count 1m data (timeout): {str(e)[:50]}")

    # Get date range for 1m data
    try:
        oldest = (
            supabase.client.table("ohlc_data")
            .select("timestamp")
            .eq("timeframe", "1m")
            .order("timestamp")
            .limit(1)
            .execute()
        )

        newest = (
            supabase.client.table("ohlc_data")
            .select("timestamp")
            .eq("timeframe", "1m")
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )

        if oldest.data and newest.data:
            oldest_date = oldest.data[0]["timestamp"]
            newest_date = newest.data[0]["timestamp"]

            oldest_dt = datetime.fromisoformat(oldest_date.replace("Z", "+00:00"))
            newest_dt = datetime.fromisoformat(newest_date.replace("Z", "+00:00"))

            days_of_data = (newest_dt - oldest_dt).days

            print(
                f"Oldest: {oldest_date[:19]} ({(datetime.now(timezone.utc) - oldest_dt).days} days ago)"
            )
            print(f"Newest: {newest_date[:19]}")
            print(f"Total span: {days_of_data} days")
    except Exception as e:
        print(f"Cannot get date range: {str(e)[:50]}")

    # Check recent 1m data (last 24 hours)
    try:
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        recent = (
            supabase.client.table("ohlc_data")
            .select("*", count="exact", head=True)
            .eq("timeframe", "1m")
            .gte("timestamp", yesterday)
            .execute()
        )

        if hasattr(recent, "count"):
            print(f"Last 24 hours: {recent.count:,} rows")
            print(f"Rate: ~{recent.count/24:.0f} rows/hour")
    except:
        pass

    # 2. Check 15-minute data
    print("\n📈 15-MINUTE DATA:")
    print("-" * 60)

    try:
        # Total 15m data
        result = (
            supabase.client.table("ohlc_data")
            .select("*", count="exact", head=True)
            .eq("timeframe", "15m")
            .execute()
        )

        if hasattr(result, "count"):
            print(f"Total 15m rows: {result.count:,}")

        # Check how much is older than 1 year
        one_year_ago = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
        old_15m = (
            supabase.client.table("ohlc_data")
            .select("*", count="exact", head=True)
            .eq("timeframe", "15m")
            .lt("timestamp", one_year_ago)
            .execute()
        )

        if hasattr(old_15m, "count"):
            print(f"Rows older than 1 year: {old_15m.count:,} (TO BE DELETED)")
            if result.count and old_15m.count:
                pct = (old_15m.count / result.count) * 100
                print(f"That's {pct:.1f}% of 15m data")
    except Exception as e:
        print(f"Error checking 15m data: {str(e)[:50]}")

    # 3. Check 1-hour data
    print("\n📊 1-HOUR DATA:")
    print("-" * 60)

    try:
        # Total 1h data
        result = (
            supabase.client.table("ohlc_data")
            .select("*", count="exact", head=True)
            .eq("timeframe", "1h")
            .execute()
        )

        if hasattr(result, "count"):
            print(f"Total 1h rows: {result.count:,}")

        # Check how much is older than 2 years
        two_years_ago = (datetime.now(timezone.utc) - timedelta(days=730)).isoformat()
        old_1h = (
            supabase.client.table("ohlc_data")
            .select("*", count="exact", head=True)
            .eq("timeframe", "1h")
            .lt("timestamp", two_years_ago)
            .execute()
        )

        if hasattr(old_1h, "count"):
            print(f"Rows older than 2 years: {old_1h.count:,} (TO BE DELETED)")
            if result.count and old_1h.count:
                pct = (old_1h.count / result.count) * 100
                print(f"That's {pct:.1f}% of 1h data")
    except Exception as e:
        print(f"Error checking 1h data: {str(e)[:50]}")

    # 4. Check scan_history
    print("\n📋 SCAN_HISTORY:")
    print("-" * 60)

    try:
        # Total scan_history
        result = (
            supabase.client.table("scan_history")
            .select("*", count="exact", head=True)
            .execute()
        )

        if hasattr(result, "count"):
            print(f"Total rows: {result.count:,}")

        # Check how much is older than 7 days
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        old_scans = (
            supabase.client.table("scan_history")
            .select("*", count="exact", head=True)
            .lt("timestamp", week_ago)
            .execute()
        )

        if hasattr(old_scans, "count"):
            print(f"Rows older than 7 days: {old_scans.count:,} (TO BE DELETED)")
    except Exception as e:
        print(f"Error checking scan_history: {str(e)[:50]}")

    # 5. Summary
    print("\n" + "=" * 80)
    print("💡 CLEANUP SUMMARY:")
    print("=" * 80)

    print(
        """
Based on your retention policy:
- 1-minute: Keep 30 days (appears to be current already)
- 15-minute: Keep 1 year (need to delete older data)
- 1-hour: Keep 2 years (need to delete older data)
- scan_history: Keep 7 days (need to delete older data)

The 1-minute data timeout suggests you have LOTS of recent 1m data,
which is expected if you're collecting 90 symbols at 1-min intervals.
This is about 130K rows/day, so 30 days = ~4 million rows.
"""
    )


if __name__ == "__main__":
    main()
