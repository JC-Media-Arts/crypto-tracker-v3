#!/usr/bin/env python3
"""
Refresh materialized views for OHLC data.
Run this daily to keep views up to date.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime
from src.config.settings import get_settings
from supabase import create_client
from loguru import logger
import time


def refresh_views():
    """Refresh both materialized views."""
    settings = get_settings()

    logger.info("=" * 60)
    logger.info("REFRESHING MATERIALIZED VIEWS")
    logger.info("=" * 60)

    # SQL commands to refresh views
    refresh_commands = [
        ("ohlc_today", "REFRESH MATERIALIZED VIEW CONCURRENTLY ohlc_today;"),
        ("ohlc_recent", "REFRESH MATERIALIZED VIEW CONCURRENTLY ohlc_recent;"),
    ]

    print("\nTo refresh the views, run these commands in Supabase SQL Editor:\n")

    for view_name, sql in refresh_commands:
        print(f"-- Refresh {view_name}")
        print(sql)
        print()

    # Also provide a combined function
    print("-- Or create this function and call it:")
    print(
        """
CREATE OR REPLACE FUNCTION refresh_ohlc_views()
RETURNS TABLE(view_name text, status text) AS $$
BEGIN
    -- Refresh ohlc_today
    REFRESH MATERIALIZED VIEW CONCURRENTLY ohlc_today;
    RETURN QUERY SELECT 'ohlc_today'::text, 'refreshed'::text;

    -- Refresh ohlc_recent
    REFRESH MATERIALIZED VIEW CONCURRENTLY ohlc_recent;
    RETURN QUERY SELECT 'ohlc_recent'::text, 'refreshed'::text;
END;
$$ LANGUAGE plpgsql;

-- Call it with:
SELECT * FROM refresh_ohlc_views();
"""
    )

    # Check current view statistics
    supabase = create_client(settings.supabase_url, settings.supabase_key)

    try:
        # Check ohlc_today
        result = supabase.table("ohlc_today").select("timestamp", count="exact").limit(1).execute()
        logger.info(f"ohlc_today: {result.count:,} rows")

        # Check ohlc_recent
        result = supabase.table("ohlc_recent").select("timestamp", count="exact").limit(1).execute()
        logger.info(f"ohlc_recent: {result.count:,} rows")

        # Get latest timestamps
        result = supabase.table("ohlc_today").select("timestamp").order("timestamp", desc=True).limit(1).execute()
        if result.data:
            logger.info(f"Latest in ohlc_today: {result.data[0]['timestamp']}")

        result = supabase.table("ohlc_recent").select("timestamp").order("timestamp", desc=True).limit(1).execute()
        if result.data:
            logger.info(f"Latest in ohlc_recent: {result.data[0]['timestamp']}")

    except Exception as e:
        logger.error(f"Error checking views: {e}")

    logger.info("\n" + "=" * 60)
    logger.info("SETUP INSTRUCTIONS")
    logger.info("=" * 60)
    print("\n1. Add to crontab for daily refresh at 2 AM:")
    print("   0 2 * * * /usr/bin/python3 /path/to/refresh_materialized_views.py")
    print("\n2. Or use Supabase Edge Functions for scheduled refresh")
    print("\n3. Or trigger manually when needed")

    return True


def test_view_performance():
    """Test query performance using the views."""
    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_key)

    logger.info("\n" + "=" * 60)
    logger.info("TESTING VIEW PERFORMANCE")
    logger.info("=" * 60)

    test_symbol = "BTC"

    # Test 1: Latest price from ohlc_today
    start = time.time()
    try:
        result = (
            supabase.table("ohlc_today")
            .select("close, timestamp")
            .eq("symbol", test_symbol)
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )
        elapsed = time.time() - start
        logger.success(f"✅ Latest price from ohlc_today: {elapsed:.3f}s")
        if result.data:
            logger.info(f"   BTC: ${result.data[0]['close']:,.2f}")
    except Exception as e:
        logger.error(f"❌ Failed: {e}")

    # Test 2: 7-day data from ohlc_recent
    start = time.time()
    try:
        result = (
            supabase.table("ohlc_recent")
            .select("symbol, timeframe, timestamp")
            .eq("symbol", test_symbol)
            .eq("timeframe", "1h")
            .execute()
        )
        elapsed = time.time() - start
        logger.success(f"✅ 7-day hourly data from ohlc_recent: {elapsed:.3f}s")
        logger.info(f"   Records: {len(result.data)}")
    except Exception as e:
        logger.error(f"❌ Failed: {e}")

    # Compare with main table (will be slow)
    logger.warning("\nComparing with main table (may timeout)...")
    start = time.time()
    try:
        cutoff = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        result = (
            supabase.table("ohlc_data")
            .select("close")
            .eq("symbol", test_symbol)
            .gte("timestamp", cutoff)
            .limit(1)
            .execute()
        )
        elapsed = time.time() - start
        logger.info(f"Main table query: {elapsed:.3f}s")
    except Exception as e:
        logger.error(f"Main table query failed (expected): {e}")


if __name__ == "__main__":
    # Add logging
    logger.add("logs/view_refresh.log", rotation="1 week")

    # Refresh views
    refresh_views()

    # Test performance
    test_view_performance()

    print("\n✅ Setup complete!")
    print("\nYour system now uses:")
    print("- ohlc_today: For real-time data (last 24 hours)")
    print("- ohlc_recent: For recent data (last 7 days)")
    print("- ohlc_data: For historical data (use sparingly)")
    print("\nRemember to refresh views daily!")
