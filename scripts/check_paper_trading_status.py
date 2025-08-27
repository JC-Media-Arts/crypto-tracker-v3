#!/usr/bin/env python3
"""Check paper trading status and diagnose dashboard notification issue"""

import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.supabase_client import SupabaseClient


def check_scan_history():
    """Check recent scan history entries"""
    db = SupabaseClient()

    # Check for recent scans (last 30 minutes - matching dashboard logic)
    thirty_minutes_ago = (
        datetime.now(timezone.utc) - timedelta(minutes=30)
    ).isoformat()

    print("\n=== Checking Scan History (Last 30 Minutes) ===")
    print(f"Current UTC time: {datetime.now(timezone.utc).isoformat()}")
    print(f"Looking for entries after: {thirty_minutes_ago}")

    result = (
        db.client.table("scan_history")
        .select("timestamp, symbol, strategy_name, decision")
        .gte("timestamp", thirty_minutes_ago)
        .order("timestamp", desc=True)
        .limit(5)
        .execute()
    )

    if result.data:
        print(f"\nFound {len(result.data)} recent scans:")
        for scan in result.data:
            print(
                f"  - {scan['timestamp']}: {scan['symbol']} | {scan['strategy_name']} | {scan['decision']}"
            )
    else:
        print("\n❌ NO RECENT SCANS FOUND!")

        # Check last scan regardless of time
        last_scan = (
            db.client.table("scan_history")
            .select("timestamp, symbol, strategy_name")
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )

        if last_scan.data:
            last_time = last_scan.data[0]["timestamp"]
            print(f"\nLast scan was at: {last_time}")
            # Calculate time difference
            last_dt = datetime.fromisoformat(last_time.replace("Z", "+00:00"))
            time_diff = datetime.now(timezone.utc) - last_dt
            print(f"That was {time_diff.total_seconds() / 60:.1f} minutes ago")
        else:
            print("\nNo scans found in database at all!")

    return bool(result.data)


def check_paper_trades():
    """Check recent paper trades"""
    db = SupabaseClient()

    thirty_minutes_ago = (
        datetime.now(timezone.utc) - timedelta(minutes=30)
    ).isoformat()

    print("\n=== Checking Paper Trades (Last 30 Minutes) ===")

    result = (
        db.client.table("paper_trades")
        .select("created_at, symbol, side, strategy_name")
        .gte("created_at", thirty_minutes_ago)
        .order("created_at", desc=True)
        .limit(5)
        .execute()
    )

    if result.data:
        print(f"\nFound {len(result.data)} recent trades:")
        for trade in result.data:
            print(
                f"  - {trade['created_at']}: {trade['symbol']} | {trade['side']} | {trade['strategy_name']}"
            )
    else:
        print(
            "\n❌ NO RECENT TRADES FOUND (this is normal if no buy/sell conditions met)"
        )

        # Check last trade
        last_trade = (
            db.client.table("paper_trades")
            .select("created_at, symbol, side")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if last_trade.data:
            last_time = last_trade.data[0]["created_at"]
            print(f"\nLast trade was at: {last_time}")
            # Calculate time difference
            last_dt = datetime.fromisoformat(last_time.replace("Z", "+00:00"))
            time_diff = datetime.now(timezone.utc) - last_dt
            print(f"That was {time_diff.total_seconds() / 60:.1f} minutes ago")

    return bool(result.data)


def check_strategy_cache():
    """Check if pre-calculator is updating strategy cache"""
    db = SupabaseClient()

    print("\n=== Checking Strategy Status Cache ===")

    result = (
        db.client.table("strategy_status_cache")
        .select("calculated_at, symbol, strategy_name, status")
        .order("calculated_at", desc=True)
        .limit(5)
        .execute()
    )

    if result.data:
        first = result.data[0]
        print(f"Last cache update: {first['calculated_at']}")

        # Check how old the cache is
        last_dt = datetime.fromisoformat(first["calculated_at"].replace("Z", "+00:00"))
        time_diff = datetime.now(timezone.utc) - last_dt
        print(f"Cache age: {time_diff.total_seconds() / 60:.1f} minutes")

        print(f"\nRecent cache entries:")
        for entry in result.data[:3]:
            print(
                f"  - {entry['symbol']} | {entry['strategy_name']} | {entry['status']}"
            )
    else:
        print("❌ No cache data found!")


def diagnose_dashboard_issue():
    """Main diagnosis function"""
    print("=" * 60)
    print("PAPER TRADING STATUS DIAGNOSIS")
    print("=" * 60)

    # Check both conditions that dashboard uses
    has_recent_scans = check_scan_history()
    has_recent_trades = check_paper_trades()

    # Check cache
    check_strategy_cache()

    print("\n" + "=" * 60)
    print("DIAGNOSIS SUMMARY")
    print("=" * 60)

    if has_recent_scans or has_recent_trades:
        print("\n✅ Paper trading should show as RUNNING")
        print("Dashboard should NOT show 'Paper Trading Stopped'")
        print("\nPossible issues:")
        print("1. Dashboard might be caching old status")
        print("2. Try refreshing the dashboard page (Ctrl+F5)")
        print("3. Check if Railway environment variable is set properly")
    else:
        print("\n❌ Paper trading appears to be STOPPED or STALLED")
        print("Dashboard is correctly showing 'Paper Trading Stopped'")
        print("\nPossible causes:")
        print("1. Paper trading service crashed or stopped")
        print("2. Paper trading is running but not logging scans")
        print("3. Database connection issue in paper trading service")
        print("4. Check Railway logs for the Paper Trading service")
        print("\nSuggested actions:")
        print("1. Check Railway dashboard for Paper Trading service status")
        print("2. Look at Railway logs for any errors")
        print("3. Restart the Paper Trading service on Railway")

    # Check environment
    print("\n" + "=" * 60)
    print("ENVIRONMENT CHECK")
    print("=" * 60)

    is_railway = os.environ.get("RAILWAY_ENVIRONMENT")
    print(f"RAILWAY_ENVIRONMENT: {is_railway or 'Not set (running locally)'}")

    if not is_railway:
        print("\nNote: Running this script locally. The dashboard on Railway")
        print("checks the same database tables but from within Railway environment.")


if __name__ == "__main__":
    diagnose_dashboard_issue()
