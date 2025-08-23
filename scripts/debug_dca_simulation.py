#!/usr/bin/env python3
"""
Debug DCA simulation to understand why we have no losses.
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient

# Load environment variables
load_dotenv()


def analyze_dca_simulation():
    """Analyze a few specific DCA setups to understand the simulation."""

    print("=" * 80)
    print("DCA SIMULATION DEBUGGER")
    print("=" * 80)

    # Load the generated labels
    labels_df = pd.read_csv("data/dca_training_labels.csv")

    print(f"\nTotal setups: {len(labels_df)}")
    print(f"Wins: {(labels_df['label'] == 'WIN').sum()}")
    print(f"Losses: {(labels_df['label'] == 'LOSS').sum()}")
    print(f"Breakeven: {(labels_df['label'] == 'BREAKEVEN').sum()}")
    print(f"Skipped: {(labels_df['label'] == 'SKIP').sum()}")

    # Analyze the data
    print("\n" + "=" * 80)
    print("ANALYSIS OF SETUPS")
    print("=" * 80)

    # Check drop percentages
    print(f"\nDrop percentages:")
    print(f"  Min: {labels_df['drop_pct'].min():.2f}%")
    print(f"  Max: {labels_df['drop_pct'].max():.2f}%")
    print(f"  Mean: {labels_df['drop_pct'].mean():.2f}%")

    # Check max drawdowns
    print(f"\nMax drawdowns from entry:")
    print(f"  Min: {labels_df['max_drawdown'].min():.2f}%")
    print(f"  Max: {labels_df['max_drawdown'].max():.2f}%")
    print(f"  Mean: {labels_df['max_drawdown'].mean():.2f}%")

    # Find setups with worst drawdowns
    worst_drawdowns = labels_df.nsmallest(5, "max_drawdown")
    print(f"\nWorst 5 drawdowns:")
    for _, row in worst_drawdowns.iterrows():
        print(
            f"  {row['symbol']} on {row['setup_time'][:10]}: {row['max_drawdown']:.2f}% -> {row['label']} ({row['pnl_pct']:.2f}%)"
        )

    # Check if any came close to stop loss
    stop_loss_threshold = -8.0
    close_to_stop = labels_df[labels_df["max_drawdown"] < -7.0]
    print(f"\nSetups that came within 1% of stop loss (-8%): {len(close_to_stop)}")

    if len(close_to_stop) > 0:
        print("Examples:")
        for _, row in close_to_stop.head(3).iterrows():
            print(f"  {row['symbol']}: drawdown {row['max_drawdown']:.2f}%, outcome: {row['label']}")

    # Let's manually check one setup
    print("\n" + "=" * 80)
    print("MANUAL CHECK OF A SPECIFIC SETUP")
    print("=" * 80)

    # Get a setup with significant drawdown
    test_setup = (
        labels_df[labels_df["max_drawdown"] < -5].iloc[0] if any(labels_df["max_drawdown"] < -5) else labels_df.iloc[0]
    )

    print(f"\nChecking: {test_setup['symbol']} on {test_setup['setup_time'][:10]}")
    print(f"  Setup price: ${test_setup['setup_price']:.2f}")
    print(f"  Drop from high: {test_setup['drop_pct']:.2f}%")
    print(f"  Max drawdown: {test_setup['max_drawdown']:.2f}%")
    print(f"  Outcome: {test_setup['label']} ({test_setup['pnl_pct']:.2f}%)")

    # Fetch the actual price data to verify
    supabase = SupabaseClient()

    setup_time = pd.to_datetime(test_setup["setup_time"])
    end_time = setup_time + timedelta(hours=72)

    result = (
        supabase.client.table("price_data")
        .select("timestamp, price")
        .eq("symbol", test_setup["symbol"])
        .gte("timestamp", setup_time.isoformat())
        .lte("timestamp", end_time.isoformat())
        .order("timestamp")
        .limit(5000)
        .execute()
    )

    if result.data:
        df = pd.DataFrame(result.data)
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        print(f"\nPrice movement after setup:")
        print(f"  Lowest price: ${df['price'].min():.2f}")
        print(f"  Highest price: ${df['price'].max():.2f}")

        # Simulate the grid
        entry_price = test_setup["setup_price"]
        grid_levels = []
        for i in range(5):
            level = entry_price * (0.99**i)
            grid_levels.append(level)
            hit = "✓" if df["price"].min() <= level else "✗"
            print(f"  Grid level {i+1}: ${level:.2f} {hit}")

        # Calculate average entry
        filled_levels = [level for level in grid_levels if df["price"].min() <= level]
        if filled_levels:
            avg_entry = np.mean(filled_levels)
            print(f"\nAverage entry: ${avg_entry:.2f}")
            print(f"Take profit target: ${avg_entry * 1.10:.2f}")
            print(f"Stop loss: ${avg_entry * 0.92:.2f}")

            # Check if stop loss should have triggered
            if df["price"].min() < avg_entry * 0.92:
                print(f"⚠️  Price went below stop loss! Min: ${df['price'].min():.2f}")

                # Find when it would have hit stop loss
                for _, row in df.iterrows():
                    if row["price"] <= avg_entry * 0.92:
                        print(f"  Would hit stop loss at {row['timestamp']}")
                        break

    # Check the distribution of PnL
    print("\n" + "=" * 80)
    print("P&L DISTRIBUTION")
    print("=" * 80)

    pnl_counts = labels_df["pnl_pct"].value_counts().sort_index()
    print("\nP&L values:")
    for pnl, count in pnl_counts.items():
        if count > 10:  # Only show significant counts
            print(f"  {pnl:+.1f}%: {count} setups")


if __name__ == "__main__":
    analyze_dca_simulation()
