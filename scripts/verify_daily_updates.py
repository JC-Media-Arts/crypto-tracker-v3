#!/usr/bin/env python3
"""
Verify that daily OHLC updates are working correctly
Checks both historical data and recent updates
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import logging
from typing import Dict, List

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from supabase import create_client, Client

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


def check_data_freshness():
    """Check how fresh the OHLC data is for all symbols"""

    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_key)

    print("\n" + "=" * 80)
    print("OHLC DATA FRESHNESS CHECK")
    print("=" * 80)

    # Check data for different time windows
    time_windows = [
        ("Last Hour", timedelta(hours=1)),
        ("Last 24 Hours", timedelta(hours=24)),
        ("Last 7 Days", timedelta(days=7)),
        ("Last 30 Days", timedelta(days=30)),
    ]

    for window_name, delta in time_windows:
        cutoff = (datetime.utcnow() - delta).isoformat()

        print(f"\n{window_name}:")
        print("-" * 40)

        for timeframe in ["1m", "15m", "1h", "1d"]:
            try:
                # Get symbols with recent updates
                result = (
                    supabase.table("ohlc_data")
                    .select("symbol, timestamp")
                    .eq("timeframe", timeframe)
                    .gte("timestamp", cutoff)
                    .execute()
                )

                if result.data:
                    unique_symbols = set(row["symbol"] for row in result.data)
                    latest_timestamp = max(row["timestamp"] for row in result.data)

                    print(
                        f"  {timeframe:4s}: {len(unique_symbols):3d} symbols updated (latest: {latest_timestamp[:16]})"
                    )
                else:
                    print(f"  {timeframe:4s}: No updates")

            except Exception as e:
                print(f"  {timeframe:4s}: Error - {str(e)[:50]}")


def check_update_mechanisms():
    """Check which update mechanisms are configured"""

    print("\n" + "=" * 80)
    print("UPDATE MECHANISMS")
    print("=" * 80)

    # Check for running processes
    import subprocess

    print("\n1. CHECKING FOR RUNNING UPDATE PROCESSES:")
    print("-" * 40)

    processes_to_check = [
        ("Data Collector", "run_data_collector.py"),
        ("Incremental Updater", "incremental_ohlc_updater.py"),
        ("Feature Calculator", "run_feature_calculator.py"),
        ("Scheduler", "schedule_updates.py"),
    ]

    try:
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)

        for name, script in processes_to_check:
            if script in result.stdout:
                print(f"  ✅ {name} is running")
            else:
                print(f"  ⚠️  {name} is not running")
    except:
        print("  Could not check running processes")

    # Check for scheduled tasks
    print("\n2. SCHEDULED TASKS (crontab):")
    print("-" * 40)

    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)

        if result.returncode == 0 and result.stdout:
            print("  Found cron jobs:")
            for line in result.stdout.split("\n"):
                if "ohlc" in line.lower() or "update" in line.lower():
                    print(f"    {line}")
        else:
            print("  ⚠️  No cron jobs configured")
    except:
        print("  Could not check cron jobs")

    # Check Railway configuration
    print("\n3. RAILWAY SERVICES:")
    print("-" * 40)

    try:
        with open("railway.json", "r") as f:
            import json

            config = json.load(f)

            if "services" in config:
                for service_name, service_config in config["services"].items():
                    if "Data" in service_name or "Collector" in service_name:
                        print(f"  ✅ {service_name} configured")
                        if "cronSchedule" in service_config:
                            print(f"     Schedule: {service_config['cronSchedule']}")
    except:
        print("  Could not check Railway configuration")


def check_data_gaps():
    """Check for gaps in the data"""

    print("\n" + "=" * 80)
    print("DATA GAP ANALYSIS")
    print("=" * 80)

    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_key)

    # Sample check for BTC to identify gaps
    test_symbol = "BTC"

    print(f"\nChecking gaps for {test_symbol}:")
    print("-" * 40)

    for timeframe in ["1d", "1h", "15m"]:
        try:
            # Get recent data
            cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()

            result = (
                supabase.table("ohlc_data")
                .select("timestamp")
                .eq("symbol", test_symbol)
                .eq("timeframe", timeframe)
                .gte("timestamp", cutoff)
                .order("timestamp")
                .execute()
            )

            if result.data:
                timestamps = [datetime.fromisoformat(row["timestamp"].replace("+00:00", "")) for row in result.data]

                # Expected interval based on timeframe
                expected_delta = {
                    "1m": timedelta(minutes=1),
                    "15m": timedelta(minutes=15),
                    "1h": timedelta(hours=1),
                    "1d": timedelta(days=1),
                }[timeframe]

                # Find gaps
                gaps = []
                for i in range(1, len(timestamps)):
                    actual_delta = timestamps[i] - timestamps[i - 1]
                    if actual_delta > expected_delta * 1.5:  # Allow some tolerance
                        gaps.append({"start": timestamps[i - 1], "end": timestamps[i], "duration": actual_delta})

                if gaps:
                    print(f"  {timeframe}: ⚠️  {len(gaps)} gaps found")
                    for gap in gaps[:3]:  # Show first 3 gaps
                        print(f"       Gap: {gap['duration']} between {gap['start']} and {gap['end']}")
                else:
                    print(f"  {timeframe}: ✅ No gaps (continuous data)")

            else:
                print(f"  {timeframe}: No data in last 7 days")

        except Exception as e:
            print(f"  {timeframe}: Error - {str(e)[:50]}")


def provide_recommendations():
    """Provide recommendations for ensuring continuous updates"""

    print("\n" + "=" * 80)
    print("RECOMMENDATIONS FOR CONTINUOUS UPDATES")
    print("=" * 80)

    print(
        """
