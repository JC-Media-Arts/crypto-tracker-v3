#!/usr/bin/env python3
"""Quick check of what data is available"""

import os
from datetime import datetime, timedelta
from src.data.supabase_client import SupabaseClient
from loguru import logger


def check_data():
    """Check what data is available in our tables"""

    db = SupabaseClient()

    # Check different tables
    tables = ["ohlc_data", "ohlc_today", "ohlc_recent"]

    for table in tables:
        try:
            # Get count and recent data
            result = (
                db.client.table(table)
                .select("symbol, timeframe, timestamp")
                .limit(10)
                .order("timestamp", desc=True)
                .execute()
            )

            if result.data:
                logger.info(f"✅ Table '{table}' has data:")
                logger.info(
                    f"   Latest: {result.data[0]['timestamp']} - {result.data[0]['symbol']}"
                )

                # Get count for BTC
                btc_result = (
                    db.client.table(table)
                    .select("count", count="exact")
                    .eq("symbol", "BTC")
                    .eq("timeframe", "15m")
                    .gte(
                        "timestamp",
                        (datetime.utcnow() - timedelta(hours=4)).isoformat(),
                    )
                    .execute()
                )
                logger.info(f"   BTC 15m records (last 4h): {btc_result.count}")
            else:
                logger.warning(f"❌ Table '{table}' appears empty")

        except Exception as e:
            logger.error(f"❌ Error checking table '{table}': {e}")

    # Check the main ohlc_data table for recent data
    logger.info("\nChecking main ohlc_data for recent entries:")
    try:
        recent = (
            db.client.table("ohlc_data")
            .select("symbol, timeframe, timestamp")
            .gte("timestamp", (datetime.utcnow() - timedelta(hours=4)).isoformat())
            .eq("timeframe", "15m")
            .order("timestamp", desc=True)
            .limit(20)
            .execute()
        )

        if recent.data:
            symbols = set(r["symbol"] for r in recent.data)
            logger.info(f"✅ Found {len(recent.data)} records for symbols: {symbols}")
            logger.info(f"   Latest: {recent.data[0]['timestamp']}")
        else:
            logger.warning("❌ No recent data in last 4 hours")

    except Exception as e:
        logger.error(f"Error checking recent data: {e}")


if __name__ == "__main__":
    check_data()
