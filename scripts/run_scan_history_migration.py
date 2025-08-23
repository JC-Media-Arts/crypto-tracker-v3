#!/usr/bin/env python3
"""
Run the scan_history migration directly using Supabase client
"""

import sys
import os

sys.path.append(".")

from src.data.supabase_client import SupabaseClient
from loguru import logger


def run_migration():
    """Execute the scan_history migration"""

    # Read the migration file
    migration_file = "migrations/004_create_scan_history.sql"
    with open(migration_file, "r") as f:
        sql = f.read()

    # Split into individual statements (Supabase can be picky)
    statements = [
        s.strip()
        for s in sql.split(";")
        if s.strip() and not s.strip().startswith("--")
    ]

    logger.info(f"Running {len(statements)} SQL statements from {migration_file}")

    # Initialize Supabase client
    client = SupabaseClient()

    # Execute each statement
    for i, statement in enumerate(statements, 1):
        if (
            "CREATE TABLE" in statement
            or "CREATE INDEX" in statement
            or "CREATE OR REPLACE VIEW" in statement
        ):
            try:
                # Use RPC to execute raw SQL
                result = client.client.rpc(
                    "exec_sql", {"query": statement + ";"}
                ).execute()
                logger.success(f"Statement {i}/{len(statements)} executed successfully")
            except Exception as e:
                # Try alternative approach - direct execution
                logger.warning(f"RPC failed, trying direct approach for statement {i}")
                logger.info(
                    f"Please run this statement manually in Supabase SQL Editor:"
                )
                logger.info(
                    statement[:200] + "..." if len(statement) > 200 else statement
                )

    # Verify table creation
    try:
        result = client.client.table("scan_history").select("*").limit(1).execute()
        logger.success("✅ scan_history table created successfully!")
    except Exception as e:
        logger.error(f"Table verification failed: {e}")
        logger.info("\n📋 Please run the following SQL in your Supabase SQL Editor:\n")
        print(sql)


if __name__ == "__main__":
    run_migration()
