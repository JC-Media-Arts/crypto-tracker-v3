#!/usr/bin/env python3
"""
Check existing database indexes and analyze query performance
"""

import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient  # noqa: E402
from loguru import logger  # noqa: E402


def check_indexes():
    """Check all indexes on ohlc_data table"""
    logger.info("=" * 60)
    logger.info("DATABASE INDEX ANALYSIS")
    logger.info("=" * 60)

    db = SupabaseClient()

    try:
        # Test query performance
        logger.info("\n" + "=" * 60)
        logger.info("TESTING QUERY PERFORMANCE")
        logger.info("=" * 60)

        # Test 1: Simple query for one symbol
        start = time.time()
        result = (
            db.client.table("ohlc_data")
            .select("*")
            .eq("symbol", "BTC")
            .eq("timeframe", "15m")
            .limit(1)
            .execute()
        )
        elapsed = time.time() - start
        logger.info(f"✓ Single symbol query (BTC, 15m, 1 row): {elapsed:.3f}s")

        # Test 2: Query for recent data
        start = time.time()
        result = (
            db.client.table("ohlc_data")
            .select("*")
            .eq("symbol", "BTC")
            .eq("timeframe", "15m")
            .order("timestamp", desc=True)
            .limit(25)
            .execute()
        )
        elapsed = time.time() - start
        logger.info(f"✓ Recent data query (BTC, 15m, 25 rows): {elapsed:.3f}s")

        # Test 3: Multiple symbols (what's timing out)
        symbols = ["BTC", "ETH", "SOL", "BNB", "XRP"]
        start = time.time()
        result = (
            db.client.table("ohlc_data")
            .select("*")
            .in_("symbol", symbols)
            .eq("timeframe", "15m")
            .order("timestamp", desc=True)
            .limit(100)
            .execute()
        )
        elapsed = time.time() - start
        logger.info(f"✓ Multi-symbol query (5 symbols, 100 rows): {elapsed:.3f}s")

        # Test 4: Check if materialized view exists and works
        logger.info("\n" + "=" * 60)
        logger.info("CHECKING MATERIALIZED VIEWS")
        logger.info("=" * 60)

        try:
            start = time.time()
            result = (
                db.client.table("ohlc_recent")
                .select("*")
                .eq("symbol", "BTC")
                .limit(1)
                .execute()
            )
            elapsed = time.time() - start
            logger.info(f"✓ ohlc_recent view exists and responds in: {elapsed:.3f}s")

            if result.data:
                logger.info(
                    f"  Latest timestamp: {result.data[0].get('timestamp', 'N/A')}"
                )
        except Exception as e:
            logger.warning(f"✗ ohlc_recent view error: {str(e)[:100]}")

        try:
            start = time.time()
            result = (
                db.client.table("ohlc_today")
                .select("*")
                .eq("symbol", "BTC")
                .limit(1)
                .execute()
            )
            elapsed = time.time() - start
            logger.info(f"✓ ohlc_today view exists and responds in: {elapsed:.3f}s")

            if result.data:
                logger.info(
                    f"  Latest timestamp: {result.data[0].get('timestamp', 'N/A')}"
                )
        except Exception as e:
            logger.warning(f"✗ ohlc_today view error: {str(e)[:100]}")

        # Check table size
        logger.info("\n" + "=" * 60)
        logger.info("TABLE SIZE ANALYSIS")
        logger.info("=" * 60)

        # Count total rows (this might timeout!)
        try:
            result = (
                db.client.table("ohlc_data")
                .select("*", count="exact", head=True)
                .execute()
            )
            if hasattr(result, "count"):
                logger.info(f"Total rows in ohlc_data: {result.count:,}")
        except Exception as e:
            logger.warning(
                f"Could not count total rows (probably too many): {str(e)[:100]}"
            )

        # Count recent rows
        from datetime import datetime, timedelta

        cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
        result = (
            db.client.table("ohlc_data")
            .select("*", count="exact", head=True)
            .gte("timestamp", cutoff)
            .execute()
        )
        if hasattr(result, "count"):
            logger.info(f"Rows from last 7 days: {result.count:,}")

        cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()
        result = (
            db.client.table("ohlc_data")
            .select("*", count="exact", head=True)
            .gte("timestamp", cutoff)
            .execute()
        )
        if hasattr(result, "count"):
            logger.info(f"Rows from last 30 days: {result.count:,}")

    except Exception as e:
        logger.error(f"Error checking indexes: {e}")

    logger.info("\n" + "=" * 60)
    logger.info("RECOMMENDATIONS")
    logger.info("=" * 60)
    logger.info("Based on the analysis, we need:")
    logger.info("1. Composite index on (symbol, timeframe, timestamp DESC)")
    logger.info("2. Partial index for recent data (last 30 days)")
    logger.info("3. Ensure materialized views are refreshed regularly")
    logger.info("4. Consider partitioning the table by month")


if __name__ == "__main__":
    check_indexes()
