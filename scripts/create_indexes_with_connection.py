#!/usr/bin/env python3
"""
Create indexes using saved connection string.
Run get_db_connection.py first to save your connection string.
"""

import os
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path


def run_sql_command(connection_string, sql_command, description):
    """Run a SQL command using psql."""
    print(f"\n📊 {description}")
    print(f"   Started: {datetime.now().strftime('%H:%M:%S')}")

    start_time = time.time()

    # Add psql to PATH
    os.environ["PATH"] = "/opt/homebrew/opt/postgresql@16/bin:" + os.environ.get(
        "PATH", ""
    )

    # Use psql to run the command
    cmd = ["psql", connection_string, "-c", sql_command]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        elapsed = time.time() - start_time
        print(f"   ✅ Completed in {elapsed:.1f} seconds")

        return True

    except subprocess.CalledProcessError as e:
        elapsed = time.time() - start_time
        print(f"   ❌ Failed after {elapsed:.1f} seconds")

        error_msg = e.stderr

        if "already exists" in error_msg.lower():
            print(f"   ℹ️  Index already exists (skipping)")
            return True
        elif "cannot run inside a transaction block" in error_msg:
            print(f"   ❌ Cannot use CONCURRENTLY with this connection")
            print(f"   Try running without CONCURRENTLY (will lock table briefly)")
            return False
        else:
            print(f"   Error: {error_msg[:200]}")
            return False


def main():
    print("\n" + "=" * 60)
    print("CREATE INDEXES ON OHLC_DATA")
    print("=" * 60)

    # Load saved connection string
    if not os.path.exists(".db_connection_string.tmp"):
        print("\n❌ No saved connection string found.")
        print("Please run: python3 scripts/get_db_connection.py")
        sys.exit(1)

    with open(".db_connection_string.tmp", "r") as f:
        connection_string = f.read().strip()

    print("\n✅ Using saved connection string")

    # Confirm before proceeding
    print("\n⚠️  This will create large indexes and may take 1-3 hours.")
    print("The table may be locked briefly if CONCURRENTLY doesn't work.")
    print("\nContinue? (y/n): ", end="")

    if input().strip().lower() != "y":
        print("Cancelled")
        return

    print("\n" + "=" * 60)
    print("CREATING INDEXES")
    print("=" * 60)

    success_count = 0

    # First, try with CONCURRENTLY
    print("\nAttempting to create indexes without locking table (CONCURRENTLY)...")

    # Index 1: Main composite index
    if run_sql_command(
        connection_string,
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_symbol_time ON ohlc_data(symbol, timeframe, timestamp DESC);",
        "Creating main composite index (may take 1-2 hours)",
    ):
        success_count += 1
    else:
        # Try without CONCURRENTLY
        print("\n   Retrying without CONCURRENTLY (will lock table)...")
        if run_sql_command(
            connection_string,
            "CREATE INDEX IF NOT EXISTS idx_ohlc_symbol_time ON ohlc_data(symbol, timeframe, timestamp DESC);",
            "Creating main composite index (with table lock)",
        ):
            success_count += 1

    # Index 2: BRIN index for timestamps
    if run_sql_command(
        connection_string,
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_timestamp_brin ON ohlc_data USING BRIN(timestamp);",
        "Creating BRIN index for timestamps (5-10 minutes)",
    ):
        success_count += 1
    else:
        # Try without CONCURRENTLY
        print("\n   Retrying without CONCURRENTLY (will lock table)...")
        if run_sql_command(
            connection_string,
            "CREATE INDEX IF NOT EXISTS idx_ohlc_timestamp_brin ON ohlc_data USING BRIN(timestamp);",
            "Creating BRIN index (with table lock)",
        ):
            success_count += 1

    # Index 3: Partial index for recent data
    if run_sql_command(
        connection_string,
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_recent_90d ON ohlc_data(symbol, timeframe, timestamp DESC) WHERE timestamp > '2024-10-22'::timestamptz;",
        "Creating partial index for recent 90 days",
    ):
        success_count += 1
    else:
        # Try without CONCURRENTLY
        print("\n   Retrying without CONCURRENTLY (will lock table)...")
        if run_sql_command(
            connection_string,
            "CREATE INDEX IF NOT EXISTS idx_ohlc_recent_90d ON ohlc_data(symbol, timeframe, timestamp DESC) WHERE timestamp > '2024-10-22'::timestamptz;",
            "Creating partial index (with table lock)",
        ):
            success_count += 1

    # Final summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"\n✅ Successfully created {success_count}/3 indexes")

    if success_count == 3:
        print("\n🎉 All indexes created successfully!")
        print("\nYour database now has:")
        print("1. Materialized views for recent data (primary performance)")
        print("2. Full indexes for historical queries (backup performance)")
        print("\nThe system should be blazing fast for all queries!")
    elif success_count > 0:
        print("\n⚠️  Some indexes were created. Check errors above.")
    else:
        print("\n❌ No indexes were created. Check your connection.")

    # Clean up temp file
    if os.path.exists(".db_connection_string.tmp"):
        os.remove(".db_connection_string.tmp")
        print("\n🧹 Cleaned up temporary connection file")


if __name__ == "__main__":
    main()
