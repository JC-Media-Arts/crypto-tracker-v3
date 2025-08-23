#!/usr/bin/env python3
"""
Emergency solution for index creation - uses materialized views instead.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from supabase import create_client
from datetime import datetime, timedelta
import time


def create_materialized_view_solution():
    """Create a materialized view as a workaround for index timeout."""
    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_key)

    print("=" * 60)
    print("EMERGENCY INDEX SOLUTION - MATERIALIZED VIEW")
    print("=" * 60)

    # Step 1: Check how much recent data we have
    print("\n1. Checking data volume...")
    try:
        # Count last 7 days
        week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
        result = (
            supabase.table("ohlc_data").select("symbol", count="exact").gte("timestamp", week_ago).limit(1).execute()
        )
        print(f"   Records in last 7 days: ~{result.count:,}")

        # Count last 24 hours
        day_ago = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        result = (
            supabase.table("ohlc_data").select("symbol", count="exact").gte("timestamp", day_ago).limit(1).execute()
        )
        print(f"   Records in last 24 hours: ~{result.count:,}")

    except Exception as e:
        print(f"   Could not get counts: {e}")

    print("\n2. Creating materialized view...")
    print("   Copy and run this in Supabase SQL Editor:\n")

    sql_commands = """
-- STEP 1: Create a materialized view with just recent data
-- This is MUCH faster than creating an index
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlc_recent AS
SELECT * FROM ohlc_data
WHERE timestamp > (CURRENT_TIMESTAMP - INTERVAL '7 days');

-- STEP 2: Create indexes on the view (will be fast)
CREATE INDEX idx_mv_symbol_time ON ohlc_recent(symbol, timeframe, timestamp DESC);
CREATE INDEX idx_mv_timestamp ON ohlc_recent(timestamp DESC);
CREATE INDEX idx_mv_symbol ON ohlc_recent(symbol, timestamp DESC);

-- STEP 3: Grant permissions
GRANT SELECT ON ohlc_recent TO authenticated;
GRANT SELECT ON ohlc_recent TO anon;

-- STEP 4: Check the view size
SELECT
    pg_size_pretty(pg_relation_size('ohlc_recent')) as view_size,
    COUNT(*) as row_count
FROM ohlc_recent;
"""

    print(sql_commands)

    print("\n3. After creating the view, update your code to use it:")
    print("   - For recent queries (last 7 days): Use 'ohlc_recent' table")
    print("   - For historical queries: Use 'ohlc_data' table")

    print("\n4. Set up automatic refresh (run daily):")
    print("   REFRESH MATERIALIZED VIEW CONCURRENTLY ohlc_recent;")

    return True


def create_code_wrapper():
    """Create a wrapper to use the materialized view."""

    code = '''
# Add this to your data fetcher to use the materialized view:

class HybridDataFetcher:
    """Uses materialized view for recent data, main table for historical."""

    def __init__(self):
        self.recent_days_threshold = 7  # Days covered by materialized view

    async def get_ohlc_data(self, symbol, timeframe, start_date, end_date):
        """Automatically choose between view and main table."""

        days_ago = (datetime.utcnow() - start_date).days

        if days_ago <= self.recent_days_threshold:
            # Use fast materialized view
            table_name = 'ohlc_recent'
            print(f"Using materialized view for {symbol}")
        else:
            # Use main table for historical
            table_name = 'ohlc_data'
            print(f"Using main table for {symbol}")

        # Query the appropriate table
        result = supabase.table(table_name)\\
            .select('*')\\
            .eq('symbol', symbol)\\
            .eq('timeframe', timeframe)\\
            .gte('timestamp', start_date.isoformat())\\
            .lte('timestamp', end_date.isoformat())\\
            .execute()

        return result.data
'''

    print("\n" + "=" * 60)
    print("CODE UPDATE NEEDED")
    print("=" * 60)
    print(code)


if __name__ == "__main__":
    create_materialized_view_solution()
    create_code_wrapper()

    print("\n" + "=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    print("1. Run the SQL commands above in Supabase SQL Editor")
    print("2. If the view creation also times out, you MUST contact Supabase support")
    print("3. Update your code to use 'ohlc_recent' for recent queries")
    print("4. Set up a daily cron job to refresh the materialized view")

    print("\n⚠️  IMPORTANT: If even the materialized view times out,")
    print("    you need Supabase support to intervene immediately.")
