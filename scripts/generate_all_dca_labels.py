#!/usr/bin/env python3
"""
Generate DCA training labels for ALL symbols from historical data.

This script:
1. Gets all available symbols from database
2. Scans historical price data for DCA setup conditions
3. Simulates what would have happened if we entered
4. Labels each setup as WIN/LOSS based on outcome
5. Saves labeled data for ML training
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dotenv import load_dotenv
from loguru import logger
import time

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from src.strategies.dca.detector import DCADetector
from src.strategies.dca.grid import GridCalculator

# Load environment variables
load_dotenv()


class DCALabelGenerator:
    """Generate training labels for DCA strategy."""

    def __init__(self, supabase_client: SupabaseClient):
        """Initialize label generator."""
        self.supabase = supabase_client
        self.detector = DCADetector(supabase_client)
        self.config = self.detector.config
        self.grid_calculator = GridCalculator(self.config)

    def get_all_symbols(self) -> List[str]:
        """Get all symbols with sufficient data from database."""
        try:
            # Get symbols with at least 1000 data points
            result = self.supabase.client.rpc(
                "get_symbols_with_data_count", {"min_count": 1000}
            ).execute()

            if result.data:
                symbols = [row["symbol"] for row in result.data]
                logger.info(f"Found {len(symbols)} symbols with sufficient data")
                return symbols
        except:
            # Fallback: query directly
            result = self.supabase.client.table("price_data").select("symbol").execute()
            if result.data:
                # Get unique symbols
                symbols = list(set([row["symbol"] for row in result.data]))
                logger.info(f"Found {len(symbols)} unique symbols")
                return sorted(symbols)

        return []

    def find_historical_setups(self, symbol: str, lookback_days: int) -> List[Dict]:
        """
        Find all DCA setups in historical data with chunking.
        """
        setups = []
        end_time = datetime.now()
        start_time = end_time - timedelta(days=lookback_days)

        # Process in 12-hour chunks to avoid query limits
        chunk_hours = 12
        current_start = start_time
        all_data = []

        print(f"\n  Fetching data for {symbol} in chunks...")
        while current_start < end_time:
            current_end = min(current_start + timedelta(hours=chunk_hours), end_time)

            # Fetch chunk
            result = (
                self.supabase.client.table("price_data")
                .select("timestamp,symbol,close,high,low,volume")
                .eq("symbol", symbol)
                .gte("timestamp", current_start.isoformat())
                .lt("timestamp", current_end.isoformat())
                .order("timestamp")
                .limit(1000)
                .execute()
            )

            if result.data:
                all_data.extend(result.data)

            current_start = current_end

        if len(all_data) < 100:
            logger.warning(
                f"Insufficient data for {symbol}: only {len(all_data)} records"
            )
            return []

        # Convert to DataFrame
        df = pd.DataFrame(all_data)
        df["timestamp"] = pd.to_datetime(df["timestamp"], format="ISO8601")
        df = df.sort_values("timestamp").reset_index(drop=True)

        # Calculate features
        df["rsi"] = self._calculate_rsi(df["close"])
        df["volume_ma"] = df["volume"].rolling(window=20, min_periods=1).mean()
        df["volume_ratio"] = df["volume"] / df["volume_ma"]

        # Find 4-hour highs
        df["high_4h"] = df["high"].rolling(window=48, min_periods=1).max()

        # Look for setups (5% drops from 4h high)
        drop_threshold = self.config["setup_detection"]["price_drop_threshold"]

        i = 48  # Start after we have enough history
        while i < len(df):
            row = df.iloc[i]

            # Calculate drop from recent high
            drop_pct = ((row["close"] - row["high_4h"]) / row["high_4h"]) * 100

            if drop_pct <= drop_threshold and row["volume_ratio"] > 1.0:
                setup = {
                    "timestamp": row["timestamp"],
                    "symbol": symbol,
                    "setup_price": row["close"],
                    "drop_pct": drop_pct,
                    "rsi": row["rsi"],
                    "volume_ratio": row["volume_ratio"],
                    "high_4h": row["high_4h"],
                    "df_index": i,
                }
                setups.append(setup)

                # Skip ahead 60 periods (5 hours) to avoid overlapping setups
                i += 60
            else:
                i += 1

        return setups

    def simulate_dca_outcome(
        self, setup: Dict, df: pd.DataFrame, ml_confidence: float = 0.6
    ) -> Dict:
        """
        Simulate DCA grid execution and determine outcome.
        """
        # Get grid configuration
        grid = self.grid_calculator.calculate_grid(
            setup_price=setup["setup_price"], ml_confidence=ml_confidence
        )

        # Simulate grid entries
        start_idx = setup["df_index"]
        end_idx = min(start_idx + 72 * 12, len(df))  # 72 hours forward

        if end_idx - start_idx < 24:  # Need at least 24 periods
            return {"outcome": "INSUFFICIENT_DATA", "pnl": 0, "exit_reason": "no_data"}

        # Track grid fills
        grid_fills = []
        total_invested = 0

        # Check each period for grid fills and exits
        for i in range(start_idx, end_idx):
            current_price = df.iloc[i]["close"]
            current_time = df.iloc[i]["timestamp"]
            hours_elapsed = (current_time - setup["timestamp"]).total_seconds() / 3600

            # Check for grid entries (buying on the way down)
            for level in grid["levels"]:
                if current_price <= level["price"] and level not in grid_fills:
                    grid_fills.append(level)
                    total_invested += level["size"]

            # If we have positions, check exit conditions
            if grid_fills:
                avg_price = sum(g["price"] * g["size"] for g in grid_fills) / sum(
                    g["size"] for g in grid_fills
                )
                current_pnl = ((current_price - avg_price) / avg_price) * 100

                # Check take profit (use 10% for now, will be ML-optimized later)
                if current_pnl >= grid["take_profit"]:
                    return {
                        "outcome": "WIN",
                        "pnl": current_pnl,
                        "exit_reason": "take_profit",
                        "exit_price": current_price,
                        "avg_entry": avg_price,
                        "hold_hours": hours_elapsed,
                        "grid_fills": len(grid_fills),
                    }

                # Check stop loss
                if current_pnl <= -grid["stop_loss"]:
                    return {
                        "outcome": "LOSS",
                        "pnl": current_pnl,
                        "exit_reason": "stop_loss",
                        "exit_price": current_price,
                        "avg_entry": avg_price,
                        "hold_hours": hours_elapsed,
                        "grid_fills": len(grid_fills),
                    }

                # Check time exit (72 hours)
                if hours_elapsed >= 72:
                    if current_pnl > 0:
                        return {
                            "outcome": "WIN",
                            "pnl": current_pnl,
                            "exit_reason": "time_exit_profit",
                            "exit_price": current_price,
                            "avg_entry": avg_price,
                            "hold_hours": 72,
                            "grid_fills": len(grid_fills),
                        }
                    elif current_pnl < -2:  # More than 2% loss
                        return {
                            "outcome": "LOSS",
                            "pnl": current_pnl,
                            "exit_reason": "time_exit_loss",
                            "exit_price": current_price,
                            "avg_entry": avg_price,
                            "hold_hours": 72,
                            "grid_fills": len(grid_fills),
                        }
                    else:
                        return {
                            "outcome": "BREAKEVEN",
                            "pnl": current_pnl,
                            "exit_reason": "time_exit_flat",
                            "exit_price": current_price,
                            "avg_entry": avg_price,
                            "hold_hours": 72,
                            "grid_fills": len(grid_fills),
                        }

        # No grid fills = setup expired
        if not grid_fills:
            return {"outcome": "EXPIRED", "pnl": 0, "exit_reason": "no_fills"}

        # Shouldn't reach here, but just in case
        return {"outcome": "UNKNOWN", "pnl": 0, "exit_reason": "unknown"}

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)  # Default to neutral

    def generate_labels_for_symbol(
        self, symbol: str, lookback_days: int = 180
    ) -> pd.DataFrame:
        """Generate labels for a single symbol."""
        print(f"\n{'='*60}")
        print(f"Processing {symbol}")
        print(f"{'='*60}")

        # Find historical setups
        setups = self.find_historical_setups(symbol, lookback_days)

        if not setups:
            print(f"  No setups found for {symbol}")
            return pd.DataFrame()

        print(f"  Found {len(setups)} potential setups")

        # Get full data for simulation
        end_time = datetime.now()
        start_time = end_time - timedelta(
            days=lookback_days + 7
        )  # Extra week for simulation

        # Fetch all data (with chunking)
        chunk_hours = 12
        current_start = start_time
        all_data = []

        while current_start < end_time:
            current_end = min(current_start + timedelta(hours=chunk_hours), end_time)

            result = (
                self.supabase.client.table("price_data")
                .select("timestamp,close,high,low,volume")
                .eq("symbol", symbol)
                .gte("timestamp", current_start.isoformat())
                .lt("timestamp", current_end.isoformat())
                .order("timestamp")
                .limit(1000)
                .execute()
            )

            if result.data:
                all_data.extend(result.data)

            current_start = current_end

        if not all_data:
            print(f"  No price data for {symbol}")
            return pd.DataFrame()

        df = pd.DataFrame(all_data)
        df["timestamp"] = pd.to_datetime(df["timestamp"], format="ISO8601")
        df = df.sort_values("timestamp").reset_index(drop=True)

        # Simulate each setup
        results = []
        for setup in setups:
            # Find the setup point in our dataframe
            setup_time = setup["timestamp"]
            df_at_setup = df[df["timestamp"] >= setup_time].reset_index(drop=True)

            if len(df_at_setup) < 100:
                continue

            setup["df_index"] = 0  # Reset index for simulation
            outcome = self.simulate_dca_outcome(setup, df_at_setup)

            # Combine setup and outcome
            result = {
                "symbol": symbol,
                "setup_time": setup_time,
                "setup_price": setup["setup_price"],
                "drop_pct": setup["drop_pct"],
                "rsi": setup["rsi"],
                "volume_ratio": setup["volume_ratio"],
                "high_4h": setup["high_4h"],
                "label": outcome["outcome"],
                "pnl_pct": outcome["pnl"],
                "exit_reason": outcome.get("exit_reason", "unknown"),
            }

            # Add additional outcome details if available
            for key in ["exit_price", "avg_entry", "hold_hours", "grid_fills"]:
                if key in outcome:
                    result[key] = outcome[key]

            results.append(result)

        return pd.DataFrame(results)

    def generate_labels(
        self, symbols: Optional[List[str]] = None, lookback_days: int = 180
    ) -> pd.DataFrame:
        """
        Generate DCA labels from historical data.

        Args:
            symbols: List of symbols to process (None = all available)
            lookback_days: How many days of history to scan

        Returns:
            DataFrame with labeled setups
        """
        if symbols is None:
            symbols = self.get_all_symbols()

        all_results = []
        total_symbols = len(symbols)

        for idx, symbol in enumerate(symbols, 1):
            print(f"\nProgress: {idx}/{total_symbols} symbols")

            try:
                df = self.generate_labels_for_symbol(symbol, lookback_days)
                if not df.empty:
                    all_results.append(df)

                    # Print summary for this symbol
                    wins = len(df[df["label"] == "WIN"])
                    losses = len(df[df["label"] == "LOSS"])
                    breakeven = len(df[df["label"] == "BREAKEVEN"])

                    if wins + losses > 0:
                        win_rate = wins / (wins + losses)
                        print(
                            f"  Results: {wins} wins, {losses} losses, {breakeven} breakeven"
                        )
                        print(f"  Win rate: {win_rate:.1%}")

                        if wins > 0:
                            avg_win = df[df["label"] == "WIN"]["pnl_pct"].mean()
                            print(f"  Avg win: {avg_win:.2f}%")
                        if losses > 0:
                            avg_loss = df[df["label"] == "LOSS"]["pnl_pct"].mean()
                            print(f"  Avg loss: {avg_loss:.2f}%")

                # Small delay to avoid rate limits
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                continue

        if all_results:
            return pd.concat(all_results, ignore_index=True)
        else:
            return pd.DataFrame()

    def save_labels(
        self, df: pd.DataFrame, filename: str = "dca_training_labels_all.csv"
    ):
        """Save labels to CSV file."""
        output_dir = Path("data/training")
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / filename
        df.to_csv(output_path, index=False)
        print(f"\nSaved {len(df)} labels to {output_path}")

        # Print overall summary
        print("\n" + "=" * 60)
        print("OVERALL SUMMARY")
        print("=" * 60)

        # Group by symbol
        symbol_summary = (
            df.groupby("symbol")
            .agg({"label": "count", "pnl_pct": "mean"})
            .rename(columns={"label": "setups", "pnl_pct": "avg_pnl"})
        )

        print("\nSetups by symbol:")
        print(symbol_summary.sort_values("setups", ascending=False).head(10))

        # Overall statistics
        total_setups = len(df)
        wins = len(df[df["label"] == "WIN"])
        losses = len(df[df["label"] == "LOSS"])
        breakeven = len(df[df["label"] == "BREAKEVEN"])

        print(f"\nTotal setups: {total_setups}")
        print(f"Wins: {wins} ({wins/total_setups:.1%})")
        print(f"Losses: {losses} ({losses/total_setups:.1%})")
        print(f"Breakeven: {breakeven} ({breakeven/total_setups:.1%})")

        if wins + losses > 0:
            win_rate = wins / (wins + losses)
            print(f"\nOverall win rate: {win_rate:.1%}")

            if wins > 0:
                avg_win = df[df["label"] == "WIN"]["pnl_pct"].mean()
                print(f"Average win: {avg_win:.2f}%")
            if losses > 0:
                avg_loss = df[df["label"] == "LOSS"]["pnl_pct"].mean()
                print(f"Average loss: {avg_loss:.2f}%")

            # Expected value
            if wins > 0 and losses > 0:
                ev = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)
                print(f"Expected value per trade: {ev:.2f}%")


def main():
    """Generate DCA training labels for all symbols."""
    print("=" * 80)
    print("DCA TRAINING LABEL GENERATOR - ALL SYMBOLS")
    print("=" * 80)

    # Initialize
    supabase = SupabaseClient()
    generator = DCALabelGenerator(supabase)

    # Get all available symbols
    symbols = generator.get_all_symbols()

    if not symbols:
        print("No symbols found!")
        return

    print(f"\nFound {len(symbols)} symbols to process")
    print(f"Lookback period: 180 days")
    print("-" * 40)

    # For initial testing, just do top 20 symbols
    # Remove this limit when ready for full run
    symbols = symbols[:20]  # Start with top 20 for testing
    print(f"Processing first {len(symbols)} symbols for testing...")

    # Generate labels
    df = generator.generate_labels(symbols, lookback_days=180)

    # Save results
    if len(df) > 0:
        generator.save_labels(df)

        # Optionally save to database
        print("\nSaving setups to database...")
        saved_count = 0
        for _, row in df.iterrows():
            if row["label"] in ["WIN", "LOSS"]:
                setup_data = {
                    "strategy_name": "DCA",
                    "symbol": row["symbol"],
                    "detected_at": row["setup_time"].isoformat(),
                    "setup_price": float(row["setup_price"]),
                    "setup_data": {
                        "drop_pct": float(row["drop_pct"]),
                        "rsi": float(row["rsi"]),
                        "volume_ratio": float(row["volume_ratio"]),
                        "high_4h": float(row["high_4h"]),
                    },
                    "outcome": row["label"],
                    "pnl": float(row["pnl_pct"]),
                }

                try:
                    result = (
                        supabase.client.table("strategy_setups")
                        .insert(setup_data)
                        .execute()
                    )
                    if result.data:
                        saved_count += 1
                except Exception as e:
                    logger.error(f"Error saving setup: {e}")

        print(f"Saved {saved_count} setups to database")
    else:
        print("No setups found!")

    print("\n" + "=" * 80)
    print("LABEL GENERATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
