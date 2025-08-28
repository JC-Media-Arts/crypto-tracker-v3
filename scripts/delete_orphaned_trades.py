#!/usr/bin/env python3
"""
Delete orphaned SELL trades without trade_group_id.
These are incomplete trades that would mess up ML training.
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from loguru import logger


def delete_orphaned_trades(dry_run=True):
    """Delete orphaned trades without trade_group_id"""

    logger.info("Starting orphaned trades deletion...")

    db = SupabaseClient()

    # Get all trades without trade_group_id
    orphaned_trades = []
    batch_limit = 1000
    batch_offset = 0

    logger.info("Finding orphaned trades without trade_group_id...")

    while True:
        batch = (
            db.client.table("paper_trades")
            .select("*")
            .is_("trade_group_id", "null")
            .range(batch_offset, batch_offset + batch_limit - 1)
            .execute()
        )

        if not batch.data:
            break

        orphaned_trades.extend(batch.data)

        if len(batch.data) < batch_limit:
            break
        batch_offset += batch_limit

    logger.info(f"Found {len(orphaned_trades)} trades without trade_group_id")

    if not orphaned_trades:
        logger.info("No orphaned trades to delete!")
        return

    # Analyze what we're about to delete
    from collections import Counter

    sides = Counter([t.get("side", "Unknown") for t in orphaned_trades])
    strategies = Counter([t.get("strategy_name", "Unknown") for t in orphaned_trades])

    logger.info("\n📋 Trades to delete:")
    logger.info(f"  Total: {len(orphaned_trades)} trades")

    logger.info("\n  By side:")
    for side, count in sides.items():
        logger.info(f"    {side}: {count} trades")

    logger.info("\n  By strategy:")
    for strategy, count in strategies.items():
        logger.info(f"    {strategy}: {count} trades")

    # Check date range
    dates = []
    for trade in orphaned_trades:
        if trade.get("created_at"):
            try:
                dt = datetime.fromisoformat(trade["created_at"].replace("Z", "+00:00"))
                dates.append(dt)
            except:
                pass

    if dates:
        oldest = min(dates)
        newest = max(dates)
        logger.info(
            f"\n  Date range: {oldest.strftime('%Y-%m-%d')} to {newest.strftime('%Y-%m-%d')}"
        )

    # Show why these are problematic
    no_entry = len([t for t in orphaned_trades if not t.get("entry_price")])
    no_exit = len([t for t in orphaned_trades if not t.get("exit_price")])

    logger.info(f"\n  Missing entry_price: {no_entry} trades")
    logger.info(f"  Missing exit_price: {no_exit} trades")

    if dry_run:
        logger.info("\n🔍 DRY RUN - No changes will be made")

        # Show sample trades
        logger.info("\nSample trades that would be deleted (first 5):")
        for i, trade in enumerate(orphaned_trades[:5], 1):
            logger.info(
                f"  {i}. {trade['symbol']} | {trade.get('side')} | P&L: {trade.get('pnl')} | {trade.get('exit_reason')}"
            )

        logger.info("\n💡 Run with --execute to actually delete these orphaned trades")
    else:
        logger.info("\n⚡ EXECUTING DELETION...")

        # Delete in batches using IDs
        deleted_count = 0
        failed_count = 0

        # Get all IDs
        trade_ids = [trade["id"] for trade in orphaned_trades if trade.get("id")]

        logger.info(f"Deleting {len(trade_ids)} trades...")

        # Delete in chunks of 100
        chunk_size = 100
        for i in range(0, len(trade_ids), chunk_size):
            chunk = trade_ids[i : i + chunk_size]

            try:
                result = (
                    db.client.table("paper_trades").delete().in_("id", chunk).execute()
                )

                deleted_count += len(chunk)

                if (i + chunk_size) % 200 == 0:
                    logger.info(f"  Deleted {deleted_count}/{len(trade_ids)} trades...")

            except Exception as e:
                logger.error(f"Failed to delete chunk: {e}")
                failed_count += len(chunk)

        logger.info(f"\n✅ Successfully deleted {deleted_count} orphaned trades")
        if failed_count > 0:
            logger.warning(f"⚠️ Failed to delete {failed_count} trades")

        logger.info(
            "\n🧹 Database cleaned! These incomplete trades won't affect ML training anymore."
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Delete orphaned trades without trade_group_id"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually execute deletions (not dry run)",
    )

    args = parser.parse_args()

    delete_orphaned_trades(dry_run=not args.execute)
