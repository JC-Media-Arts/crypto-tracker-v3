#!/usr/bin/env python3
"""Final production readiness check."""

from datetime import datetime, timezone, timedelta
import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))


async def final_production_check():
    print("=" * 60)
    print("FINAL PRODUCTION READINESS CHECK")
    print("=" * 60)

    checks = {}

    # 1. Data freshness
    from src.data.supabase_client import SupabaseClient

    db = SupabaseClient()

    result = (
        db.client.table("ohlc_data")
        .select("timestamp")
        .eq("timeframe", "1m")
        .order("timestamp", desc=True)
        .limit(1)
        .execute()
    )

    if result.data:
        ts = result.data[0]["timestamp"]
        if "Z" in ts:
            timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        else:
            timestamp = datetime.fromisoformat(ts)
        age_minutes = (datetime.now(timezone.utc) - timestamp).total_seconds() / 60
        checks["Data freshness < 5 min"] = age_minutes < 5
        print(f"  Data age: {age_minutes:.1f} minutes")
    else:
        checks["Data freshness < 5 min"] = False

    # 2. ML features (with updated code)
    from src.ml.feature_calculator import FeatureCalculator

    calc = FeatureCalculator()
    features = await calc.calculate_features_for_symbol("BTC", lookback_hours=48)
    checks["ML features working"] = features is not None and not features.empty

    # 3. Strategy tables
    tables = ["strategy_dca_labels", "strategy_swing_labels", "strategy_channel_labels"]
    all_exist = True
    for table in tables:
        try:
            db.client.table(table).select("*").limit(1).execute()
        except:
            all_exist = False
    checks["Strategy tables exist"] = all_exist

    # 4. Environment variables
    import os
    from dotenv import load_dotenv

    load_dotenv()
    env_vars = ["POLYGON_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"]
    checks["All env vars set"] = all(os.getenv(v) for v in env_vars)

    # 5. Performance
    from src.data.hybrid_fetcher import HybridDataFetcher
    import time

    fetcher = HybridDataFetcher()
    start = time.time()
    await fetcher.get_latest_price("BTC", "1m")
    elapsed = time.time() - start
    checks["Performance < 0.5s"] = elapsed < 0.5
    print(f"  Query time: {elapsed:.3f}s")

    # 6. Data coverage
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    result = (
        db.client.table("ohlc_data")
        .select("symbol")
        .gte("timestamp", cutoff)
        .limit(10000)
        .execute()
    )

    if result.data:
        unique_symbols = set(r["symbol"] for r in result.data)
        checks["Symbol coverage > 80"] = len(unique_symbols) >= 80
        print(f"  Active symbols: {len(unique_symbols)}/90")
    else:
        checks["Symbol coverage > 80"] = False

    # Print results
    print("\nResults:")
    print("-" * 40)
    passed = sum(1 for v in checks.values() if v)
    total = len(checks)

    for name, result in checks.items():
        status = "✅" if result else "❌"
        print(f"{status} {name}")

    print(f"\nScore: {passed}/{total} ({passed/total*100:.0f}%)")

    if passed == total:
        print("\n🎉 SYSTEM IS PRODUCTION READY!")
        print("   All critical checks passed")
        print("   Performance is excellent")
        print("   Data pipeline is active")
    elif passed >= 5:
        print("\n⚠️  System is NEARLY ready")
        print("   Fix remaining issue(s) above")
    else:
        print("\n❌ System needs attention")
        print("   Review failed checks above")

    return passed, total


async def main():
    passed, total = await final_production_check()
    print(f"\n{'='*60}")
    print(f"ADVISOR ASSESSMENT: {passed}/{total} checks passed")

    if passed >= 5:
        print("✅ Your system is functional and can be used!")
        print("   The core infrastructure is solid")
        print("   Minor issues can be fixed while running")

    if passed == total:
        print("\n🚀 READY FOR PRODUCTION TRADING!")

    return 0 if passed >= 5 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
