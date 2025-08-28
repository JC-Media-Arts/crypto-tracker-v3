#!/usr/bin/env python3
"""
Emergency script to close excess CHANNEL positions.
Closes oldest positions first to get within limits.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
import asyncio

sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from src.trading.simple_paper_trader_v2 import SimplePaperTraderV2
from loguru import logger
import pandas as pd


async def close_excess_positions(dry_run=True, max_to_close=None):
    """Close excess CHANNEL positions to get within limits"""

    logger.info("Starting emergency position cleanup...")

    db = SupabaseClient()

    # Fetch all open positions
    all_trades = []
    batch_limit = 1000
    batch_offset = 0

    while True:
        batch_result = (
            db.client.table("paper_trades")
            .select("*")
            .order("created_at", desc=True)
            .range(batch_offset, batch_offset + batch_limit - 1)
            .execute()
        )

        if not batch_result.data:
            break

        all_trades.extend(batch_result.data)

        if len(batch_result.data) < batch_limit:
            break
        batch_offset += batch_limit

    # Group by trade_group_id to find open positions
    open_channel_positions = []

    for trade in all_trades:
        if trade.get("side") == "BUY" and trade.get("strategy_name") == "CHANNEL":
            group_id = trade.get("trade_group_id")
            if group_id:
                # Check if this group has a SELL
                has_sell = any(
                    t.get("trade_group_id") == group_id and t.get("side") == "SELL"
                    for t in all_trades
                )
                if not has_sell:
                    open_channel_positions.append(
                        {
                            "group_id": group_id,
                            "symbol": trade["symbol"],
                            "price": trade["price"],
                            "amount": trade["amount"],
                            "created_at": trade["created_at"],
                        }
                    )

    logger.info(f"Found {len(open_channel_positions)} open CHANNEL positions")

    # Sort by age (oldest first)
    open_channel_positions.sort(key=lambda x: x["created_at"])

    # Calculate how many to close
    max_channel_positions = 50  # Target
    excess = len(open_channel_positions) - max_channel_positions

    if excess <= 0:
        logger.info("✅ CHANNEL positions within limit, nothing to close")
        return

    # Limit how many we close if specified
    if max_to_close:
        excess = min(excess, max_to_close)

    positions_to_close = open_channel_positions[:excess]

    logger.info(f"Need to close {excess} CHANNEL positions")

    if dry_run:
        logger.info("🔍 DRY RUN - No changes will be made")
        logger.info("\nPositions that would be closed:")
        for i, pos in enumerate(positions_to_close[:20], 1):
            created_at = datetime.fromisoformat(
                pos["created_at"].replace("Z", "+00:00")
            )
            age_hours = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
            logger.info(
                f"  {i}. {pos['symbol']} - Age: {age_hours:.1f}h - Group: {pos['group_id'][:8]}..."
            )

        if len(positions_to_close) > 20:
            logger.info(f"  ... and {len(positions_to_close) - 20} more")

        logger.info("\n💡 Run with --execute to actually close these positions")
    else:
        logger.info("⚡ EXECUTING CLOSES...")

        # Initialize paper trader to create SELL trades
        paper_trader = SimplePaperTraderV2(
            initial_balance=10000, max_positions=150, max_positions_per_strategy=50
        )

        # Get current prices
        symbols = list(set(pos["symbol"] for pos in positions_to_close))
        current_prices = {}

        for symbol in symbols:
            try:
                price_result = (
                    db.client.table("ohlc_data")
                    .select("close")
                    .eq("symbol", symbol)
                    .order("timestamp", desc=True)
                    .limit(1)
                    .execute()
                )

                if price_result.data:
                    current_prices[symbol] = float(price_result.data[0]["close"])
            except Exception as e:
                logger.error(f"Could not get price for {symbol}: {e}")

        # Create SELL trades
        closed_count = 0
        total_pnl = 0

        for pos in positions_to_close:
            symbol = pos["symbol"]

            if symbol not in current_prices:
                logger.warning(f"No price for {symbol}, skipping")
                continue

            current_price = current_prices[symbol]
            entry_price = float(pos["price"])
            amount = float(pos["amount"])

            # Calculate P&L
            pnl = (current_price - entry_price) * amount
            pnl_pct = ((current_price - entry_price) / entry_price) * 100

            # Create SELL trade record (with required fields)
            sell_trade = {
                "symbol": symbol,
                "side": "SELL",
                "order_type": "MARKET",  # Required field
                "status": "FILLED",  # Required field
                "price": current_price,
                "amount": amount,
                "strategy_name": "CHANNEL",
                "trade_group_id": pos["group_id"],
                "exit_reason": "POSITION_LIMIT_CLEANUP",
                "pnl": pnl,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            # Insert into database
            try:
                result = db.client.table("paper_trades").insert(sell_trade).execute()
                closed_count += 1
                total_pnl += pnl
                logger.info(f"  Closed {symbol}: P&L ${pnl:.2f} ({pnl_pct:.2f}%)")
            except Exception as e:
                logger.error(f"Failed to close {symbol}: {e}")

        logger.info(f"\n✅ Closed {closed_count} positions")
        logger.info(f"📊 Total P&L from cleanup: ${total_pnl:.2f}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Close excess CHANNEL positions")
    parser.add_argument(
        "--execute", action="store_true", help="Actually execute closes (not dry run)"
    )
    parser.add_argument("--max", type=int, help="Maximum number of positions to close")

    args = parser.parse_args()

    asyncio.run(close_excess_positions(dry_run=not args.execute, max_to_close=args.max))
