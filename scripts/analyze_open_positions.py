#!/usr/bin/env python3
"""
Analyze and clean up open positions in the paper trading system.
Identifies truly open positions vs closed ones that may appear open.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from loguru import logger
import pandas as pd


def analyze_open_positions():
    """Analyze all trades to identify truly open positions"""

    logger.info("Analyzing paper trades to identify truly open positions...")

    db = SupabaseClient()

    # Fetch ALL trades
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

    logger.info(f"Fetched {len(all_trades)} total trades from database")

    # Group by trade_group_id
    trades_by_group = defaultdict(
        lambda: {"buys": [], "sells": [], "symbol": None, "strategy": None}
    )

    for trade in all_trades:
        group_id = trade.get("trade_group_id")
        if not group_id:
            continue

        trades_by_group[group_id]["symbol"] = trade["symbol"]
        trades_by_group[group_id]["strategy"] = trade.get("strategy_name", "N/A")

        if trade["side"] == "BUY":
            trades_by_group[group_id]["buys"].append(trade)
        else:
            trades_by_group[group_id]["sells"].append(trade)

    # Analyze positions
    open_positions = []
    closed_positions = []
    strategy_counts = defaultdict(int)
    symbol_counts = defaultdict(int)

    for group_id, group_data in trades_by_group.items():
        has_buys = len(group_data["buys"]) > 0
        has_sells = len(group_data["sells"]) > 0

        if has_buys and not has_sells:
            # Truly open position
            open_positions.append(
                {
                    "group_id": group_id,
                    "symbol": group_data["symbol"],
                    "strategy": group_data["strategy"],
                    "buy_count": len(group_data["buys"]),
                    "created_at": min(b["created_at"] for b in group_data["buys"]),
                }
            )
            strategy_counts[group_data["strategy"]] += 1
            symbol_counts[group_data["symbol"]] += 1
        elif has_buys and has_sells:
            # Closed position
            closed_positions.append(
                {
                    "group_id": group_id,
                    "symbol": group_data["symbol"],
                    "strategy": group_data["strategy"],
                }
            )

    # Print analysis
    print("\n" + "=" * 80)
    print("PAPER TRADING POSITION ANALYSIS")
    print("=" * 80)

    print(f"\n📊 SUMMARY:")
    print(f"  Total Trade Groups: {len(trades_by_group)}")
    print(f"  Open Positions: {len(open_positions)}")
    print(f"  Closed Positions: {len(closed_positions)}")

    print(f"\n📈 OPEN POSITIONS BY STRATEGY:")
    for strategy, count in sorted(
        strategy_counts.items(), key=lambda x: x[1], reverse=True
    ):
        print(f"  {strategy}: {count} positions")

    print(f"\n🪙 TOP 10 SYMBOLS WITH MOST OPEN POSITIONS:")
    for symbol, count in sorted(
        symbol_counts.items(), key=lambda x: x[1], reverse=True
    )[:10]:
        print(f"  {symbol}: {count} positions")

    # Check for duplicate positions on same symbol
    symbol_strategy_pairs = defaultdict(list)
    for pos in open_positions:
        key = f"{pos['symbol']}_{pos['strategy']}"
        symbol_strategy_pairs[key].append(pos)

    duplicates = {k: v for k, v in symbol_strategy_pairs.items() if len(v) > 1}

    if duplicates:
        print(f"\n⚠️  DUPLICATE POSITIONS (same symbol/strategy):")
        for key, positions in duplicates.items():
            symbol, strategy = key.split("_", 1)
            print(f"  {symbol} ({strategy}): {len(positions)} duplicate positions")
            for pos in positions[:3]:  # Show first 3
                print(
                    f"    - Group ID: {pos['group_id'][:8]}... Created: {pos['created_at']}"
                )

    # Identify old positions that should be closed
    now = datetime.now(timezone.utc)
    old_positions = []

    for pos in open_positions:
        created_at = datetime.fromisoformat(pos["created_at"].replace("Z", "+00:00"))
        age_hours = (now - created_at).total_seconds() / 3600

        if age_hours > 72:  # Positions older than 72 hours
            old_positions.append({**pos, "age_hours": age_hours})

    if old_positions:
        print(f"\n⏰ OLD POSITIONS (>72 hours):")
        print(f"  Found {len(old_positions)} positions older than 72 hours")
        for pos in sorted(old_positions, key=lambda x: x["age_hours"], reverse=True)[
            :10
        ]:
            print(
                f"  {pos['symbol']} ({pos['strategy']}): {pos['age_hours']:.1f} hours old"
            )

    # Check against configured limits
    print(f"\n🚨 LIMIT VIOLATIONS:")
    max_per_strategy = 50  # From config
    max_total = 150  # From config

    if len(open_positions) > max_total:
        print(
            f"  ❌ Total positions ({len(open_positions)}) exceeds limit ({max_total})"
        )
    else:
        print(f"  ✅ Total positions ({len(open_positions)}) within limit ({max_total})")

    for strategy, count in strategy_counts.items():
        if count > max_per_strategy:
            print(
                f"  ❌ {strategy}: {count} positions exceeds limit ({max_per_strategy})"
            )
        else:
            print(
                f"  ✅ {strategy}: {count} positions within limit ({max_per_strategy})"
            )

    # Recommendations
    print(f"\n💡 RECOMMENDATIONS:")

    if len(open_positions) > max_total:
        excess = len(open_positions) - max_total
        print(f"  1. Close {excess} positions to get within total limit")

    for strategy, count in strategy_counts.items():
        if count > max_per_strategy:
            excess = count - max_per_strategy
            print(
                f"  2. Close {excess} {strategy} positions to get within strategy limit"
            )

    if old_positions:
        print(
            f"  3. Consider closing {len(old_positions)} positions older than 72 hours"
        )

    if duplicates:
        total_dups = sum(len(v) - 1 for v in duplicates.values())
        print(f"  4. Close {total_dups} duplicate positions on same symbol/strategy")

    return open_positions, closed_positions, strategy_counts


def close_excess_positions(dry_run=True):
    """Close excess positions to get within limits"""

    open_positions, _, strategy_counts = analyze_open_positions()

    if not open_positions:
        print("\nNo open positions to close.")
        return

    # Identify positions to close
    positions_to_close = []

    # First, close positions that exceed strategy limits
    for strategy, count in strategy_counts.items():
        if count > 50:  # Max per strategy
            excess = count - 50
            strategy_positions = [
                p for p in open_positions if p["strategy"] == strategy
            ]
            # Sort by age (oldest first)
            strategy_positions.sort(key=lambda x: x["created_at"])
            positions_to_close.extend(strategy_positions[:excess])

    # Then, if total still exceeds limit, close oldest
    remaining_open = len(open_positions) - len(positions_to_close)
    if remaining_open > 150:  # Max total
        excess = remaining_open - 150
        # Get positions not already marked for closing
        close_ids = {p["group_id"] for p in positions_to_close}
        available = [p for p in open_positions if p["group_id"] not in close_ids]
        available.sort(key=lambda x: x["created_at"])
        positions_to_close.extend(available[:excess])

    if not positions_to_close:
        print("\n✅ All positions within limits, nothing to close.")
        return

    print(f"\n🎯 POSITIONS TO CLOSE: {len(positions_to_close)}")

    if dry_run:
        print("\n⚠️  DRY RUN - No changes will be made")
        print("\nPositions that would be closed:")
        for pos in positions_to_close[:20]:  # Show first 20
            print(
                f"  - {pos['symbol']} ({pos['strategy']}) - Group: {pos['group_id'][:8]}..."
            )
        if len(positions_to_close) > 20:
            print(f"  ... and {len(positions_to_close) - 20} more")
        print("\nRun with --execute to actually close these positions")
    else:
        print("\n⚡ EXECUTING CLOSES...")
        # Here you would implement the actual closing logic
        # This would involve creating SELL trades for each position
        print("(Close logic not implemented yet - would create SELL trades here)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Analyze and clean up open positions")
    parser.add_argument("--close", action="store_true", help="Close excess positions")
    parser.add_argument(
        "--execute", action="store_true", help="Actually execute closes (not dry run)"
    )

    args = parser.parse_args()

    if args.close:
        close_excess_positions(dry_run=not args.execute)
    else:
        analyze_open_positions()
