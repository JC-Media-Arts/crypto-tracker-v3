#!/usr/bin/env python3
"""
Analyze optimal take profit and stop loss levels by market cap.
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


def analyze_price_movements():
    """Analyze typical price movements after 5% drops for different coins."""

    print("=" * 80)
    print("OPTIMAL TARGET ANALYSIS BY MARKET CAP")
    print("=" * 80)

    supabase = SupabaseClient()

    # Define coin tiers by market cap/volatility
    coin_tiers = {
        "Large Cap (Stable)": ["BTC", "ETH"],
        "Mid Cap (Moderate)": ["SOL", "ADA", "DOT", "AVAX", "LINK"],
        "Small Cap (Volatile)": ["UNI", "ATOM", "NEAR"],
    }

    results = {}

    for tier, symbols in coin_tiers.items():
        print(f"\n{tier}:")
        print("-" * 40)

        tier_results = []

        for symbol in symbols:
            # Get historical data
            end_date = datetime.now() - timedelta(days=1)
            start_date = end_date - timedelta(days=90)  # 90 days for faster analysis

            result = (
                supabase.client.table("price_data")
                .select("timestamp, price")
                .eq("symbol", symbol)
                .gte("timestamp", start_date.isoformat())
                .lte("timestamp", end_date.isoformat())
                .order("timestamp")
                .limit(10000)
                .execute()
            )

            if not result.data or len(result.data) < 1000:
                continue

            df = pd.DataFrame(result.data)
            df["timestamp"] = pd.to_datetime(df["timestamp"], format="ISO8601")
            df = df.set_index("timestamp")

            # Find all 5% drops
            drops = []
            window_size = 240  # 4 hours

            for i in range(window_size, len(df) - 4320):  # Leave room for 72h forward
                high_4h = df["price"].iloc[max(0, i - window_size) : i].max()
                current_price = df["price"].iloc[i]
                drop_pct = ((current_price - high_4h) / high_4h) * 100

                if drop_pct <= -5.0:
                    # Analyze what happens next
                    future_prices = df["price"].iloc[
                        i : min(i + 4320, len(df))
                    ]  # Next 72 hours

                    if len(future_prices) > 100:
                        max_bounce = (
                            (future_prices.max() - current_price) / current_price
                        ) * 100
                        min_drop = (
                            (future_prices.min() - current_price) / current_price
                        ) * 100
                        final_move = (
                            (future_prices.iloc[-1] - current_price) / current_price
                        ) * 100

                        # Time to reach different targets
                        time_to_5pct = None
                        time_to_7pct = None
                        time_to_10pct = None

                        for j, price in enumerate(future_prices):
                            pct_move = ((price - current_price) / current_price) * 100
                            hours = j / 60  # Convert minutes to hours

                            if pct_move >= 5 and time_to_5pct is None:
                                time_to_5pct = hours
                            if pct_move >= 7 and time_to_7pct is None:
                                time_to_7pct = hours
                            if pct_move >= 10 and time_to_10pct is None:
                                time_to_10pct = hours

                        drops.append(
                            {
                                "symbol": symbol,
                                "drop_size": drop_pct,
                                "max_bounce": max_bounce,
                                "min_additional_drop": min_drop,
                                "final_72h_move": final_move,
                                "hit_5pct": time_to_5pct is not None,
                                "hit_7pct": time_to_7pct is not None,
                                "hit_10pct": time_to_10pct is not None,
                                "time_to_5pct": time_to_5pct,
                                "time_to_7pct": time_to_7pct,
                                "time_to_10pct": time_to_10pct,
                            }
                        )

                    # Skip ahead to avoid overlaps
                    i += 720  # Skip 12 hours

            if drops:
                drop_df = pd.DataFrame(drops)

                # Calculate statistics
                stats = {
                    "symbol": symbol,
                    "setups": len(drop_df),
                    "avg_max_bounce": drop_df["max_bounce"].mean(),
                    "avg_additional_drop": drop_df["min_additional_drop"].mean(),
                    "pct_hit_5": (drop_df["hit_5pct"].sum() / len(drop_df)) * 100,
                    "pct_hit_7": (drop_df["hit_7pct"].sum() / len(drop_df)) * 100,
                    "pct_hit_10": (drop_df["hit_10pct"].sum() / len(drop_df)) * 100,
                    "avg_time_to_5": (
                        drop_df["time_to_5pct"].dropna().mean()
                        if any(drop_df["hit_5pct"])
                        else None
                    ),
                    "avg_time_to_7": (
                        drop_df["time_to_7pct"].dropna().mean()
                        if any(drop_df["hit_7pct"])
                        else None
                    ),
                    "avg_time_to_10": (
                        drop_df["time_to_10pct"].dropna().mean()
                        if any(drop_df["hit_10pct"])
                        else None
                    ),
                }

                tier_results.append(stats)

                print(f"\n{symbol}:")
                print(f"  Setups found: {stats['setups']}")
                print(f"  Avg max bounce: {stats['avg_max_bounce']:.2f}%")
                print(f"  Avg additional drop: {stats['avg_additional_drop']:.2f}%")
                print(f"  Hit 5% profit: {stats['pct_hit_5']:.1f}% of setups")
                print(f"  Hit 7% profit: {stats['pct_hit_7']:.1f}% of setups")
                print(f"  Hit 10% profit: {stats['pct_hit_10']:.1f}% of setups")

                if stats["avg_time_to_5"]:
                    print(f"  Avg time to 5%: {stats['avg_time_to_5']:.1f} hours")
                if stats["avg_time_to_7"]:
                    print(f"  Avg time to 7%: {stats['avg_time_to_7']:.1f} hours")
                if stats["avg_time_to_10"]:
                    print(f"  Avg time to 10%: {stats['avg_time_to_10']:.1f} hours")

        if tier_results:
            results[tier] = pd.DataFrame(tier_results)

    # Summary recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDED TARGETS BY TIER")
    print("=" * 80)

    for tier, df in results.items():
        if len(df) > 0:
            avg_5_hit = df["pct_hit_5"].mean()
            avg_7_hit = df["pct_hit_7"].mean()
            avg_10_hit = df["pct_hit_10"].mean()
            avg_drop = df["avg_additional_drop"].mean()

            print(f"\n{tier}:")
            print(f"  5% Take Profit: {avg_5_hit:.1f}% success rate")
            print(f"  7% Take Profit: {avg_7_hit:.1f}% success rate")
            print(f"  10% Take Profit: {avg_10_hit:.1f}% success rate")
            print(f"  Avg additional drop: {avg_drop:.1f}%")

            # Recommendation
            if avg_10_hit > 40:
                recommended_tp = 10
            elif avg_7_hit > 50:
                recommended_tp = 7
            else:
                recommended_tp = 5

            recommended_sl = abs(avg_drop) + 3  # Add 3% buffer

            print(f"\n  📊 RECOMMENDATION:")
            print(f"  Take Profit: {recommended_tp}%")
            print(f"  Stop Loss: -{recommended_sl:.0f}%")

    print("\n" + "=" * 80)
    print("ML OPTIMIZATION POTENTIAL")
    print("=" * 80)

    print(
        """
    YES! ML can definitely help optimize these parameters:

    1. DYNAMIC TAKE PROFIT:
       - Train on features: volatility, market cap, volume, RSI
       - Predict: optimal take profit for each setup
       - Output: 5%, 7%, or 10% based on conditions

    2. ADAPTIVE STOP LOSS:
       - Consider: support levels, volatility, market regime
       - Predict: likely max drawdown
       - Output: tighter or wider stop based on risk

    3. POSITION SIZING:
       - High confidence + stable coin = larger position
       - Low confidence + volatile coin = smaller position

    4. TIME-BASED EXITS:
       - ML can predict optimal hold time
       - Some setups recover quickly, others need more time

    The ML model would learn patterns like:
    - BTC rarely bounces 10% → use 5-7% targets
    - Small caps in bull markets → can use 10-15% targets
    - High RSI oversold → likely to bounce more
    - Strong support nearby → tighter stop loss safe
    """
    )


if __name__ == "__main__":
    analyze_price_movements()
