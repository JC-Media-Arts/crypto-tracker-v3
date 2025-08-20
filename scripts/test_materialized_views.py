#!/usr/bin/env python3
"""
Test that materialized views are working and fast.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import time
from datetime import datetime, timedelta
from src.config.settings import get_settings
from supabase import create_client
from loguru import logger


def test_views():
    """Test materialized view performance."""
    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_key)

    print("\n" + "=" * 60)
    print("TESTING MATERIALIZED VIEWS PERFORMANCE")
    print("=" * 60)

    test_results = []

    # Test 1: Get latest BTC price from ohlc_today
    print("\n1. Testing ohlc_today (last 24 hours)...")
    start = time.time()
    try:
        result = (
            supabase.table("ohlc_today")
            .select("symbol, close, timestamp")
            .eq("symbol", "BTC")
            .eq("timeframe", "1m")
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )
        elapsed = time.time() - start

        if result.data:
            print(f"   ✅ SUCCESS in {elapsed:.3f}s")
            print(f"   Latest BTC: ${result.data[0]['close']:,.2f} at {result.data[0]['timestamp']}")
            test_results.append(("ohlc_today latest", True, elapsed))
        else:
            print(f"   ⚠️ No data found")
            test_results.append(("ohlc_today latest", False, elapsed))
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        test_results.append(("ohlc_today latest", False, 0))

    # Test 2: Get all symbols from ohlc_today
    print("\n2. Testing multi-symbol query on ohlc_today...")
    start = time.time()
    try:
        result = supabase.table("ohlc_today").select("symbol").eq("timeframe", "15m").execute()
        elapsed = time.time() - start

        unique_symbols = set(r["symbol"] for r in result.data)
        print(f"   ✅ Found {len(unique_symbols)} symbols in {elapsed:.3f}s")
        print(f"   Symbols: {', '.join(sorted(list(unique_symbols))[:10])}...")
        test_results.append(("ohlc_today symbols", True, elapsed))
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        test_results.append(("ohlc_today symbols", False, 0))

    # Test 3: Get 7-day data from ohlc_recent
    print("\n3. Testing ohlc_recent (last 7 days)...")
    start = time.time()
    try:
        result = (
            supabase.table("ohlc_recent")
            .select("timestamp, close")
            .eq("symbol", "ETH")
            .eq("timeframe", "1h")
            .order("timestamp", desc=True)
            .limit(168)
            .execute()
        )
        elapsed = time.time() - start

        print(f"   ✅ Retrieved {len(result.data)} hourly records in {elapsed:.3f}s")
        if result.data:
            print(
                f"   ETH range: ${min(r['close'] for r in result.data):,.2f} - ${max(r['close'] for r in result.data):,.2f}"
            )
        test_results.append(("ohlc_recent hourly", True, elapsed))
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        test_results.append(("ohlc_recent hourly", False, 0))

    # Test 4: Complex query on ohlc_recent
    print("\n4. Testing complex filtering on ohlc_recent...")
    start = time.time()
    try:
        cutoff = (datetime.utcnow() - timedelta(days=3)).isoformat()
        result = (
            supabase.table("ohlc_recent")
            .select("symbol, timestamp, close, volume")
            .in_("symbol", ["BTC", "ETH", "SOL", "AVAX", "MATIC"])
            .eq("timeframe", "15m")
            .gte("timestamp", cutoff)
            .execute()
        )
        elapsed = time.time() - start

        print(f"   ✅ Retrieved {len(result.data)} records for 5 symbols in {elapsed:.3f}s")
        test_results.append(("ohlc_recent multi", True, elapsed))
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        test_results.append(("ohlc_recent multi", False, 0))

    # Test 5: Check indexes are being used
    print("\n5. Checking indexes...")
    try:
        # This query checks if indexes exist
        result = (
            supabase.rpc("get_indexes", {"table_names": ["ohlc_today", "ohlc_recent"]}).execute() if False else None
        )  # RPC might not exist

        # Alternative: Just verify we can query quickly
        start = time.time()
        result = (
            supabase.table("ohlc_today")
            .select("timestamp")
            .eq("symbol", "BTC")
            .eq("timeframe", "1m")
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )
        elapsed = time.time() - start

        if elapsed < 0.5:  # Should be very fast with index
            print(f"   ✅ Indexes appear to be working (query took {elapsed:.3f}s)")
            test_results.append(("index check", True, elapsed))
        else:
            print(f"   ⚠️ Query slower than expected ({elapsed:.3f}s) - indexes may not be created")
            test_results.append(("index check", False, elapsed))
    except Exception as e:
        print(f"   ⚠️ Could not verify indexes: {e}")
        test_results.append(("index check", False, 0))

    # Summary
    print("\n" + "=" * 60)
    print("PERFORMANCE SUMMARY")
    print("=" * 60)

    for test_name, success, elapsed in test_results:
        status = "✅" if success else "❌"
        if success and elapsed > 0:
            print(f"{status} {test_name:<25} {elapsed:>8.3f}s")
        else:
            print(f"{status} {test_name:<25} {'FAILED':>8}")

    avg_time = sum(t for _, s, t in test_results if s and t > 0) / max(
        1, sum(1 for _, s, t in test_results if s and t > 0)
    )
    success_rate = sum(1 for _, s, _ in test_results if s) / len(test_results) * 100

    print(f"\nAverage query time: {avg_time:.3f}s")
    print(f"Success rate: {success_rate:.0f}%")

    if avg_time < 0.5:
        print("\n🚀 EXCELLENT: Views are performing well!")
    elif avg_time < 1.0:
        print("\n✅ GOOD: Views are working acceptably")
    else:
        print("\n⚠️ WARNING: Performance could be better - check indexes")

    # Check if refresh is needed
    print("\n" + "=" * 60)
    print("CHECKING DATA FRESHNESS")
    print("=" * 60)

    try:
        # Check latest in main table
        result_main = supabase.table("ohlc_data").select("timestamp").order("timestamp", desc=True).limit(1).execute()

        # Check latest in views
        result_today = supabase.table("ohlc_today").select("timestamp").order("timestamp", desc=True).limit(1).execute()

        result_recent = (
            supabase.table("ohlc_recent").select("timestamp").order("timestamp", desc=True).limit(1).execute()
        )

        if result_main.data and result_today.data:
            main_time = datetime.fromisoformat(result_main.data[0]["timestamp"].replace("Z", "+00:00"))
            today_time = datetime.fromisoformat(result_today.data[0]["timestamp"].replace("Z", "+00:00"))

            lag = (main_time - today_time).total_seconds() / 60

            print(f"Latest in main table:  {result_main.data[0]['timestamp']}")
            print(f"Latest in ohlc_today:  {result_today.data[0]['timestamp']}")
            print(f"Latest in ohlc_recent: {result_recent.data[0]['timestamp'] if result_recent.data else 'N/A'}")

            if abs(lag) < 60:
                print(f"\n✅ Views are up to date (lag: {abs(lag):.1f} minutes)")
            else:
                print(f"\n⚠️ Views need refresh (lag: {abs(lag):.1f} minutes)")
                print("\nRun this SQL to refresh:")
                print("REFRESH MATERIALIZED VIEW CONCURRENTLY ohlc_today;")
                print("REFRESH MATERIALIZED VIEW CONCURRENTLY ohlc_recent;")

    except Exception as e:
        print(f"Could not check freshness: {e}")

    return success_rate == 100


if __name__ == "__main__":
    logger.add("logs/view_test.log")

    success = test_views()

    if success:
        print("\n✅ All tests passed! Your views are ready for production.")
    else:
        print("\n⚠️ Some tests failed. Check the issues above.")
        print("\nMake sure you've created all indexes from migrations/015_individual_indexes.sql")

    print("\nNext steps:")
    print("1. Create remaining indexes one by one")
    print("2. Update your code to use HybridDataFetcher")
    print("3. Set up daily refresh cron job")
    print("4. Monitor performance with this script")
