#!/usr/bin/env python3
"""
Comprehensive audit of paper_trades table to identify data quality issues.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter, defaultdict

sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from loguru import logger
import pandas as pd


def audit_paper_trades():
    """Perform comprehensive audit of paper trades data"""

    logger.info("Starting comprehensive paper trades audit...")

    db = SupabaseClient()

    # Fetch all trades
    all_trades = []
    batch_limit = 1000
    batch_offset = 0

    logger.info("Fetching all trades from database...")

    while True:
        batch = (
            db.client.table("paper_trades")
            .select("*")
            .order("created_at", desc=True)
            .range(batch_offset, batch_offset + batch_limit - 1)
            .execute()
        )

        if not batch.data:
            break

        all_trades.extend(batch.data)

        if len(batch.data) < batch_limit:
            break
        batch_offset += batch_limit

    logger.info(f"Fetched {len(all_trades)} total trades")

    # Organize trades by group
    trade_groups = defaultdict(list)
    for trade in all_trades:
        if trade.get("trade_group_id"):
            trade_groups[trade["trade_group_id"]].append(trade)

    print("\n" + "=" * 80)
    print("PAPER TRADES AUDIT REPORT")
    print("=" * 80)

    # 1. Basic Statistics
    print("\n📊 BASIC STATISTICS:")
    print(f"  Total trades: {len(all_trades)}")
    print(f"  Total trade groups: {len(trade_groups)}")

    buy_trades = [t for t in all_trades if t.get("side") == "BUY"]
    sell_trades = [t for t in all_trades if t.get("side") == "SELL"]
    print(f"  BUY trades: {len(buy_trades)}")
    print(f"  SELL trades: {len(sell_trades)}")

    # 2. Check for orphaned trades
    print("\n🔍 DATA INTEGRITY CHECKS:")

    orphaned_buys = 0
    orphaned_sells = 0
    incomplete_groups = 0

    for group_id, trades in trade_groups.items():
        sides = [t.get("side") for t in trades]
        if "BUY" in sides and "SELL" not in sides:
            orphaned_buys += 1
        elif "SELL" in sides and "BUY" not in sides:
            orphaned_sells += 1
        elif len(trades) == 1:
            incomplete_groups += 1

    if orphaned_buys > 0:
        print(f"  ⚠️  Orphaned BUY trades (no matching SELL): {orphaned_buys} groups")
    if orphaned_sells > 0:
        print(f"  ⚠️  Orphaned SELL trades (no matching BUY): {orphaned_sells} groups")
    if incomplete_groups > 0:
        print(
            f"  ⚠️  Incomplete trade groups (only 1 trade): {incomplete_groups} groups"
        )

    if orphaned_buys == 0 and orphaned_sells == 0 and incomplete_groups == 0:
        print(f"  ✅ All trade groups properly paired")

    # 3. Check for missing required fields
    print("\n📝 FIELD COMPLETENESS:")

    missing_fields = defaultdict(int)
    required_fields = [
        "symbol",
        "side",
        "price",
        "amount",
        "strategy_name",
        "trade_group_id",
        "status",
    ]

    for trade in all_trades:
        for field in required_fields:
            if not trade.get(field):
                missing_fields[field] += 1

    if missing_fields:
        for field, count in missing_fields.items():
            print(f"  ⚠️  Missing {field}: {count} trades")
    else:
        print(f"  ✅ All required fields present")

    # 4. Check for suspicious prices
    print("\n💰 PRICE ANOMALIES:")

    zero_prices = [t for t in all_trades if t.get("price", 0) <= 0]
    huge_prices = [t for t in all_trades if t.get("price", 0) > 100000]

    if zero_prices:
        print(f"  ⚠️  Zero or negative prices: {len(zero_prices)} trades")
    if huge_prices:
        print(f"  ⚠️  Suspiciously high prices (>$100k): {len(huge_prices)} trades")

    if not zero_prices and not huge_prices:
        print(f"  ✅ All prices within reasonable range")

    # 5. Check P&L consistency
    print("\n📈 P&L ANALYSIS:")

    trades_with_pnl = [t for t in sell_trades if t.get("pnl") is not None]

    if trades_with_pnl:
        pnls = [t["pnl"] for t in trades_with_pnl]
        total_pnl = sum(pnls)
        avg_pnl = total_pnl / len(pnls)
        max_pnl = max(pnls)
        min_pnl = min(pnls)

        print(f"  Total P&L: ${total_pnl:.2f}")
        print(f"  Average P&L per trade: ${avg_pnl:.2f}")
        print(f"  Best trade: ${max_pnl:.2f}")
        print(f"  Worst trade: ${min_pnl:.2f}")

        # Check for unrealistic P&L
        huge_wins = [t for t in trades_with_pnl if t["pnl"] > 100]
        huge_losses = [t for t in trades_with_pnl if t["pnl"] < -100]

        if huge_wins:
            print(f"  ⚠️  Unusually large wins (>$100): {len(huge_wins)} trades")
        if huge_losses:
            print(f"  ⚠️  Unusually large losses (<-$100): {len(huge_losses)} trades")

    # 6. Strategy distribution
    print("\n🎯 STRATEGY DISTRIBUTION:")

    strategies = Counter([t.get("strategy_name", "Unknown") for t in all_trades])
    for strategy, count in strategies.most_common():
        print(f"  {strategy}: {count} trades")

    # 7. Exit reason analysis
    print("\n🚪 EXIT REASONS:")

    exit_reasons = Counter(
        [t.get("exit_reason", "None") for t in sell_trades if t.get("exit_reason")]
    )

    if exit_reasons:
        for reason, count in exit_reasons.most_common(10):
            print(f"  {reason}: {count} trades")
    else:
        print("  No exit reasons recorded")

    # 8. Time-based analysis
    print("\n⏰ TEMPORAL ANALYSIS:")

    if all_trades:
        dates = []
        for trade in all_trades:
            if trade.get("created_at"):
                try:
                    dt = datetime.fromisoformat(
                        trade["created_at"].replace("Z", "+00:00")
                    )
                    dates.append(dt)
                except:
                    pass

        if dates:
            oldest = min(dates)
            newest = max(dates)

            print(f"  Oldest trade: {oldest.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            print(f"  Newest trade: {newest.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            print(f"  Time span: {(newest - oldest).days} days")

            # Check for future dates
            now = datetime.now(timezone.utc)
            future_trades = [
                t
                for t in all_trades
                if t.get("created_at")
                and datetime.fromisoformat(t["created_at"].replace("Z", "+00:00")) > now
            ]

            if future_trades:
                print(f"  ⚠️  Trades with future timestamps: {len(future_trades)}")

    # 9. Duplicate detection
    print("\n🔄 DUPLICATE DETECTION:")

    # Check for exact duplicates (same symbol, price, amount, timestamp)
    trade_signatures = []
    for trade in all_trades:
        sig = f"{trade.get('symbol')}_{trade.get('price')}_{trade.get('amount')}_{trade.get('created_at')}"
        trade_signatures.append(sig)

    sig_counts = Counter(trade_signatures)
    duplicates = {sig: count for sig, count in sig_counts.items() if count > 1}

    if duplicates:
        print(f"  ⚠️  Potential duplicate trades: {len(duplicates)} sets")
        for sig, count in list(duplicates.items())[:5]:
            print(f"    - {sig[:50]}...: {count} duplicates")
    else:
        print(f"  ✅ No duplicate trades detected")

    # 10. Symbol analysis
    print("\n🪙 SYMBOL ANALYSIS:")

    symbols = Counter([t.get("symbol", "Unknown") for t in all_trades])
    print(f"  Total unique symbols: {len(symbols)}")
    print(f"  Top 5 most traded:")
    for symbol, count in symbols.most_common(5):
        print(f"    - {symbol}: {count} trades")

    # Check for invalid symbols
    invalid_symbols = [
        s for s in symbols.keys() if not s or s == "Unknown" or len(s) > 10
    ]
    if invalid_symbols:
        print(f"  ⚠️  Invalid or suspicious symbols: {invalid_symbols}")

    # 11. Check for test/debug data
    print("\n🧪 TEST DATA CHECK:")

    test_indicators = ["test", "debug", "demo", "sample"]
    test_trades = []

    for trade in all_trades:
        for field in ["symbol", "strategy_name", "exit_reason", "trade_group_id"]:
            value = str(trade.get(field, "")).lower()
            if any(indicator in value for indicator in test_indicators):
                test_trades.append(trade)
                break

    if test_trades:
        print(f"  ⚠️  Potential test/debug trades: {len(test_trades)}")
    else:
        print(f"  ✅ No obvious test data detected")

    # 12. Final summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    issues = []
    if orphaned_buys > 0:
        issues.append(f"Orphaned BUY trades: {orphaned_buys}")
    if orphaned_sells > 0:
        issues.append(f"Orphaned SELL trades: {orphaned_sells}")
    if missing_fields:
        issues.append(f"Missing fields in {sum(missing_fields.values())} trades")
    if zero_prices:
        issues.append(f"Zero/negative prices: {len(zero_prices)}")
    if huge_prices:
        issues.append(f"Suspicious prices: {len(huge_prices)}")
    if duplicates:
        issues.append(f"Duplicate trades: {len(duplicates)} sets")
    if test_trades:
        issues.append(f"Test data: {len(test_trades)} trades")

    if issues:
        print("⚠️  ISSUES FOUND:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("✅ DATA LOOKS CLEAN - No major issues detected")

    # Show open positions
    print("\n📂 CURRENT OPEN POSITIONS:")
    open_positions = 0
    for group_id, trades in trade_groups.items():
        sides = [t.get("side") for t in trades]
        if "BUY" in sides and "SELL" not in sides:
            open_positions += 1

    print(f"  Open positions: {open_positions}")

    # Group open positions by strategy
    open_by_strategy = defaultdict(int)
    for group_id, trades in trade_groups.items():
        sides = [t.get("side") for t in trades]
        if "BUY" in sides and "SELL" not in sides:
            strategy = trades[0].get("strategy_name", "Unknown")
            open_by_strategy[strategy] += 1

    for strategy, count in open_by_strategy.items():
        print(f"    - {strategy}: {count} positions")


if __name__ == "__main__":
    audit_paper_trades()
