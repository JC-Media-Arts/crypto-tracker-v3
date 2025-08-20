#!/usr/bin/env python3
"""
Create indexes using Supabase CLI to avoid transaction block issues.
This script connects directly to PostgreSQL and runs CREATE INDEX CONCURRENTLY.
"""

import os
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config.settings import get_settings


def get_database_url():
    """Get the database URL from settings."""
    settings = get_settings()

    # Parse Supabase URL to get project reference
    # Format: https://[PROJECT_REF].supabase.co
    project_ref = settings.supabase_url.split("//")[1].split(".")[0]

    # Construct PostgreSQL connection URL
    # Note: You'll need to provide the password
    db_url = (
        f"postgresql://postgres:[PASSWORD]@db.{project_ref}.supabase.co:5432/postgres"
    )

    print("\n" + "=" * 60)
    print("DATABASE CONNECTION SETUP")
    print("=" * 60)
    print(f"\nProject Reference: {project_ref}")
    print("\nYou need to provide your database password.")
    print("Find it in your Supabase Dashboard:")
    print("1. Go to Settings > Database")
    print("2. Copy the password from 'Database Password'")
    print("\nEnter your database password: ", end="")

    password = input().strip()

    if not password:
        print("❌ Password is required")
        sys.exit(1)

    db_url = db_url.replace("[PASSWORD]", password)
    return db_url


def run_sql_command(db_url, sql_command, description):
    """Run a SQL command using psql."""
    print(f"\n📊 {description}")
    print(f"   Command: {sql_command[:80]}...")
    print(f"   Started: {datetime.now().strftime('%H:%M:%S')}")

    start_time = time.time()

    # Use psql to run the command
    cmd = ["psql", db_url, "-c", sql_command]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        elapsed = time.time() - start_time
        print(f"   ✅ Completed in {elapsed:.1f} seconds")

        if result.stdout:
            print(f"   Output: {result.stdout[:200]}")

        return True

    except subprocess.CalledProcessError as e:
        elapsed = time.time() - start_time
        print(f"   ❌ Failed after {elapsed:.1f} seconds")
        print(f"   Error: {e.stderr}")
        return False
    except FileNotFoundError:
        print("   ❌ psql not found. Please install PostgreSQL client tools:")
        print("      brew install postgresql")
        return False


def monitor_index_progress(db_url):
    """Check if any indexes are being created."""
    sql = """
    SELECT
        pid,
        now() - pg_stat_activity.query_start AS duration,
        left(query, 100) as query_preview
    FROM pg_stat_activity
    WHERE query LIKE '%CREATE INDEX%'
    AND state = 'active';
    """

    cmd = ["psql", db_url, "-c", sql, "-t"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout.strip():
            print("\n📈 Active Index Creation:")
            print(result.stdout)
            return True
        return False
    except:
        return False


def check_existing_indexes(db_url):
    """Check what indexes already exist."""
    sql = """
    SELECT
        indexname,
        pg_size_pretty(pg_relation_size(indexname::regclass)) as size
    FROM pg_indexes
    WHERE tablename = 'ohlc_data'
    ORDER BY indexname;
    """

    print("\n📋 Existing Indexes on ohlc_data:")

    cmd = ["psql", db_url, "-c", sql]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout)
    except:
        print("Could not check existing indexes")


def main():
    print("\n" + "=" * 60)
    print("CREATE INDEXES WITH CONCURRENTLY")
    print("=" * 60)
    print("\nThis script will create indexes without locking the table.")
    print("Estimated time: 1-3 hours total")

    # Get database connection
    db_url = get_database_url()

    # Check existing indexes
    check_existing_indexes(db_url)

    # Confirm before proceeding
    print("\n⚠️  WARNING: This will create large indexes and may take hours.")
    print("Continue? (y/n): ", end="")

    if input().strip().lower() != "y":
        print("Cancelled")
        return

    # Set session timeout
    print("\n" + "=" * 60)
    print("CREATING INDEXES")
    print("=" * 60)

    success_count = 0

    # Index 1: Main composite index
    if run_sql_command(
        db_url,
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_symbol_time ON ohlc_data(symbol, timeframe, timestamp DESC);",
        "Creating main composite index (may take 1-2 hours)",
    ):
        success_count += 1

    # Index 2: BRIN index for timestamps
    if run_sql_command(
        db_url,
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_timestamp_brin ON ohlc_data USING BRIN(timestamp);",
        "Creating BRIN index for timestamps (5-10 minutes)",
    ):
        success_count += 1

    # Index 3: Partial index for recent data
    if run_sql_command(
        db_url,
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_recent_90d ON ohlc_data(symbol, timeframe, timestamp DESC) WHERE timestamp > '2024-10-22'::timestamptz;",
        "Creating partial index for recent 90 days",
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
        print("You can re-run this script to retry failed indexes.")
    else:
        print("\n❌ No indexes were created. Check your connection and try again.")

    # Show final index status
    check_existing_indexes(db_url)


if __name__ == "__main__":
    main()
