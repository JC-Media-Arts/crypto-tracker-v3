#!/usr/bin/env python3
"""
Monitor index creation progress in real-time.
Run this in a separate terminal while indexes are being created.
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
    project_ref = settings.supabase_url.split("//")[1].split(".")[0]

    print(f"Project Reference: {project_ref}")
    print("Enter your database password: ", end="")

    password = input().strip()

    if not password:
        print("❌ Password is required")
        sys.exit(1)

    db_url = (
        f"postgresql://postgres:{password}@db.{project_ref}.supabase.co:5432/postgres"
    )
    return db_url


def check_active_indexes(db_url):
    """Check for active index creation."""
    sql = """
    SELECT
        pid,
        now() - pg_stat_activity.query_start AS duration,
        state,
        wait_event_type,
        wait_event,
        left(query, 150) as query
    FROM pg_stat_activity
    WHERE (query LIKE '%CREATE INDEX%' OR query LIKE '%REINDEX%')
    AND pid != pg_backend_pid()
    ORDER BY query_start;
    """

    cmd = ["psql", db_url, "-c", sql, "-x"]  # -x for expanded display

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.stdout
    except:
        return None


def check_index_sizes(db_url):
    """Check sizes of all indexes on ohlc_data."""
    sql = """
    SELECT
        indexname,
        pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size,
        pg_size_pretty(pg_total_relation_size(indexname::regclass)) as total_size
    FROM pg_indexes
    WHERE tablename = 'ohlc_data'
    AND schemaname = 'public'
    ORDER BY pg_relation_size(indexname::regclass) DESC;
    """

    cmd = ["psql", db_url, "-c", sql, "-t"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.stdout
    except:
        return None


def check_table_stats(db_url):
    """Check table statistics."""
    sql = """
    SELECT
        relname as table_name,
        pg_size_pretty(pg_total_relation_size(C.oid)) AS total_size,
        n_live_tup as live_rows,
        n_dead_tup as dead_rows,
        last_vacuum,
        last_autovacuum
    FROM pg_stat_user_tables S
    JOIN pg_class C ON S.relid = C.oid
    WHERE relname = 'ohlc_data';
    """

    cmd = ["psql", db_url, "-c", sql, "-x"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.stdout
    except:
        return None


def check_lock_status(db_url):
    """Check for any locks on the table."""
    sql = """
    SELECT
        pid,
        mode,
        granted,
        now() - pg_stat_activity.query_start AS duration,
        left(query, 100) as query
    FROM pg_locks
    JOIN pg_stat_activity ON pg_locks.pid = pg_stat_activity.pid
    WHERE relation = 'ohlc_data'::regclass
    AND pg_locks.pid != pg_backend_pid();
    """

    cmd = ["psql", db_url, "-c", sql, "-t"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        output = result.stdout.strip()
        return output if output else "No locks detected"
    except:
        return None


def monitor_loop(db_url):
    """Main monitoring loop."""
    print("\n" + "=" * 60)
    print("INDEX CREATION MONITOR")
    print("=" * 60)
    print("\nPress Ctrl+C to stop monitoring\n")

    iteration = 0

    while True:
        iteration += 1

        # Clear screen (optional - comment out if you want to keep history)
        # os.system('clear' if os.name == 'posix' else 'cls')

        print(f"\n{'=' * 60}")
        print(f"Update #{iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # Check active index creation
        print("\n📊 ACTIVE INDEX CREATION:")
        print("-" * 40)
        active = check_active_indexes(db_url)
        if active and "CREATE INDEX" in active:
            print(active)
        else:
            print("No active index creation detected")

        # Check index sizes
        print("\n📈 INDEX SIZES:")
        print("-" * 40)
        sizes = check_index_sizes(db_url)
        if sizes:
            print(sizes)
        else:
            print("Could not retrieve index sizes")

        # Check table stats
        print("\n📋 TABLE STATISTICS:")
        print("-" * 40)
        stats = check_table_stats(db_url)
        if stats:
            print(stats)

        # Check locks
        print("\n🔒 LOCK STATUS:")
        print("-" * 40)
        locks = check_lock_status(db_url)
        if locks:
            print(locks)

        # Wait before next update
        print(f"\nNext update in 30 seconds... (Press Ctrl+C to stop)")
        time.sleep(30)


def main():
    print("\n" + "=" * 60)
    print("INDEX CREATION PROGRESS MONITOR")
    print("=" * 60)
    print("\nThis will monitor index creation progress in real-time.")
    print("Run this in a separate terminal while creating indexes.\n")

    # Check if psql is available
    try:
        subprocess.run(["psql", "--version"], capture_output=True, check=True)
    except FileNotFoundError:
        print("❌ psql not found. Please install PostgreSQL client tools:")
        print("   brew install postgresql")
        sys.exit(1)

    # Get database connection
    db_url = get_database_url()

    # Test connection
    print("\nTesting database connection...")
    test_cmd = ["psql", db_url, "-c", "SELECT 1;"]

    try:
        subprocess.run(test_cmd, capture_output=True, check=True)
        print("✅ Connected successfully!\n")
    except subprocess.CalledProcessError:
        print("❌ Failed to connect. Check your password and try again.")
        sys.exit(1)

    # Start monitoring
    try:
        monitor_loop(db_url)
    except KeyboardInterrupt:
        print("\n\n✅ Monitoring stopped")

        # Show final status
        print("\n" + "=" * 60)
        print("FINAL STATUS")
        print("=" * 60)

        sizes = check_index_sizes(db_url)
        if sizes:
            print("\n📊 Final Index Sizes:")
            print(sizes)


if __name__ == "__main__":
    main()
