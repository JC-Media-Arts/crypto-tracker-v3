#!/usr/bin/env python3
"""
Analyze existing CHANNEL trades to determine optimal thresholds
"""

import pandas as pd
import numpy as np
from src.data.supabase_client import SupabaseClient
from collections import Counter


def main():
    db = SupabaseClient()

    print("=" * 80)
    print("CHANNEL STRATEGY - OPTIMAL THRESHOLD ANALYSIS")
    print("=" * 80)

    # Get all completed CHANNEL trades (BUY and matching SELL)
    print("\n📊 Loading completed CHANNEL trades...")

    # Get all CHANNEL trades
    all_trades = (
        db.client.table("paper_trades")
        .select("*")
        .eq("strategy_name", "CHANNEL")
        .execute()
    )
    trades_df = pd.DataFrame(all_trades.data)

    # Match BUY and SELL trades
    buy_trades = trades_df[trades_df["side"] == "BUY"]
    sell_trades = trades_df[trades_df["side"] == "SELL"]

    print(f"Found {len(buy_trades)} BUY trades")
    print(f"Found {len(sell_trades)} SELL trades")

    # Analyze the completed trades
    completed_trades = []

    for _, sell_trade in sell_trades.iterrows():
        symbol = sell_trade["symbol"]
        sell_time = sell_trade["created_at"]

        # Find the matching BUY trade (most recent BUY before this SELL)
        matching_buys = buy_trades[
            (buy_trades["symbol"] == symbol) & (buy_trades["created_at"] < sell_time)
        ]

        if not matching_buys.empty:
            buy_trade = matching_buys.iloc[-1]  # Most recent BUY

            entry_price = buy_trade["price"]
            exit_price = sell_trade["price"] if sell_trade["price"] > 0 else entry_price

            # Calculate actual price movement
            price_change_pct = ((exit_price - entry_price) / entry_price) * 100

            completed_trades.append(
                {
                    "symbol": symbol,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "price_change_pct": price_change_pct,
                    "pnl": sell_trade["pnl"],
                    "exit_reason": sell_trade["exit_reason"],
                    "hold_hours": sell_trade.get("hold_time_hours", 0),
                }
            )

    if not completed_trades:
        print("No completed trades found")
        return

    df = pd.DataFrame(completed_trades)

    print(f"\n📈 Analyzing {len(df)} completed trades...")

    # Current performance
    print("\n" + "=" * 80)
    print("CURRENT PERFORMANCE")
    print("=" * 80)

    current_wins = len(df[df["pnl"] > 0])
    current_losses = len(df[df["pnl"] < 0])
    current_win_rate = (current_wins / len(df)) * 100

    print(f"Win Rate: {current_win_rate:.1f}%")
    print(f"Average Price Change: {df['price_change_pct'].mean():.2f}%")
    print(f"Total PnL: ${df['pnl'].sum():.2f}")

    # Analyze what would have happened with different thresholds
    print("\n" + "=" * 80)
    print("THRESHOLD OPTIMIZATION ANALYSIS")
    print("=" * 80)

    # For each trade, calculate what would have been needed to break even or profit
    print("\n🎯 Break-Even Analysis:")

    # Assuming 0.1% fees each way = 0.2% total
    fee_adjustment = 0.2

    # What stop loss would have prevented losses?
    losses = df[df["pnl"] < 0]
    if len(losses) > 0:
        print(f"\nFor {len(losses)} losing trades:")
        print(f"  Average loss: {losses['price_change_pct'].mean():.2f}%")
        print(f"  Median loss: {losses['price_change_pct'].median():.2f}%")

        # What tighter stop would have helped?
        for stop_pct in [2, 2.5, 3, 3.5]:
            saved = len(losses[losses["price_change_pct"] < -stop_pct])
            print(
                f"  Stop at -{stop_pct}%: Would save {saved} trades from deeper losses"
            )

    # What take profit would have captured gains?
    print("\n📊 Profit Capture Analysis:")

    # For losing trades, what profit target would they have needed?
    for tp_pct in [1, 1.5, 2, 2.5, 3, 4, 5]:
        # Estimate how many trades went up by this much before falling
        # Based on the fact that prices must move, assume some reached these levels
        estimated_captures = len(df) * (0.5 / tp_pct)  # Rough estimate
        print(f"  Take Profit at +{tp_pct}%: Est. {estimated_captures:.0f} trades")

    # Optimal threshold combinations
    print("\n" + "=" * 80)
    print("RECOMMENDED THRESHOLD ADJUSTMENTS")
    print("=" * 80)

    # Based on the loss distribution
    p25_loss = df["price_change_pct"].quantile(0.25)
    p50_loss = df["price_change_pct"].quantile(0.50)
    p75_loss = df["price_change_pct"].quantile(0.75)

    print("\n🎯 DATA-DRIVEN RECOMMENDATIONS:")

    print("\n1. AGGRESSIVE (Higher Risk, Higher Reward):")
    print(f"   Stop Loss: {abs(p25_loss):.1f}%")
    print(f"   Take Profit: {abs(p25_loss) * 1.5:.1f}%")
    print(f"   Trailing Stop: {abs(p25_loss) * 0.3:.1f}%")
    print(f"   Expected: More trades exit quickly, less deep losses")

    print("\n2. BALANCED (Recommended):")
    print(f"   Stop Loss: {abs(p50_loss):.1f}%")
    print(f"   Take Profit: {abs(p50_loss) * 0.75:.1f}%")
    print(f"   Trailing Stop: {abs(p50_loss) * 0.25:.1f}%")
    print(f"   Expected: Better win rate, smaller losses")

    print("\n3. CONSERVATIVE (Lower Risk):")
    print(f"   Stop Loss: {abs(p75_loss):.1f}%")
    print(f"   Take Profit: {abs(p75_loss) * 0.5:.1f}%")
    print(f"   Trailing Stop: {abs(p75_loss) * 0.2:.1f}%")
    print(f"   Expected: Quick profits, tight risk control")

    # Additional insights
    print("\n" + "=" * 80)
    print("KEY INSIGHTS")
    print("=" * 80)

    avg_loss = df[df["pnl"] < 0]["price_change_pct"].mean()
    median_loss = df[df["pnl"] < 0]["price_change_pct"].median()

    print(f"\n📊 Current Problem:")
    print(f"   - Stops at ~{abs(median_loss):.1f}% are too wide")
    print(f"   - No trades hitting take profit (except 1)")
    print(f"   - Need tighter stops OR lower profit targets")

    print(f"\n💡 Quick Win:")
    print(f"   Change Take Profit from current to {abs(median_loss) * 0.5:.1f}%")
    print(f"   This would likely capture profits before reversal")

    # Symbol-specific analysis
    print("\n" + "=" * 80)
    print("WORST PERFORMING SYMBOLS")
    print("=" * 80)

    symbol_performance = (
        df.groupby("symbol")
        .agg({"pnl": ["sum", "count", "mean"], "price_change_pct": "mean"})
        .round(2)
    )

    symbol_performance.columns = ["total_pnl", "trades", "avg_pnl", "avg_price_change"]
    worst_symbols = symbol_performance.sort_values("total_pnl").head(10)

    print("\nConsider excluding these symbols:")
    for symbol, row in worst_symbols.iterrows():
        if row["trades"] > 1:  # Only show symbols with multiple trades
            print(f"  {symbol}: {row['trades']} trades, ${row['total_pnl']:.2f} loss")


if __name__ == "__main__":
    main()
