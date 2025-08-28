#!/usr/bin/env python3
"""
Delete all manually closed trades from the database.
These trades have exit reasons indicating manual intervention or cleanup,
which would negatively impact ML training.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from loguru import logger


def delete_manual_trades(dry_run=True):
    """Delete all trades with manual/cleanup exit reasons"""

    logger.info("Starting manual trades deletion...")

    db = SupabaseClient()

    # Keywords that indicate manual closure
    manual_keywords = [
        "manual",
        "cleanup",
        "excess",
        "position_limit",
        "portfolio_cleanup",
    ]

    # First, find all SELL trades with manual exit reasons
    manual_sells = []
    batch_limit = 1000
    batch_offset = 0

    logger.info("Finding all manually closed trades...")

    while True:
        batch = (
            db.client.table("paper_trades")
            .select("trade_group_id, exit_reason, symbol, created_at")
            .eq("side", "SELL")
            .range(batch_offset, batch_offset + batch_limit - 1)
            .execute()
        )

        if not batch.data:
            break

        for trade in batch.data:
            exit_reason = trade.get("exit_reason", "")
            if exit_reason and any(
                keyword in exit_reason.lower() for keyword in manual_keywords
            ):
                manual_sells.append(trade)

        if len(batch.data) < batch_limit:
            break
        batch_offset += batch_limit

    logger.info(f"Found {len(manual_sells)} manually closed SELL trades")

    # Get unique trade group IDs
    trade_group_ids = list(set(trade["trade_group_id"] for trade in manual_sells))
    logger.info(f"Found {len(trade_group_ids)} unique trade groups to delete")

    # Count exit reasons
    from collections import Counter

    exit_reasons = Counter([t.get("exit_reason", "None") for t in manual_sells])

    logger.info("\n📋 Breakdown by exit reason:")
    for reason, count in exit_reasons.most_common():
        logger.info(f"  {reason}: {count} trades")

    if dry_run:
        logger.info("\n🔍 DRY RUN - No changes will be made")
        logger.info(
            f"Would delete all trades (BUY and SELL) for {len(trade_group_ids)} trade groups"
        )

        # Show sample of what would be deleted
        logger.info("\nSample trade groups that would be deleted (first 10):")
        for i, group_id in enumerate(trade_group_ids[:10], 1):
            # Find the corresponding trade info
            trade = next(
                (t for t in manual_sells if t["trade_group_id"] == group_id), None
            )
            if trade:
                logger.info(
                    f"  {i}. {trade['symbol']} - {group_id[:30]}... ({trade['exit_reason']})"
                )

        logger.info("\n💡 Run with --execute to actually delete these trades")
    else:
        logger.info("\n⚡ EXECUTING DELETION...")

        deleted_count = 0
        failed_count = 0

        # Delete all trades for each trade group
        for i, group_id in enumerate(trade_group_ids, 1):
            try:
                # Delete all trades with this trade_group_id (both BUY and SELL)
                result = (
                    db.client.table("paper_trades")
                    .delete()
                    .eq("trade_group_id", group_id)
                    .execute()
                )

                deleted_count += 1

                if i % 100 == 0:
                    logger.info(f"  Deleted {i}/{len(trade_group_ids)} trade groups...")

            except Exception as e:
                logger.error(f"Failed to delete trade group {group_id}: {e}")
                failed_count += 1

        logger.info(f"\n✅ Successfully deleted {deleted_count} trade groups")
        if failed_count > 0:
            logger.warning(f"⚠️ Failed to delete {failed_count} trade groups")

        # Calculate total trades deleted (approximately 2x trade groups for BUY+SELL)
        estimated_trades = deleted_count * 2
        logger.info(f"📊 Estimated total trades deleted: ~{estimated_trades}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Delete manually closed trades from database"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually execute deletions (not dry run)",
    )

    args = parser.parse_args()

    delete_manual_trades(dry_run=not args.execute)
