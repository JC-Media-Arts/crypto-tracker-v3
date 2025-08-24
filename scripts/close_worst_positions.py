#!/usr/bin/env python3
"""
Close the worst performing paper trading positions to enforce position limits.
Target: 50 positions per strategy maximum.
"""

import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import List, Dict

sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient  # noqa: E402
from loguru import logger  # noqa: E402


def analyze_positions():
    """Analyze all open positions and their performance"""
    db = SupabaseClient()

    # Get all trades
    result = (
        db.client.table("paper_trades")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )

    if not result.data:
        logger.error("No trades found in database")
        return [], []

    # Group trades by trade_group_id
    trade_groups = defaultdict(list)
    for trade in result.data:
        group_id = trade.get("trade_group_id")
        if group_id:
            trade_groups[group_id].append(trade)

    # Analyze open positions
    open_positions = []

    for group_id, trades in trade_groups.items():
        has_buy = any(t["side"] == "BUY" for t in trades)
        has_sell = any(t["side"] == "SELL" for t in trades)

        if has_buy and not has_sell:
            # Position is still open
            buy_trade = next(t for t in trades if t["side"] == "BUY")
            open_positions.append(
                {
                    "trade_group_id": group_id,
                    "symbol": buy_trade["symbol"],
                    "strategy": buy_trade.get("strategy_name", "UNKNOWN"),
                    "entry_price": float(buy_trade["price"]),
                    "amount": float(buy_trade["amount"]),
                    "created_at": buy_trade["created_at"],
                    "trade_id": buy_trade["trade_id"],
                }
            )

    # Get current prices for all symbols from database
    symbols = list(set(p["symbol"] for p in open_positions))
    current_prices = {}

    logger.info(f"Fetching current prices for {len(symbols)} symbols...")

    # Get latest prices from ohlc_data table
    for symbol in symbols:
        try:
            result = (
                db.client.table("ohlc_data")
                .select("close")
                .eq("symbol", symbol)
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )

            if result.data and len(result.data) > 0:
                current_prices[symbol] = float(result.data[0]["close"])
            else:
                logger.warning(f"Could not get price for {symbol}")
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")

    # Calculate P&L for each position
    for pos in open_positions:
        if pos["symbol"] in current_prices:
            current_price = current_prices[pos["symbol"]]
            pos["current_price"] = current_price
            pos["pnl_pct"] = (
                (current_price - pos["entry_price"]) / pos["entry_price"]
            ) * 100
            pos["pnl_dollar"] = (current_price - pos["entry_price"]) * pos["amount"]
        else:
            pos["current_price"] = pos["entry_price"]
            pos["pnl_pct"] = 0
            pos["pnl_dollar"] = 0

    # Separate by strategy
    channel_positions = [p for p in open_positions if p["strategy"] == "CHANNEL"]
    other_positions = [p for p in open_positions if p["strategy"] != "CHANNEL"]

    return channel_positions, other_positions


def close_positions(positions_to_close: List[Dict], dry_run: bool = True):
    """Close the specified positions by creating SELL orders"""
    db = SupabaseClient()

    logger.info(
        f"{'DRY RUN: Would close' if dry_run else 'Closing'} {len(positions_to_close)} positions"
    )

    closed_count = 0
    for pos in positions_to_close:
        try:
            if not dry_run:
                # Create SELL trade to close position
                sell_trade = {
                    "symbol": pos["symbol"],
                    "side": "SELL",
                    "order_type": "MARKET",
                    "price": pos["current_price"],
                    "amount": pos["amount"],
                    "status": "FILLED",
                    "created_at": datetime.utcnow().isoformat(),
                    "filled_at": datetime.utcnow().isoformat(),
                    "fees": pos["current_price"]
                    * pos["amount"]
                    * 0.0026,  # 0.26% taker fee
                    "pnl": pos["pnl_dollar"],
                    "strategy_name": pos["strategy"],
                    "trading_engine": "manual_cleanup",
                    "exit_reason": "POSITION_LIMIT_CLEANUP",
                    "trade_group_id": pos["trade_group_id"],
                }

                result = db.client.table("paper_trades").insert(sell_trade).execute()
                if result.data:
                    closed_count += 1
                    logger.info(f"Closed {pos['symbol']} - P&L: {pos['pnl_pct']:.2f}%")
            else:
                logger.info(f"Would close {pos['symbol']} - P&L: {pos['pnl_pct']:.2f}%")
                closed_count += 1

        except Exception as e:
            logger.error(f"Error closing position {pos['trade_group_id']}: {e}")

    return closed_count


def main():
    """Main execution"""
    logger.info("=" * 60)
    logger.info("POSITION LIMIT ENFORCEMENT SCRIPT")
    logger.info("=" * 60)

    # Analyze current positions
    channel_positions, other_positions = analyze_positions()

    logger.info("\n📊 CURRENT POSITIONS:")
    logger.info(f"  CHANNEL: {len(channel_positions)}")
    logger.info(f"  Others: {len(other_positions)}")

    # Sort CHANNEL positions by P&L (worst first)
    channel_positions.sort(key=lambda x: x["pnl_pct"])

    # Determine how many to close
    target_channel_positions = 50
    positions_to_close = []

    if len(channel_positions) > target_channel_positions:
        num_to_close = len(channel_positions) - target_channel_positions
        positions_to_close = channel_positions[:num_to_close]

        logger.info(f"\n🎯 TARGET: {target_channel_positions} CHANNEL positions")
        logger.info(f"📉 Need to close: {num_to_close} positions")

        # Show worst performers
        logger.info("\n📊 WORST 10 PERFORMERS TO CLOSE:")
        for pos in positions_to_close[:10]:
            logger.info(
                f"  {pos['symbol']}: {pos['pnl_pct']:.2f}% (${pos['pnl_dollar']:.2f})"
            )

        # Calculate total impact
        total_pnl = sum(p["pnl_dollar"] for p in positions_to_close)
        avg_pnl = sum(p["pnl_pct"] for p in positions_to_close) / len(
            positions_to_close
        )

        logger.info(f"\n💰 IMPACT OF CLOSING {num_to_close} POSITIONS:")
        logger.info(f"  Total P&L: ${total_pnl:.2f}")
        logger.info(f"  Average P&L: {avg_pnl:.2f}%")

        # Ask for confirmation
        logger.info(f"\n⚠️  This will close {num_to_close} CHANNEL positions")
        response = input("Proceed? (yes/no/dry-run): ").lower()

        if response == "yes":
            closed = close_positions(positions_to_close, dry_run=False)
            logger.info(f"\n✅ Successfully closed {closed} positions")
        elif response == "dry-run":
            closed = close_positions(positions_to_close, dry_run=True)
            logger.info(f"\n🔍 Dry run completed - would close {closed} positions")
        else:
            logger.info("❌ Cancelled")
    else:
        logger.info(
            f"\n✅ CHANNEL positions ({len(channel_positions)}) already within limit ({target_channel_positions})"
        )


if __name__ == "__main__":
    main()
