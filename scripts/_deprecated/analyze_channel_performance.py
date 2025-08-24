#!/usr/bin/env python3
"""
Analyze CHANNEL strategy performance to inform threshold adjustments
"""

import pandas as pd
import numpy as np
from src.data.supabase_client import SupabaseClient
from datetime import datetime, timedelta
from collections import defaultdict


def main():
    db = SupabaseClient()

    print("=" * 80)
    print("CHANNEL STRATEGY PERFORMANCE ANALYSIS")
    print("=" * 80)

    # Get all CHANNEL trades
    trades = (
        db.client.table("paper_trades")
        .select("*")
        .eq("strategy_name", "CHANNEL")
        .eq("side", "SELL")
        .execute()
    )

    if not trades.data:
        print("No completed CHANNEL trades found")
        return

    df = pd.DataFrame(trades.data)

    # Calculate key metrics
    print(f"\n📊 OVERALL STATISTICS:")
    print(f"Total trades: {len(df)}")
    print(f"Wins: {len(df[df['pnl'] > 0])}")
    print(f"Losses: {len(df[df['pnl'] < 0])}")
    print(f"Win rate: {(len(df[df['pnl'] > 0]) / len(df)) * 100:.1f}%")
    print(f"Average PnL: ${df['pnl'].mean():.2f}")
    print(f"Total PnL: ${df['pnl'].sum():.2f}")

    # Analyze losses in detail
    losses = df[df["pnl"] < 0].copy()
    if len(losses) > 0:
        # Calculate loss percentages
        losses["loss_pct"] = (
            losses["pnl"] / (losses["price"] * losses["amount"])
        ) * 100

        print(f"\n🔴 LOSS ANALYSIS ({len(losses)} trades):")
        print(f"Average loss: {losses['loss_pct'].mean():.2f}%")
        print(f"Median loss: {losses['loss_pct'].median():.2f}%")
        print(f"Smallest loss: {losses['loss_pct'].max():.2f}%")
        print(f"Largest loss: {losses['loss_pct'].min():.2f}%")

        # Loss distribution
        print("\nLoss Distribution:")
        bins = [0, -2, -3, -4, -5, -6, -10, -100]
        for i in range(len(bins) - 1):
            count = len(
                losses[
                    (losses["loss_pct"] <= bins[i]) & (losses["loss_pct"] > bins[i + 1])
                ]
            )
            if count > 0:
                print(
                    f"  {bins[i+1]}% to {bins[i]}%: {count} trades ({count/len(losses)*100:.1f}%)"
                )

    # Get OHLC data to analyze price action after entry
    print("\n" + "=" * 80)
    print("ANALYZING PRICE ACTION AFTER ENTRY")
    print("=" * 80)

    # Sample analysis for recent trades
    recent_trades = sorted(trades.data, key=lambda x: x["created_at"], reverse=True)[
        :10
    ]

    max_gains = []
    max_losses = []
    time_to_stop = []

    for trade in recent_trades:
        symbol = trade["symbol"]
        entry_time = datetime.fromisoformat(trade["created_at"].replace("Z", "+00:00"))
        exit_time = datetime.fromisoformat(trade["filled_at"].replace("Z", "+00:00"))
        entry_price = trade["price"]

        # Get 15min OHLC data for this period
        start = entry_time.isoformat()
        end = exit_time.isoformat()

        ohlc = (
            db.client.table("ohlc_recent")
            .select("*")
            .eq("symbol", symbol)
            .eq("timeframe", "15min")
            .gte("timestamp", start)
            .lte("timestamp", end)
            .order("timestamp")
            .execute()
        )

        if ohlc.data:
            prices = pd.DataFrame(ohlc.data)

            # Find maximum gain and loss during the trade
            highs = prices["high"].values
            lows = prices["low"].values

            max_gain_pct = (
                ((max(highs) - entry_price) / entry_price) * 100
                if len(highs) > 0
                else 0
            )
            max_loss_pct = (
                ((min(lows) - entry_price) / entry_price) * 100 if len(lows) > 0 else 0
            )

            max_gains.append(max_gain_pct)
            max_losses.append(max_loss_pct)

            # Time to hit stop
            hours_to_stop = (exit_time - entry_time).total_seconds() / 3600
            time_to_stop.append(hours_to_stop)

    if max_gains:
        print(f"\n📈 MISSED OPPORTUNITIES (last {len(max_gains)} trades):")
        print(f"Average max gain before stop: {np.mean(max_gains):.2f}%")
        print(f"Median max gain before stop: {np.median(max_gains):.2f}%")
        print(f"Best possible gain: {max(max_gains):.2f}%")

        # How many trades were profitable at some point?
        profitable_at_some_point = sum(
            1 for g in max_gains if g > 0.5
        )  # 0.5% threshold for fees
        print(
            f"Trades that were profitable at some point: {profitable_at_some_point}/{len(max_gains)}"
        )

        print(f"\n⏱️ TIMING ANALYSIS:")
        print(f"Average time to stop loss: {np.mean(time_to_stop):.1f} hours")
        print(f"Median time to stop loss: {np.median(time_to_stop):.1f} hours")
        print(f"Fastest stop hit: {min(time_to_stop):.1f} hours")
        print(f"Slowest stop hit: {max(time_to_stop):.1f} hours")

    # Analyze by symbol
    print("\n" + "=" * 80)
    print("PERFORMANCE BY SYMBOL")
    print("=" * 80)

    symbol_stats = (
        df.groupby("symbol")
        .agg({"pnl": ["count", "sum", "mean"], "amount": "first"})
        .round(2)
    )

    # Sort by total PnL
    symbol_stats.columns = ["trades", "total_pnl", "avg_pnl", "position_size"]
    symbol_stats = symbol_stats.sort_values("total_pnl")

    print("\nWorst performing symbols:")
    print(symbol_stats.head(10).to_string())

    # Get current thresholds
    print("\n" + "=" * 80)
    print("CURRENT THRESHOLDS & RECOMMENDATIONS")
    print("=" * 80)

    # Estimate current stop loss from data
    if len(losses) > 0:
        estimated_stop = losses["loss_pct"].median()
        print(f"\nEstimated stop loss: {estimated_stop:.2f}%")

    print("\n🎯 DATA-BACKED RECOMMENDATIONS:\n")

    if len(max_gains) > 0 and np.mean(max_gains) > 2:
        print("1. TRAILING STOP ACTIVATION:")
        print(f"   - Many trades reach +{np.mean(max_gains):.1f}% before reversing")
        print(f"   - Consider activating trailing stop at +{np.mean(max_gains)/2:.1f}%")

    if len(losses) > 0:
        median_loss = losses["loss_pct"].median()
        if median_loss < -4:
            print("\n2. STOP LOSS ADJUSTMENT:")
            print(f"   - Current stops around {median_loss:.1f}%")
            print(
                f"   - Consider tighter stops at {median_loss/2:.1f}% to reduce losses"
            )

        # Check if losses are quick
        if len(time_to_stop) > 0 and np.median(time_to_stop) < 12:
            print("\n3. ENTRY SIGNAL QUALITY:")
            print(
                f"   - Stops hit quickly (median {np.median(time_to_stop):.1f} hours)"
            )
            print("   - Suggests poor entry timing - need stronger confirmation")
            print("   - Consider adding filters like:")
            print("     • Minimum volume requirements")
            print("     • RSI confirmation (not just oversold)")
            print("     • Trend alignment check")

    if profitable_at_some_point > len(max_gains) * 0.3:
        print("\n4. TAKE PROFIT ADJUSTMENT:")
        print(
            f"   - {profitable_at_some_point}/{len(max_gains)} trades were profitable"
        )
        print(
            f"   - Consider lower take profit target: +{np.percentile(max_gains, 75):.1f}%"
        )

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
