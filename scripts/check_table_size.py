#!/usr/bin/env python3
"""
Check OHLC table size and stats to understand the timeout issue.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from supabase import create_client


def main():
    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_key)

    print("Checking OHLC table statistics...")
    print("=" * 60)

    # Get row count (approximate)
    try:
        result = supabase.table("ohlc_data").select("id", count="exact").limit(1).execute()
        print(f"Total rows: {result.count:,}")
    except Exception as e:
        print(f"Could not get exact count: {e}")

        # Try approximate count
        try:
            result = supabase.table("ohlc_data").select("id").limit(1).execute()
            print("Table exists but count unavailable")
        except Exception as e2:
            print(f"Error accessing table: {e2}")

    # Check existing indexes
    print("\nChecking existing indexes...")
    query = """
    SELECT
        indexname,
        indexdef
    FROM pg_indexes
    WHERE tablename = 'ohlc_data'
    ORDER BY indexname;
    """

    try:
        # Use raw SQL through Supabase RPC or REST API
        result = supabase.rpc("get_indexes", {"table_name": "ohlc_data"}).execute()
        print(f"Existing indexes: {result.data}")
    except:
        print("Could not retrieve index information via RPC")
        print("You may need to check indexes manually in Supabase dashboard")

    # Get date range
    print("\nChecking data date range...")
    try:
        # Get oldest
        oldest = supabase.table("ohlc_data").select("timestamp").order("timestamp").limit(1).execute()
        if oldest.data:
            print(f"Oldest data: {oldest.data[0]['timestamp']}")

        # Get newest
        newest = supabase.table("ohlc_data").select("timestamp").order("timestamp", desc=True).limit(1).execute()
        if newest.data:
            print(f"Newest data: {newest.data[0]['timestamp']}")
    except Exception as e:
        print(f"Could not get date range: {e}")

    print("\n" + "=" * 60)
    print("RECOMMENDATION:")
    print("If you have millions of rows, indexes need to be created")
    print("during low-traffic periods or through Supabase support.")
    print("Contact Supabase support to create indexes if timeouts persist.")


if __name__ == "__main__":
    main()
