#!/usr/bin/env python3
"""Verify cache tables exist in Supabase"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient  # noqa: E402
from loguru import logger  # noqa: E402


def verify_tables():
    """Check if cache tables exist"""
    db = SupabaseClient()

    logger.info("=" * 60)
    logger.info("VERIFYING CACHE TABLES")
    logger.info("=" * 60)

    # Test 1: Try to query strategy_status_cache
    try:
        result = db.client.table("strategy_status_cache").select("*").limit(1).execute()
        logger.success("✅ strategy_status_cache table EXISTS")
        logger.info(f"   Rows in table: {len(result.data) if result.data else 0}")
    except Exception as e:
        logger.error(f"❌ strategy_status_cache NOT FOUND: {str(e)[:100]}")

    # Test 2: Try to query market_summary_cache
    try:
        result = db.client.table("market_summary_cache").select("*").limit(1).execute()
        logger.success("✅ market_summary_cache table EXISTS")
        logger.info(f"   Rows in table: {len(result.data) if result.data else 0}")
    except Exception as e:
        logger.error(f"❌ market_summary_cache NOT FOUND: {str(e)[:100]}")

    logger.info("\n" + "=" * 60)
    logger.info("TROUBLESHOOTING")
    logger.info("=" * 60)
    logger.info("If tables are missing:")
    logger.info("1. Go to Supabase SQL Editor")
    logger.info("2. Run: migrations/025_fix_dashboard_performance_final.sql")
    logger.info("3. Check for any error messages")
    logger.info("4. Verify in Table Editor that tables were created")


if __name__ == "__main__":
    verify_tables()
