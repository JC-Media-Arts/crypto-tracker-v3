#!/usr/bin/env python3
"""
Verify that the Data Scheduler is updating OHLC data correctly
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from dateutil import tz

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from loguru import logger


def check_recent_updates():
    """Check for recent OHLC updates from the scheduler"""
    supabase = SupabaseClient()

    # Check data from last 30 minutes
    since = (datetime.now(tz.UTC) - timedelta(minutes=30)).isoformat()

    results = {}

    for timeframe in ["1m", "15m", "1h", "1d"]:
        try:
            # Get count of recent records
            response = (
                supabase.client.table("ohlc_data")
                .select("symbol", count="exact")
                .eq("timeframe", timeframe)
                .gte("timestamp", since)
                .execute()
            )

            count = response.count if hasattr(response, "count") else 0

            # Get sample of symbols updated
            response = (
                supabase.client.table("ohlc_data")
                .select("symbol", "timestamp")
                .eq("timeframe", timeframe)
                .gte("timestamp", since)
                .order("timestamp", desc=True)
                .limit(5)
                .execute()
            )

            symbols = list(set([r["symbol"] for r in response.data])) if response.data else []

            results[timeframe] = {
                "count": count,
                "symbols_sample": symbols[:5],
                "latest": response.data[0]["timestamp"] if response.data else None,
            }

        except Exception as e:
            logger.error(f"Error checking {timeframe}: {e}")
            results[timeframe] = {"error": str(e)}

    return results


def check_data_freshness():
    """Check how fresh the data is for key symbols"""
    supabase = SupabaseClient()
    key_symbols = ["BTC", "ETH", "SOL"]

    freshness = {}
    now = datetime.now(tz.UTC)

    for symbol in key_symbols:
        freshness[symbol] = {}

        for timeframe in ["1m", "15m", "1h", "1d"]:
            try:
                response = (
                    supabase.client.table("ohlc_data")
                    .select("timestamp")
                    .eq("symbol", symbol)
                    .eq("timeframe", timeframe)
                    .order("timestamp", desc=True)
                    .limit(1)
                    .execute()
                )

                if response.data:
                    latest = datetime.fromisoformat(response.data[0]["timestamp"].replace("Z", "+00:00"))
                    age_minutes = (now - latest).total_seconds() / 60
                    freshness[symbol][timeframe] = {
                        "latest": latest.isoformat(),
                        "age_minutes": round(age_minutes, 1),
                    }
                else:
                    freshness[symbol][timeframe] = {"latest": None, "age_minutes": None}

            except Exception as e:
                freshness[symbol][timeframe] = {"error": str(e)}

    return freshness


def main():
    logger.info("=" * 60)
    logger.info("SCHEDULER VERIFICATION REPORT")
    logger.info("=" * 60)

    # Check recent updates
    logger.info("\n📊 Recent Updates (Last 30 minutes):")
    updates = check_recent_updates()

    for timeframe, data in updates.items():
        if "error" not in data:
            logger.info(f"\n{timeframe}:")
            logger.info(f"  Records added: {data['count']}")
            logger.info(f"  Symbols updated: {', '.join(data['symbols_sample']) if data['symbols_sample'] else 'None'}")
            if data["latest"]:
                logger.info(f"  Latest timestamp: {data['latest']}")
        else:
            logger.error(f"{timeframe}: {data['error']}")

    # Check data freshness
    logger.info("\n⏰ Data Freshness Check:")
    freshness = check_data_freshness()

    for symbol, timeframes in freshness.items():
        logger.info(f"\n{symbol}:")
        for tf, data in timeframes.items():
            if "error" not in data and data["age_minutes"] is not None:
                status = (
                    "✅"
                    if (
                        (tf == "1m" and data["age_minutes"] < 10)
                        or (tf == "15m" and data["age_minutes"] < 20)
                        or (tf == "1h" and data["age_minutes"] < 65)
                        or (tf == "1d" and data["age_minutes"] < 1440)
                    )
                    else "⚠️"
                )
                logger.info(f"  {tf}: {status} {data['age_minutes']} minutes old")
            else:
                logger.warning(f"  {tf}: No data or error")

    # Summary
    logger.info("\n" + "=" * 60)

    # Check if scheduler is working
    if updates.get("1m", {}).get("count", 0) > 0 or updates.get("15m", {}).get("count", 0) > 0:
        logger.success("✅ SCHEDULER IS WORKING! Data is being updated.")
    else:
        logger.warning("⚠️ No recent updates found. Scheduler may need more time or there may be an issue.")

    logger.info("=" * 60)


if __name__ == "__main__":
    main()
