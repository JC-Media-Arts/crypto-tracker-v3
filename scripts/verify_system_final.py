#!/usr/bin/env python3
"""
Final system verification to confirm everything is working
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient


def verify_system():
    """Comprehensive final system check"""
    print("=" * 50)
    print("🔍 FINAL SYSTEM VERIFICATION")
    print("=" * 50)

    supabase = SupabaseClient()
    all_good = True

    # Check recent scans for each strategy
    print("\n📊 Strategy Activity (last 10 minutes):")
    print("-" * 40)

    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()

    for strategy in ["DCA", "SWING", "CHANNEL"]:
        try:
            result = (
                supabase.client.table("scan_history")
                .select("*", count="exact")
                .eq("strategy_name", strategy)
                .gte("timestamp", cutoff)
                .execute()
            )

            count = result.count if result else 0
            status = "✅" if count > 0 else "❌"
            print(f"{status} {strategy}: {count} scans")

            if count == 0:
                all_good = False

        except Exception as e:
            print(f"❌ {strategy}: Error checking - {str(e)[:50]}")
            all_good = False

    # Check shadow testing
    print("\n🔬 Shadow Testing Activity:")
    print("-" * 40)

    try:
        # Total shadow scans
        result = supabase.client.table("shadow_testing_scans").select("*", count="exact").execute()

        total_shadow = result.count if result else 0

        # Recent shadow scans
        result = (
            supabase.client.table("shadow_testing_scans").select("*", count="exact").gte("scan_time", cutoff).execute()
        )

        recent_shadow = result.count if result else 0

        print(f"✅ Total scans: {total_shadow}")
        print(f"✅ Recent scans (10 min): {recent_shadow}")

    except Exception as e:
        print(f"❌ Error checking shadow testing: {str(e)[:50]}")

    # Check data freshness
    print("\n📡 Data Pipeline:")
    print("-" * 40)

    try:
        result = supabase.client.table("ohlc_data").select("timestamp").order("timestamp", desc=True).limit(1).execute()

        if result.data and len(result.data) > 0:
            last_data = datetime.fromisoformat(result.data[0]["timestamp"].replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - last_data).total_seconds() / 60

            if age < 5:
                print(f"✅ Data freshness: {age:.1f} minutes")
            else:
                print(f"⚠️  Data freshness: {age:.1f} minutes (>5 min)")
                all_good = False
        else:
            print("❌ No data found")
            all_good = False

    except Exception as e:
        print(f"❌ Error checking data: {str(e)[:50]}")
        all_good = False

    # Check ML features
    print("\n🤖 ML System:")
    print("-" * 40)

    try:
        result = (
            supabase.client.table("ml_features").select("timestamp").order("timestamp", desc=True).limit(1).execute()
        )

        if result.data and len(result.data) > 0:
            last_feature = datetime.fromisoformat(result.data[0]["timestamp"].replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - last_feature).total_seconds() / 60

            if age < 30:
                print(f"✅ Feature calculation: {age:.1f} minutes ago")
            else:
                print(f"⚠️  Feature calculation: {age:.1f} minutes ago (stale)")

    except Exception as e:
        print(f"⚠️  ML features check: {str(e)[:50]}")

    # Summary
    print("\n" + "=" * 50)

    if all_good:
        print("🎉 SYSTEM IS FULLY OPERATIONAL!")
        print("All strategies are scanning and recording data.")
        print("\nNext steps:")
        print("1. Monitor for 24 hours")
        print("2. Check for generated trades")
        print("3. Review shadow testing results")
    else:
        print("⚠️  SYSTEM PARTIALLY OPERATIONAL")
        print("\nRecommended actions:")
        print("1. Use PM2 for auto-restart: pm2 start ecosystem.config.js")
        print("2. OR setup cron: crontab -e")
        print("   */5 * * * * /Users/justincoit/crypto-tracker-v3/scripts/run_strategies_cron.sh")
        print("3. Monitor logs: tail -f logs/strategy_cron.log")

    print("\n📈 Expected in 24 hours:")
    print("- 3,000+ scans per hour")
    print("- 5-15 trades generated")
    print("- 10,000+ shadow tests")
    print("=" * 50)


if __name__ == "__main__":
    verify_system()
