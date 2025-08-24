#!/usr/bin/env python3
"""
Backtest different threshold combinations for CHANNEL strategy
Uses last 14 days of data to find optimal parameters
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.data.supabase_client import SupabaseClient
from itertools import product
from collections import defaultdict


def simulate_trade(
    entry_price, ohlc_data, stop_loss_pct, take_profit_pct, trailing_stop_pct
):
    """
    Simulate a single trade with given thresholds
    Returns: (exit_reason, pnl_pct, bars_held)
    """
    highest_price = entry_price
    stop_price = entry_price * (1 - stop_loss_pct)
    target_price = entry_price * (1 + take_profit_pct)

    for i, bar in enumerate(ohlc_data):
        # Update highest price for trailing stop
        if bar["high"] > highest_price:
            highest_price = bar["high"]

        # Calculate current trailing stop
        trailing_stop_price = highest_price * (1 - trailing_stop_pct)

        # Check exit conditions (in order of priority)
        # Check if stop loss hit
        if bar["low"] <= stop_price:
            exit_price = stop_price
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100
            return "stop_loss", pnl_pct, i + 1

        # Check if trailing stop hit (only if we were profitable)
        if highest_price > entry_price * 1.001:  # Was profitable
            if bar["low"] <= trailing_stop_price:
                exit_price = trailing_stop_price
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                return "trailing_stop", pnl_pct, i + 1

        # Check if take profit hit
        if bar["high"] >= target_price:
            exit_price = target_price
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100
            return "take_profit", pnl_pct, i + 1

    # Max hold time reached
    exit_price = ohlc_data[-1]["close"] if ohlc_data else entry_price
    pnl_pct = ((exit_price - entry_price) / entry_price) * 100
    return "time_exit", pnl_pct, len(ohlc_data)


def backtest_strategy(
    signals_df, ohlc_dict, stop_loss, take_profit, trailing_stop, max_bars=96
):
    """
    Backtest strategy with given thresholds
    max_bars: Maximum bars to hold (96 = 24 hours for 15min bars)
    """
    results = []

    for _, signal in signals_df.iterrows():
        symbol = signal["symbol"]
        entry_time = signal["timestamp"]
        entry_price = signal["entry_price"]

        # Get OHLC data after entry
        symbol_ohlc = ohlc_dict.get(symbol, pd.DataFrame())
        if symbol_ohlc.empty:
            continue

        # Filter to bars after entry
        future_bars = symbol_ohlc[symbol_ohlc["timestamp"] > entry_time].head(max_bars)
        if future_bars.empty:
            continue

        # Simulate the trade
        exit_reason, pnl_pct, bars_held = simulate_trade(
            entry_price,
            future_bars.to_dict("records"),
            stop_loss,
            take_profit,
            trailing_stop,
        )

        results.append(
            {
                "symbol": symbol,
                "entry_time": entry_time,
                "entry_price": entry_price,
                "exit_reason": exit_reason,
                "pnl_pct": pnl_pct,
                "bars_held": bars_held,
            }
        )

    return pd.DataFrame(results)


def main():
    db = SupabaseClient()

    print("=" * 80)
    print("CHANNEL STRATEGY BACKTEST - LAST 2 DAYS")
    print("=" * 80)

    # Get actual CHANNEL trades from last 2 days as entry signals
    start_date = (datetime.now() - timedelta(days=2)).isoformat()

    print("\n📊 Loading historical CHANNEL trades...")
    # Get BUY trades (entries) from paper_trades
    trades = (
        db.client.table("paper_trades")
        .select("*")
        .eq("strategy_name", "CHANNEL")
        .eq("side", "BUY")
        .gte("created_at", start_date)
        .execute()
    )

    if not trades.data:
        print("No CHANNEL entry trades found in the last 14 days")
        return

    # Convert to signals format
    signals_df = pd.DataFrame(trades.data)
    signals_df["timestamp"] = pd.to_datetime(signals_df["created_at"])
    signals_df["entry_price"] = signals_df["price"]
    print(f"Found {len(signals_df)} CHANNEL entry signals")

    # Get unique symbols
    symbols = signals_df["symbol"].unique()
    print(f"Across {len(symbols)} symbols")

    # Load OHLC data for all symbols
    print("\n📈 Loading price data...")
    ohlc_dict = {}

    for symbol in symbols:
        ohlc = (
            db.client.table("ohlc_recent")
            .select("*")
            .eq("symbol", symbol)
            .eq("timeframe", "15min")
            .gte("timestamp", start_date)
            .order("timestamp")
            .execute()
        )

        if ohlc.data:
            ohlc_dict[symbol] = pd.DataFrame(ohlc.data)
            ohlc_dict[symbol]["timestamp"] = pd.to_datetime(
                ohlc_dict[symbol]["timestamp"]
            )

    print(f"Loaded data for {len(ohlc_dict)} symbols")

    # Define parameter ranges to test
    stop_losses = [0.02, 0.025, 0.03, 0.035, 0.04, 0.045, 0.05]  # 2% to 5%
    take_profits = [0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10]  # 2% to 10%
    trailing_stops = [0.01, 0.015, 0.02, 0.025, 0.03]  # 1% to 3%

    print(
        f"\n🔬 Testing {len(stop_losses) * len(take_profits) * len(trailing_stops)} parameter combinations..."
    )

    # Store results for all combinations
    all_results = []

    for sl, tp, ts in product(stop_losses, take_profits, trailing_stops):
        # Skip invalid combinations
        if tp <= sl:  # Take profit must be higher than stop loss
            continue

        results = backtest_strategy(signals_df, ohlc_dict, sl, tp, ts)

        if len(results) > 0:
            win_rate = (results["pnl_pct"] > 0).sum() / len(results) * 100
            avg_pnl = results["pnl_pct"].mean()
            total_pnl = results["pnl_pct"].sum()
            sharpe = (
                avg_pnl / results["pnl_pct"].std()
                if results["pnl_pct"].std() > 0
                else 0
            )

            # Count exit reasons
            exit_counts = results["exit_reason"].value_counts().to_dict()

            all_results.append(
                {
                    "stop_loss": sl * 100,
                    "take_profit": tp * 100,
                    "trailing_stop": ts * 100,
                    "trades": len(results),
                    "win_rate": win_rate,
                    "avg_pnl_pct": avg_pnl,
                    "total_pnl_pct": total_pnl,
                    "sharpe": sharpe,
                    "stop_losses": exit_counts.get("stop_loss", 0),
                    "take_profits": exit_counts.get("take_profit", 0),
                    "trailing_stops": exit_counts.get("trailing_stop", 0),
                    "time_exits": exit_counts.get("time_exit", 0),
                }
            )

    # Convert to DataFrame and sort by performance
    results_df = pd.DataFrame(all_results)

    # Sort by multiple criteria
    results_df["score"] = (
        results_df["win_rate"] * 0.3
        + results_df["avg_pnl_pct"] * 0.4
        + results_df["sharpe"] * 0.3
    )
    results_df = results_df.sort_values("score", ascending=False)

    print("\n" + "=" * 80)
    print("TOP 10 PARAMETER COMBINATIONS")
    print("=" * 80)

    top_10 = results_df.head(10)

    for i, row in enumerate(top_10.itertuples(), 1):
        print(f"\n#{i} COMBINATION:")
        print(f"  Stop Loss: {row.stop_loss:.1f}%")
        print(f"  Take Profit: {row.take_profit:.1f}%")
        print(f"  Trailing Stop: {row.trailing_stop:.1f}%")
        print(f"  ---")
        print(f"  Win Rate: {row.win_rate:.1f}%")
        print(f"  Avg PnL: {row.avg_pnl_pct:.2f}%")
        print(f"  Total PnL: {row.total_pnl_pct:.1f}%")
        print(f"  Sharpe: {row.sharpe:.2f}")
        print(
            f"  Exit Distribution: SL:{row.stop_losses} TP:{row.take_profits} TS:{row.trailing_stops} Time:{row.time_exits}"
        )

    # Compare with current settings (estimated from actual trades)
    print("\n" + "=" * 80)
    print("COMPARISON WITH CURRENT SETTINGS")
    print("=" * 80)

    current_settings = results_df[
        (results_df["stop_loss"].between(4, 4.5)) & (results_df["take_profit"] > 5)
    ]

    if not current_settings.empty:
        current = current_settings.iloc[0]
        best = top_10.iloc[0]

        print(f"\nCurrent (estimated ~4.2% SL):")
        print(f"  Win Rate: {current.win_rate:.1f}%")
        print(f"  Avg PnL: {current.avg_pnl_pct:.2f}%")

        print(f"\nBest Found:")
        print(
            f"  Win Rate: {best.win_rate:.1f}% ({best.win_rate - current.win_rate:+.1f}%)"
        )
        print(
            f"  Avg PnL: {best.avg_pnl_pct:.2f}% ({best.avg_pnl_pct - current.avg_pnl_pct:+.2f}%)"
        )

        print(f"\n💡 POTENTIAL IMPROVEMENT:")
        print(f"  Win Rate: {best.win_rate / current.win_rate:.1f}x better")
        print(
            f"  Profitability: {abs(best.avg_pnl_pct / current.avg_pnl_pct):.1f}x better"
        )

    # Analyze patterns in best performers
    print("\n" + "=" * 80)
    print("PATTERNS IN TOP PERFORMERS")
    print("=" * 80)

    print(
        f"\nOptimal Stop Loss Range: {top_10['stop_loss'].min():.1f}% - {top_10['stop_loss'].max():.1f}%"
    )
    print(
        f"Optimal Take Profit Range: {top_10['take_profit'].min():.1f}% - {top_10['take_profit'].max():.1f}%"
    )
    print(
        f"Optimal Trailing Stop Range: {top_10['trailing_stop'].min():.1f}% - {top_10['trailing_stop'].max():.1f}%"
    )

    print("\n🎯 RECOMMENDED SETTINGS:")
    best = top_10.iloc[0]
    print(f"  Stop Loss: {best.stop_loss:.1f}%")
    print(f"  Take Profit: {best.take_profit:.1f}%")
    print(f"  Trailing Stop: {best.trailing_stop:.1f}%")
    print(f"\nExpected Performance (based on backtest):")
    print(f"  Win Rate: {best.win_rate:.1f}%")
    print(f"  Average Trade: {best.avg_pnl_pct:+.2f}%")


if __name__ == "__main__":
    main()