To ensure continuous OHLC data updates:

1. **IMMEDIATE: Start the Incremental Updater**
   Run this to catch up any missing recent data:
   ```bash
   python scripts/incremental_ohlc_updater.py
   ```

2. **FOR DEVELOPMENT: Run the Scheduler**
   This will handle periodic updates:
   ```bash
   python scripts/schedule_updates.py
   ```

3. **FOR PRODUCTION: Set up Cron Jobs**
   Add to crontab (crontab -e):
   ```bash
   # Update 1-minute data every 5 minutes
   */5 * * * * cd /Users/justincoit/crypto-tracker-v3 && python3 scripts/incremental_ohlc_updater.py --timeframe 1m

   # Update 15-minute data every 15 minutes
   */15 * * * * cd /Users/justincoit/crypto-tracker-v3 && python3 scripts/incremental_ohlc_updater.py --timeframe 15m

   # Update hourly data every hour
   0 * * * * cd /Users/justincoit/crypto-tracker-v3 && python3 scripts/incremental_ohlc_updater.py --timeframe 1h

   # Update daily data once per day at 1 AM
   0 1 * * * cd /Users/justincoit/crypto-tracker-v3 && python3 scripts/incremental_ohlc_updater.py --timeframe 1d
   ```

4. **FOR RAILWAY: Deploy the Data Collector Service**
   The Data Collector service is configured in railway.json
   Deploy it to Railway for continuous updates

5. **MONITORING: Set up Health Checks**
   Run periodically to ensure data is fresh:
   ```bash
   python scripts/verify_daily_updates.py
   ```

IMPORTANT: The incremental updater is smart and will:
- Only fetch new data since last update
- Handle rate limiting automatically
- Skip symbols that are already up-to-date
- Retry on failures
"""
    )


def main():
    """Run all verification checks"""

    print("\n" + "=" * 80)
    print("DAILY UPDATE VERIFICATION REPORT")
    print("=" * 80)
    print(f"Timestamp: {datetime.now()}")

    check_data_freshness()
    check_update_mechanisms()
    check_data_gaps()
    provide_recommendations()

    print("\n" + "=" * 80)
    print("VERIFICATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
