#!/usr/bin/env python3
"""
Verify Data Cleanup Cron deployment on Railway.
This script tests the configuration without actually deleting data.
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))


def verify_environment():
    """Verify all required environment variables are set."""
    print("🔍 Checking Environment Variables...")
    print("-" * 50)

    required_vars = {
        "SUPABASE_URL": os.getenv("SUPABASE_URL"),
        "SUPABASE_KEY": os.getenv("SUPABASE_KEY"),
        "SLACK_WEBHOOK_URL": os.getenv("SLACK_WEBHOOK_URL"),
        "SLACK_WEBHOOK_ALERTS": os.getenv("SLACK_WEBHOOK_ALERTS"),
        "ENVIRONMENT": os.getenv("ENVIRONMENT", "development"),
    }

    all_set = True
    for var_name, var_value in required_vars.items():
        if var_value:
            # Mask sensitive values
            if "KEY" in var_name or "WEBHOOK" in var_name:
                display_value = f"{var_value[:8]}...{var_value[-4:]}" if len(var_value) > 12 else "***"
            else:
                display_value = var_value
            print(f"✅ {var_name}: {display_value}")
        else:
            print(f"❌ {var_name}: NOT SET")
            all_set = False

    return all_set


def verify_database_connection():
    """Test Supabase connection."""
    print("\n🔍 Testing Database Connection...")
    print("-" * 50)

    try:
        from src.data.supabase_client import SupabaseClient

        client = SupabaseClient()

        # Test query - count rows in ohlc_data
        result = client.client.table("ohlc_data").select("*", count="exact").limit(1).execute()

        print(f"✅ Database connected successfully")
        print(f"   Total rows in ohlc_data: {result.count:,}")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def verify_slack_connection():
    """Test Slack webhook."""
    print("\n🔍 Testing Slack Connection...")
    print("-" * 50)

    try:
        from src.notifications.slack_notifier import SlackNotifier

        slack = SlackNotifier()

        # Send test message
        success = slack.send_message(
            "🧪 Data Cleanup Cron Test",
            f"Testing Railway deployment at {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            webhook_type="alerts",
        )

        if success:
            print(f"✅ Slack message sent to #system-alerts")
        else:
            print(f"⚠️  Slack message might have failed (check channel)")
        return success
    except Exception as e:
        print(f"❌ Slack connection failed: {e}")
        return False


def check_data_to_cleanup():
    """Check how much data would be cleaned up."""
    print("\n📊 Checking Data to Clean...")
    print("-" * 50)

    try:
        from src.data.supabase_client import SupabaseClient

        client = SupabaseClient()

        # Calculate cutoff dates
        cutoffs = {
            "1-minute (>30 days)": (
                ["1m", "1min", "1"],
                datetime.now() - timedelta(days=30),
            ),
            "15-minute (>1 year)": (
                ["15m", "15min"],
                datetime.now() - timedelta(days=365),
            ),
            "1-hour (>2 years)": (
                ["1h", "1hr", "60m", "60min"],
                datetime.now() - timedelta(days=730),
            ),
        }

        total_to_delete = 0
        for description, (timeframes, cutoff) in cutoffs.items():
            try:
                count = 0
                for tf in timeframes:
                    result = (
                        client.client.table("ohlc_data")
                        .select("*", count="exact")
                        .eq("timeframe", tf)
                        .lt("timestamp", cutoff.isoformat())
                        .limit(0)
                        .execute()
                    )
                    count += result.count or 0

                if count > 0:
                    print(f"  • {description}: {count:,} rows to delete")
                    total_to_delete += count
                else:
                    print(f"  • {description}: No data to delete")
            except Exception as e:
                print(f"  • {description}: Error checking ({str(e)[:50]})")

        print(f"\n📈 Total rows to be cleaned: {total_to_delete:,}")

        # Estimate cleanup time (rough estimate: 10k rows/minute)
        est_minutes = total_to_delete / 10000
        if est_minutes < 1:
            print(f"⏱️  Estimated cleanup time: <1 minute")
        else:
            print(f"⏱️  Estimated cleanup time: ~{est_minutes:.1f} minutes")

        return True
    except Exception as e:
        print(f"❌ Failed to check data: {e}")
        return False


def verify_cron_schedule():
    """Display cron schedule information."""
    print("\n⏰ Cron Schedule Information...")
    print("-" * 50)

    cron_schedule = "0 10 * * *"
    print(f"📅 Schedule: {cron_schedule}")
    print(f"   Runs at: 10:00 AM UTC / 3:00 AM PST / 2:00 AM PDT")
    print(f"   Next run: Tomorrow at the scheduled time")
    print(f"   Frequency: Daily")

    # Calculate next run time
    now = datetime.utcnow()
    next_run = now.replace(hour=10, minute=0, second=0, microsecond=0)
    if now.hour >= 10:
        next_run = next_run + timedelta(days=1)

    hours_until = (next_run - now).total_seconds() / 3600
    print(f"   Time until next run: {hours_until:.1f} hours")

    return True


def main():
    """Run all verification checks."""
    print("=" * 50)
    print("🚀 DATA CLEANUP CRON VERIFICATION")
    print("=" * 50)

    checks = [
        ("Environment", verify_environment),
        ("Database", verify_database_connection),
        ("Slack", verify_slack_connection),
        ("Data Analysis", check_data_to_cleanup),
        ("Cron Schedule", verify_cron_schedule),
    ]

    results = []
    for name, check_func in checks:
        try:
            success = check_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ {name} check failed with error: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 50)
    print("📋 VERIFICATION SUMMARY")
    print("=" * 50)

    all_passed = True
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")
        if not success:
            all_passed = False

    if all_passed:
        print("\n🎉 All checks passed! Data Cleanup Cron is ready.")
        print("💡 The service will run automatically at 3 AM PST daily.")
        print("💡 To test immediately, you can:")
        print("   1. Manually trigger in Railway dashboard")
        print("   2. Run: python scripts/daily_data_cleanup.py --dry-run")
    else:
        print("\n⚠️  Some checks failed. Please review the configuration.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
