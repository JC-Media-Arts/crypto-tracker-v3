#!/usr/bin/env python3
"""
Check trades without trade_group_id to see if they'll affect ML training.
"""

import sys
from pathlib import Path
from datetime import datetime
from collections import Counter

sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from loguru import logger


def check_old_trades():
    db = SupabaseClient()

    # Get trades without trade_group_id
    trades_without_group = []
    batch_limit = 1000
    batch_offset = 0

    print("Analyzing trades without trade_group_id...")

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

        trades_without_group.extend(batch.data)

        if len(batch.data) < batch_limit:
            break
        batch_offset += batch_limit

    print(f"\nFound {len(trades_without_group)} trades without trade_group_id")

    if not trades_without_group:
        print("No trades without trade_group_id found!")
        return

    # Analyze these trades
    # Check dates
    dates = []
    for trade in trades_without_group:
        if trade.get("created_at"):
            try:
                dt = datetime.fromisoformat(trade["created_at"].replace("Z", "+00:00"))
                dates.append(dt)
            except:
                pass

    if dates:
        oldest = min(dates)
        newest = max(dates)
        print(
            f'Date range: {oldest.strftime("%Y-%m-%d")} to {newest.strftime("%Y-%m-%d")}'
        )

    # Check if they have exit_price (are they closed?)
    with_exit_price = [t for t in trades_without_group if t.get("exit_price")]
    without_exit_price = [t for t in trades_without_group if not t.get("exit_price")]

    print(f"\nTrades with exit_price (closed): {len(with_exit_price)}")
    print(f"Trades without exit_price (open or BUY): {len(without_exit_price)}")

    # Check sides
    buy_trades = [t for t in trades_without_group if t.get("side") == "BUY"]
    sell_trades = [t for t in trades_without_group if t.get("side") == "SELL"]

    print(f"\nBUY trades: {len(buy_trades)}")
    print(f"SELL trades: {len(sell_trades)}")

    # Check strategies
    strategies = Counter(
        [t.get("strategy_name", "Unknown") for t in trades_without_group]
    )
    print(f"\nStrategies:")
    for strategy, count in strategies.items():
        print(f"  {strategy}: {count} trades")

    # Check if these are complete trades (have entry and exit info)
    complete_trades = [
        t
        for t in trades_without_group
        if t.get("entry_price") and t.get("exit_price") and t.get("pnl") is not None
    ]

    print(f"\nComplete trades (have entry, exit, and P&L): {len(complete_trades)}")

    if complete_trades:
        print(
            f"\n⚠️  IMPORTANT: These {len(complete_trades)} trades are COMPLETE and have P&L data!"
        )
        print(
            "They represent old-style single-record trades where BUY and SELL were in one record."
        )
        print("These WILL be included in ML training as they have all necessary data.")

    # Sample a few to see structure
    print("\nSample trades without trade_group_id:")
    for i, trade in enumerate(trades_without_group[:3]):
        print(f"\nTrade {i+1}:")
        print(f'  Symbol: {trade.get("symbol")}')
        print(f'  Side: {trade.get("side")}')
        print(f'  Entry Price: {trade.get("entry_price")}')
        print(f'  Exit Price: {trade.get("exit_price")}')
        print(f'  P&L: {trade.get("pnl")}')
        print(f'  Strategy: {trade.get("strategy_name")}')
        print(f'  Exit Reason: {trade.get("exit_reason")}')
        created = trade.get("created_at")
        print(f'  Created: {created[:19] if created else "N/A"}')

    # Check impact on ML training
    print("\n" + "=" * 60)
    print("IMPACT ON ML TRAINING:")
    print("=" * 60)

    if len(complete_trades) == len(trades_without_group):
        print("n✅ GOOD NEWS: All trades without trade_group_id are COMPLETE trades")
        print("   They have entry_price, exit_price, and P&L data.")
        print("   These are old-format trades that stored everything in one record.")
        print("   They WILL work fine for ML training!")
    else:
        incomplete = len(trades_without_group) - len(complete_trades)
        print(f"\n⚠️  WARNING: {incomplete} trades are incomplete")
        print("   These trades are missing critical data for ML training.")
        print("   Recommendation: Consider excluding these from training data.")

        # Show what's missing
        print("\n   Missing data breakdown:")
        no_entry = [t for t in trades_without_group if not t.get("entry_price")]
        no_exit = [t for t in trades_without_group if not t.get("exit_price")]
        no_pnl = [t for t in trades_without_group if t.get("pnl") is None]

        if no_entry:
            print(f"     - No entry_price: {len(no_entry)} trades")
        if no_exit:
            print(f"     - No exit_price: {len(no_exit)} trades")
        if no_pnl:
            print(f"     - No P&L: {len(no_pnl)} trades")


if __name__ == "__main__":
    check_old_trades()
