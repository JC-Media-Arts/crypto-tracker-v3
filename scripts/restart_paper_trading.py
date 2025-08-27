#!/usr/bin/env python3
"""
Script to diagnose and provide instructions for restarting paper trading on Railway
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.supabase_client import SupabaseClient  # noqa: E402


def check_last_activity():
    """Check when paper trading was last active"""
    db = SupabaseClient()

    # Check last scan
    last_scan = (
        db.client.table("scan_history")
        .select("timestamp")
        .order("timestamp", desc=True)
        .limit(1)
        .execute()
    )

    if last_scan.data:
        last_time = last_scan.data[0]["timestamp"]
        last_dt = datetime.fromisoformat(last_time.replace("Z", "+00:00"))
        time_diff = datetime.now(timezone.utc) - last_dt
        hours_ago = time_diff.total_seconds() / 3600

        print(f"Last scan: {last_time}")
        print(f"That was {hours_ago:.1f} hours ago")

        if hours_ago > 0.5:  # More than 30 minutes
            return False
        return True
    else:
        print("No scans found in database")
        return False


def provide_restart_instructions():
    """Provide instructions for restarting the service"""

    print("\n" + "=" * 60)
    print("PAPER TRADING SERVICE NEEDS RESTART")
    print("=" * 60)

    print("\n📋 RAILWAY RESTART INSTRUCTIONS:")
    print("-" * 40)

    print("\n1. Go to Railway Dashboard:")
    print("   https://railway.app/dashboard")

    print("\n2. Select your project (crypto-tracker-v3)")

    print("\n3. Find the 'Trading - Paper Engine' service")

    print("\n4. Click on the service to view details")

    print("\n5. Look for the '⟲ Restart' button (usually in top-right)")

    print("\n6. Click Restart and wait for it to redeploy")

    print("\n" + "-" * 40)
    print("ALTERNATIVE: Manual Restart via Railway CLI")
    print("-" * 40)

    print("\nIf you have Railway CLI installed:")
    print("$ railway restart")

    print("\n" + "-" * 40)
    print("CHECK THE LOGS")
    print("-" * 40)

    print("\nAfter restarting, check the logs for errors:")
    print("1. In Railway dashboard, click on the service")
    print("2. Go to 'Logs' tab")
    print("3. Look for any error messages, especially:")
    print("   - Database connection errors")
    print("   - API key issues")
    print("   - Import errors")
    print("   - Uncaught exceptions")

    print("\n" + "-" * 40)
    print("COMMON ISSUES AND FIXES")
    print("-" * 40)

    print("\n1. Database Connection Error:")
    print("   - Check SUPABASE_URL and SUPABASE_KEY environment variables")

    print("\n2. Import Error:")
    print("   - Check if all dependencies are in requirements.txt")

    print("\n3. API Rate Limit:")
    print("   - Check Polygon API usage")
    print("   - May need to reduce scan frequency")

    print("\n4. Memory Issues:")
    print("   - Service might be running out of memory")
    print("   - Check Railway resource usage")

    print("\n" + "=" * 60)
    print("AFTER RESTART")
    print("=" * 60)

    print("\nWait 2-3 minutes, then run this check again:")
    print("$ python3 scripts/check_paper_trading_status.py")

    print("\nIf still showing as stopped:")
    print("1. Check Railway logs for errors")
    print("2. Run locally to debug: python3 scripts/run_paper_trading_simple.py")


def main():
    print("Checking Paper Trading Service Status...")
    print("=" * 60)

    is_active = check_last_activity()

    if is_active:
        print("\n✅ Paper Trading appears to be running normally!")
        print("Dashboard should show it as active.")
    else:
        print("\n❌ Paper Trading is not active!")
        provide_restart_instructions()

        # Also create a quick test script
        print("\n" + "=" * 60)
        print("LOCAL TESTING")
        print("=" * 60)
        print("\nTo test the paper trading script locally:")
        print("$ python3 scripts/run_paper_trading_simple.py")
        print("\nThis will help identify if there are code issues.")


if __name__ == "__main__":
    main()
