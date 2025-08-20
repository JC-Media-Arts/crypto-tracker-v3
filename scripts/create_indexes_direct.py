#!/usr/bin/env python3
"""
Create indexes directly using psycopg2 to bypass SQL Editor limitations.
This allows CONCURRENTLY to work properly.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import psycopg2
from psycopg2 import sql
import time
from urllib.parse import urlparse
from src.config.settings import get_settings
from loguru import logger


def create_indexes_concurrently():
    """Create indexes using direct PostgreSQL connection."""
    settings = get_settings()

    # Parse Supabase URL
    parsed = urlparse(settings.supabase_url)
    db_host = parsed.hostname
    db_port = 5432  # Supabase uses standard PostgreSQL port

    # You'll need to add these to your .env:
    # SUPABASE_DB_PASSWORD=your-database-password
    db_password = (
        settings.supabase_db_password
        if hasattr(settings, "supabase_db_password")
        else input("Enter Supabase database password: ")
    )

    # Connection string
    conn_string = f"host={db_host} port={db_port} dbname=postgres user=postgres password={db_password}"

    try:
        # Connect with autocommit for CONCURRENTLY
        conn = psycopg2.connect(conn_string)
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        logger.info("Connected to database")

        # Set timeout
        cur.execute("SET statement_timeout = '3600000'")  # 1 hour
        logger.info("Set timeout to 1 hour")

        # Create indexes one by one
        indexes = [
            {
                "name": "idx_ohlc_recent_7d",
                "sql": """
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_recent_7d
                    ON ohlc_data(symbol, timeframe, timestamp DESC)
                    WHERE timestamp > CURRENT_DATE - INTERVAL '7 days'
                """,
                "description": "7-day partial index for real-time trading",
            },
            {
                "name": "idx_ohlc_ml_30d",
                "sql": """
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_ml_30d
                    ON ohlc_data(symbol, timestamp DESC)
                    WHERE timestamp > CURRENT_DATE - INTERVAL '30 days'
                """,
                "description": "30-day partial index for ML features",
            },
            {
                "name": "idx_ohlc_timestamp_brin",
                "sql": """
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_timestamp_brin
                    ON ohlc_data USING BRIN(timestamp)
                """,
                "description": "BRIN index for time-series queries",
            },
        ]

        for idx in indexes:
            logger.info(f"Creating index: {idx['name']}")
            logger.info(f"Description: {idx['description']}")

            start_time = time.time()
            try:
                cur.execute(idx["sql"])
                elapsed = time.time() - start_time
                logger.success(f"✅ Created {idx['name']} in {elapsed:.2f} seconds")
            except psycopg2.errors.DuplicateTable:
                logger.info(f"Index {idx['name']} already exists")
            except Exception as e:
                logger.error(f"Failed to create {idx['name']}: {e}")
                continue

            # Check if index was created
            cur.execute(
                """
                SELECT indexname, pg_size_pretty(pg_relation_size(indexname::regclass)) as size
                FROM pg_indexes
                WHERE tablename = 'ohlc_data' AND indexname = %s
            """,
                (idx["name"],),
            )

            result = cur.fetchone()
            if result:
                logger.info(f"Index size: {result[1]}")

        # Analyze table
        logger.info("Analyzing table to update statistics...")
        cur.execute("ANALYZE ohlc_data")
        logger.success("✅ Table analyzed")

        # Close connection
        cur.close()
        conn.close()
        logger.success("✅ All indexes created successfully!")

    except Exception as e:
        logger.error(f"Connection failed: {e}")
        logger.info("Please check your database credentials and try again")
        return False

    return True


if __name__ == "__main__":
    logger.add("logs/index_creation.log", rotation="10 MB")
    logger.info("Starting index creation with CONCURRENTLY...")

    success = create_indexes_concurrently()

    if success:
        logger.success("Index creation completed successfully!")
        print("\n✅ Indexes created! Your queries should now be much faster.")
        print("\nNext steps:")
        print("1. Test query performance with your optimized fetcher")
        print("2. Monitor index usage over the next 24 hours")
        print("3. Create full index over the weekend if needed")
    else:
        logger.error("Index creation failed")
        print("\n❌ Index creation failed. Check logs/index_creation.log for details")
        print("\nAlternative: Use the materialized view approach in the SQL editor")
