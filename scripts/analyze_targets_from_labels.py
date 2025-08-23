#!/usr/bin/env python3
"""
Analyze optimal targets using our existing labeled data.
"""

import pandas as pd
import numpy as np


def analyze_targets():
    """Analyze what targets would have been optimal."""

    print("=" * 80)
    print("ANALYZING OPTIMAL TARGETS FROM EXISTING DATA")
    print("=" * 80)

    # Load our labeled data
    df = pd.read_csv("data/dca_training_labels.csv")

    print(f"\nTotal setups analyzed: {len(df)}")
    print(f"Symbol: {df['symbol'].iloc[0]}")

    # Analyze the P&L distribution
    print("\n" + "=" * 80)
    print("ACTUAL P&L DISTRIBUTION")
    print("-" * 40)

    wins = df[df["label"] == "WIN"]
    losses = df[df["label"] == "LOSS"]
    breakeven = df[df["label"] == "BREAKEVEN"]

    print(f"\nWins: {len(wins)} setups")
    if len(wins) > 0:
        print(f"  Average win: {wins['pnl_pct'].mean():.2f}%")
        print(f"  Max win: {wins['pnl_pct'].max():.2f}%")
        print(f"  Min win: {wins['pnl_pct'].min():.2f}%")

        # How many would hit different targets?
        for target in [3, 5, 7, 10]:
            hit_target = (wins["pnl_pct"] >= target).sum()
            pct = (hit_target / len(df)) * 100
            print(f"  Would hit {target}% target: {hit_target}/{len(df)} ({pct:.1f}% of all setups)")

    print(f"\nLosses: {len(losses)} setups")
    if len(losses) > 0:
        print(f"  Average loss: {losses['pnl_pct'].mean():.2f}%")
        print(f"  Max loss: {losses['pnl_pct'].max():.2f}%")
        print(f"  Min loss: {losses['pnl_pct'].min():.2f}%")

    print(f"\nBreakeven: {len(breakeven)} setups")
    if len(breakeven) > 0:
        print(f"  Average P&L: {breakeven['pnl_pct'].mean():.2f}%")
        print(f"  Range: {breakeven['pnl_pct'].min():.2f}% to {breakeven['pnl_pct'].max():.2f}%")

    # Analyze by drop size
    print("\n" + "=" * 80)
    print("ANALYSIS BY DROP SIZE")
    print("-" * 40)

    df["drop_bucket"] = pd.cut(
        df["drop_pct"],
        bins=[-100, -10, -7, -5, 0],
        labels=["Huge (>10%)", "Large (7-10%)", "Medium (5-7%)", "Small (<5%)"],
    )

    for bucket in df["drop_bucket"].unique():
        if pd.notna(bucket):
            subset = df[df["drop_bucket"] == bucket]
            if len(subset) > 0:
                win_rate = (subset["label"] == "WIN").mean() * 100
                avg_pnl = subset["pnl_pct"].mean()
                print(f"\n{bucket} drops: {len(subset)} setups")
                print(f"  Win rate: {win_rate:.1f}%")
                print(f"  Avg P&L: {avg_pnl:.2f}%")

    # Analyze by RSI
    print("\n" + "=" * 80)
    print("ANALYSIS BY RSI")
    print("-" * 40)

    df["rsi_bucket"] = pd.cut(
        df["rsi"],
        bins=[0, 30, 50, 70, 100],
        labels=["Oversold (<30)", "Low (30-50)", "Neutral (50-70)", "High (>70)"],
    )

    for bucket in df["rsi_bucket"].unique():
        if pd.notna(bucket):
            subset = df[df["rsi_bucket"] == bucket]
            if len(subset) > 0:
                win_rate = (subset["label"] == "WIN").mean() * 100
                avg_pnl = subset["pnl_pct"].mean()
                print(f"\n{bucket} RSI: {len(subset)} setups")
                print(f"  Win rate: {win_rate:.1f}%")
                print(f"  Avg P&L: {avg_pnl:.2f}%")

    # Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS FOR BTC")
    print("=" * 80)

    # Calculate what would have been optimal
    all_pnls = df["pnl_pct"].values

    # Simulate different take profit levels
    print("\nSimulating different take profit levels:")
    for tp in [3, 5, 7, 10]:
        # Count how many would hit this target
        would_hit = 0
        total_pnl = 0

        for pnl in all_pnls:
            if pnl >= tp:
                would_hit += 1
                total_pnl += tp  # Lock in profit at target
            elif pnl < -8:  # Stop loss
                total_pnl += -8
            else:
                total_pnl += pnl  # Take actual P&L

        avg_pnl = total_pnl / len(all_pnls)
        hit_rate = (would_hit / len(all_pnls)) * 100

        print(f"\n{tp}% Take Profit:")
        print(f"  Would hit: {hit_rate:.1f}% of setups")
        print(f"  Expected value: {avg_pnl:.2f}% per trade")

    print("\n" + "=" * 80)
    print("ML OPTIMIZATION STRATEGY")
    print("=" * 80)

    print(
        """
    Based on this analysis, ML should:

    1. CLASSIFY SETUPS INTO TIERS:
       - Tier A: High confidence → 7-10% take profit
       - Tier B: Medium confidence → 5% take profit
       - Tier C: Low confidence → 3% take profit or skip

    2. FEATURES TO CONSIDER:
       - Drop magnitude (bigger drops = bigger bounces?)
       - RSI level (more oversold = stronger bounce?)
       - Volume surge (panic selling = reversal likely?)
       - Time of day/week (weekend drops different?)
       - Market regime (bull vs bear market)
       - Support levels nearby

    3. DYNAMIC ADJUSTMENTS:
       - BTC/ETH: Conservative 3-5% targets
       - Mid-caps: Moderate 5-7% targets
       - Small-caps: Aggressive 7-10% targets

    4. MULTI-OUTPUT MODEL:
       Instead of just WIN/LOSS, predict:
       - Optimal take profit (3%, 5%, 7%, 10%)
       - Optimal stop loss (-5%, -8%, -10%)
       - Optimal hold time (24h, 48h, 72h)
       - Position size multiplier (0.5x, 1x, 1.5x)
    """
    )


if __name__ == "__main__":
    analyze_targets()
