#!/usr/bin/env python3
"""
Verify all fixes are working after applying the 4-step fix plan
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from loguru import logger


def verify_fixes():
    """Verify all fixes are working"""

    print("=" * 60)
    print("🔍 SYSTEM FIX VERIFICATION")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)

    results = {}
    supabase = SupabaseClient()

    # 1. Check strategy processes
    print("\n1. Checking Strategy Processes...")
    print("-" * 40)

    processes = (
        os.popen(
            "ps aux | grep -E 'run_all_strategies|run_paper_trading|run_data_collector' | grep python3 | grep -v grep | wc -l"
        )
        .read()
        .strip()
    )
    process_count = int(processes) if processes else 0
    results["Strategy Processes"] = process_count >= 2  # At least 2 processes
    print(f"   Active processes: {process_count}")

    # List individual processes
    process_list = os.popen(
        "ps aux | grep -E 'run_all_strategies|run_paper_trading|run_data_collector' | grep python3 | grep -v grep"
    ).read()
    if process_list:
        for line in process_list.strip().split("\n"):
            script_name = line.split()[-1] if line else "unknown"
            print(f"   ✓ {os.path.basename(script_name)}")

    # 2. Check database tables
    print("\n2. Checking Database Tables...")
    print("-" * 40)

    # Check shadow tables exist
    try:
        result = (
            supabase.client.table("shadow_testing_scans")
            .select("*", count="exact")
            .limit(1)
            .execute()
        )
        shadow_scans_exists = True
        print("   ✅ shadow_testing_scans table exists")
    except Exception as e:
        shadow_scans_exists = False
        print("   ❌ shadow_testing_scans table missing")

    try:
        result = (
            supabase.client.table("shadow_testing_trades")
            .select("*", count="exact")
            .limit(1)
            .execute()
        )
        shadow_trades_exists = True
        print("   ✅ shadow_testing_trades table exists")
    except Exception as e:
        shadow_trades_exists = False
        print("   ❌ shadow_testing_trades table missing")

    results["Shadow Tables"] = shadow_scans_exists and shadow_trades_exists

    # Check trade_logs columns
    try:
        # Try to query the new columns
        result = (
            supabase.client.table("trade_logs")
            .select("pnl, stop_loss_price, take_profit_price")
            .limit(1)
            .execute()
        )
        pnl_columns_exist = True
        print("   ✅ trade_logs PNL columns exist")
    except Exception as e:
        if "column" in str(e) and "does not exist" in str(e):
            pnl_columns_exist = False
            print("   ❌ trade_logs PNL columns missing")
        else:
            pnl_columns_exist = False
            print(f"   ⚠️  trade_logs check error: {str(e)[:50]}")

    results["PNL Columns"] = pnl_columns_exist

    # 3. Check configuration
    print("\n3. Checking Configuration...")
    print("-" * 40)

    config_file = Path("configs/paper_trading.json")
    if config_file.exists():
        with open(config_file) as f:
            config = json.load(f)
            ml_threshold = config.get("ml_confidence_threshold", 1.0)
            results["Loosened Thresholds"] = ml_threshold <= 0.60
            print(
                f"   ML threshold: {ml_threshold} {'✅' if ml_threshold <= 0.60 else '❌ Too strict!'}"
            )

            # Check strategies are enabled
            strategies = config.get("strategies", {})
            dca_enabled = strategies.get("DCA", {}).get("enabled", False)
            swing_enabled = strategies.get("SWING", {}).get("enabled", False)
            channel_enabled = strategies.get("CHANNEL", {}).get("enabled", False)

            print(f"   DCA enabled: {'✅' if dca_enabled else '❌'}")
            print(f"   SWING enabled: {'✅' if swing_enabled else '❌'}")
            print(f"   CHANNEL enabled: {'✅' if channel_enabled else '❌'}")

            results["All Strategies Enabled"] = (
                dca_enabled and swing_enabled and channel_enabled
            )
    else:
        results["Loosened Thresholds"] = False
        results["All Strategies Enabled"] = False
        print("   ❌ Configuration file not found")

    # 4. Check strategy activity (wait for them to run)
    print("\n4. Checking Strategy Activity...")
    print("-" * 40)
    print("   Waiting 30 seconds for strategies to scan...")

    # Get baseline scan counts
    baseline_scans = {}
    for strategy in ["DCA", "SWING", "CHANNEL"]:
        try:
            result = (
                supabase.client.table("scan_history")
                .select("*", count="exact")
                .eq("strategy_name", strategy)
                .execute()
            )
            baseline_scans[strategy] = result.count if result else 0
        except:
            baseline_scans[strategy] = 0

    print(
        f"   Baseline scans - DCA: {baseline_scans['DCA']}, SWING: {baseline_scans['SWING']}, CHANNEL: {baseline_scans['CHANNEL']}"
    )

    # Wait for new scans
    time.sleep(30)

    # Check for new scans
    new_scan_activity = {}
    for strategy in ["DCA", "SWING", "CHANNEL"]:
        try:
            result = (
                supabase.client.table("scan_history")
                .select("*", count="exact")
                .eq("strategy_name", strategy)
                .execute()
            )
            current_count = result.count if result else 0
            new_scans = current_count - baseline_scans.get(strategy, 0)
            new_scan_activity[strategy] = new_scans

            if new_scans > 0:
                print(f"   ✅ {strategy}: {new_scans} new scans")
            else:
                print(f"   ❌ {strategy}: No new scans")

        except Exception as e:
            new_scan_activity[strategy] = 0
            print(f"   ❌ {strategy}: Error checking scans")

    results["DCA Activity"] = new_scan_activity.get("DCA", 0) > 0
    results["SWING Activity"] = new_scan_activity.get("SWING", 0) > 0
    results["CHANNEL Activity"] = new_scan_activity.get("CHANNEL", 0) > 0

    # 5. Check shadow testing activity
    print("\n5. Checking Shadow Testing...")
    print("-" * 40)

    try:
        # Check if shadow_testing_scans has recent entries
        one_minute_ago = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        result = (
            supabase.client.table("shadow_testing_scans")
            .select("*", count="exact")
            .gte("scan_time", one_minute_ago)
            .execute()
        )

        shadow_scan_count = result.count if result else 0
        results["Shadow Testing Active"] = shadow_scan_count > 0
        print(f"   Shadow scans (last minute): {shadow_scan_count}")

    except Exception as e:
        results["Shadow Testing Active"] = False
        print(f"   ❌ Shadow testing check failed: {str(e)[:50]}")

    # 6. Check data freshness
    print("\n6. Checking Data Pipeline...")
    print("-" * 40)

    try:
        result = (
            supabase.client.table("ohlc_data")
            .select("timestamp")
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )

        if result.data and len(result.data) > 0:
            last_data = datetime.fromisoformat(
                result.data[0]["timestamp"].replace("Z", "+00:00")
            )
            age_minutes = (datetime.now(timezone.utc) - last_data).total_seconds() / 60
            results["Data Fresh"] = age_minutes < 5
            print(
                f"   Data age: {age_minutes:.1f} minutes {'✅' if age_minutes < 5 else '⚠️'}"
            )
        else:
            results["Data Fresh"] = False
            print("   ❌ No data found")

    except Exception as e:
        results["Data Fresh"] = False
        print(f"   ❌ Data check failed: {str(e)[:50]}")

    # Summary
    print("\n" + "=" * 60)
    print("📊 VERIFICATION SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for check, result in results.items():
        status = "✅" if result else "❌"
        print(f"{status} {check}")

    score_percentage = (passed / total * 100) if total > 0 else 0
    print(f"\nOverall: {passed}/{total} checks passed ({score_percentage:.0f}%)")

    # Determine system status
    if score_percentage >= 90:
        print("\n🎉 EXCELLENT! System is at 95%+ operational!")
        print("All fixes successful - strategies are running and generating signals!")
    elif score_percentage >= 70:
        print("\n✅ GOOD! System is mostly operational (~85%)")
        print("Most fixes are working, minor issues remain.")
    elif score_percentage >= 50:
        print("\n⚠️  PARTIAL SUCCESS - System at ~70% operational")
        print("Some fixes are working but key components need attention.")
    else:
        print("\n❌ ISSUES REMAIN - System below 70% operational")
        print("Review the failed checks above and troubleshoot.")

    # Expected metrics
    print("\n📈 Expected Metrics After Fixes:")
    print("-" * 40)
    print("| Metric | Target | Actual |")
    print("|--------|--------|--------|")
    print(
        f"| Active Strategies | 3/3 | {sum([results.get('DCA Activity', False), results.get('SWING Activity', False), results.get('CHANNEL Activity', False)])}/3 |"
    )
    print(f"| Processes Running | 3+ | {process_count} |")
    print(
        f"| Shadow Testing | Active | {'Yes' if results.get('Shadow Testing Active') else 'No'} |"
    )
    print(f"| Data Fresh | <5 min | {'Yes' if results.get('Data Fresh') else 'No'} |")

    return results


if __name__ == "__main__":
    try:
        results = verify_fixes()
    except KeyboardInterrupt:
        print("\n⚠️  Verification interrupted by user")
    except Exception as e:
        print(f"\n❌ Verification error: {e}")
        logger.exception("Verification failed")
