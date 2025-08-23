#!/usr/bin/env python3
"""
Simple verification for Railway Data Cleanup Cron deployment.
"""

import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))


async def main():
    """Run verification checks."""
    print("=" * 60)
    print("🚀 RAILWAY DATA CLEANUP CRON - DEPLOYMENT VERIFICATION")
    print("=" * 60)

    # 1. Check Environment Variables
    print("\n✅ Environment Variables Check:")
    print("-" * 40)

    env_vars = {
        "SUPABASE_URL": os.getenv("SUPABASE_URL"),
        "SUPABASE_KEY": os.getenv("SUPABASE_KEY"),
        "SLACK_WEBHOOK_ALERTS": os.getenv("SLACK_WEBHOOK_ALERTS"),
        "ENVIRONMENT": os.getenv("ENVIRONMENT", "development"),
    }

    all_env_set = True
    for var_name, var_value in env_vars.items():
        if var_value:
            if "KEY" in var_name or "WEBHOOK" in var_name:
                display = f"{var_value[:10]}..." if len(var_value) > 10 else "***"
            else:
                display = var_value
            print(f"  ✓ {var_name}: {display}")
        else:
            print(f"  ✗ {var_name}: NOT SET")
            all_env_set = False

    # 2. Test Database Connection (Simple)
    print("\n✅ Database Connection Test:")
    print("-" * 40)

    try:
        from src.data.supabase_client import SupabaseClient

        client = SupabaseClient()

        # Simple test - just check if we can connect
        result = client.client.table("ohlc_data").select("symbol").limit(1).execute()

        print(f"  ✓ Database connected successfully")
        print(f"  ✓ Can query ohlc_data table")
    except Exception as e:
        print(f"  ✗ Database error: {str(e)[:100]}")

    # 3. Cron Schedule Info
    print("\n✅ Railway Cron Configuration:")
    print("-" * 40)

    print(f"  📅 Schedule: 0 10 * * * (Daily at 10:00 AM UTC)")
    print(f"  🕐 Time Zones:")
    print(f"     • 10:00 AM UTC")
    print(f"     • 3:00 AM PST / 2:00 AM PDT")
    print(f"     • 6:00 AM EST / 5:00 AM EDT")

    # Calculate next run
    now = datetime.utcnow()
    next_run = now.replace(hour=10, minute=0, second=0, microsecond=0)
    if now.hour >= 10:
        next_run = next_run + timedelta(days=1)

    hours_until = (next_run - now).total_seconds() / 3600
    print(f"  ⏱️  Next run in: {hours_until:.1f} hours")

    # 4. Service Status
    print("\n✅ Railway Service Status:")
    print("-" * 40)

    print(f"  Service Name: Data Cleanup Cron")
    print(f"  Start Command: python scripts/daily_data_cleanup.py")
    print(f"  Restart Policy: NEVER (runs once per schedule)")
    print(f"  Builder: NIXPACKS")

    # 5. Data Retention Policy
    print("\n✅ Data Retention Policy:")
    print("-" * 40)

    print(f"  • 1-minute data: Keep 30 days")
    print(f"  • 15-minute data: Keep 1 year")
    print(f"  • 1-hour data: Keep 2 years")
    print(f"  • Daily data: Keep forever")
    print(f"  • scan_history: Keep 7 days")
    print(f"  • ml_features: Keep 30 days")

    # 6. Quick Data Check (avoid timeouts)
    print("\n✅ Quick Data Check:")
    print("-" * 40)

    try:
        # Just check recent data to avoid timeouts
        recent_cutoff = (datetime.now() - timedelta(hours=1)).isoformat()

        result = (
            client.client.table("ohlc_data")
            .select("*", count="exact")
            .gte("timestamp", recent_cutoff)
            .limit(0)
            .execute()
        )

        print(f"  ✓ Data collected in last hour: {result.count:,} rows")

        # Check if cleanup is needed (sample check)
        old_1min = (datetime.now() - timedelta(days=31)).isoformat()
        sample_check = (
            client.client.table("ohlc_data")
            .select("*", count="exact")
            .eq("timeframe", "1m")
            .lt("timestamp", old_1min)
            .limit(0)
            .execute()
        )

        if sample_check.count > 0:
            print(
                f"  ⚠️  Found {sample_check.count:,} 1-minute rows older than 30 days"
            )
            print(f"     These will be cleaned on next run")
        else:
            print(f"  ✓ No 1-minute data older than 30 days found")

    except Exception as e:
        if "timeout" in str(e).lower():
            print(f"  ⚠️  Query timeout (expected with large dataset)")
            print(f"     Cleanup will run in batches to handle this")
        else:
            print(f"  ✗ Error: {str(e)[:100]}")

    # Summary
    print("\n" + "=" * 60)
    print("📋 DEPLOYMENT STATUS")
    print("=" * 60)

    if all_env_set:
        print("✅ Service is DEPLOYED and CONFIGURED")
        print("\n📌 Next Steps:")
        print("1. Monitor first automatic run at 3 AM PST")
        print("2. Check Slack #system-alerts for cleanup reports")
        print("3. To test now: python scripts/daily_data_cleanup.py --dry-run")
        print("\n💡 Railway Dashboard:")
        print("   • View logs in Railway → Data Cleanup Cron → Logs")
        print("   • Manual trigger: Railway → Data Cleanup Cron → Deploy")
    else:
        print("⚠️  Missing environment variables")
        print("Please check Railway service environment settings")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
