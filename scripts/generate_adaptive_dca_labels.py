#!/usr/bin/env python3
"""
Generate DCA labels with adaptive thresholds based on market cap tiers.
Skips large caps (BTC, ETH) due to poor DCA performance in bull markets.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from dateutil import tz
import pandas as pd
from typing import List, Dict, Optional

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from src.strategies.dca.detector import DCADetector
from src.strategies.dca.grid import GridCalculator
from loguru import logger


class AdaptiveDCALabelGenerator:
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.detector = DCADetector(supabase_client)
        self.config = self.detector.config
        self.grid_calculator = GridCalculator(self.config)

        # Define market cap tiers and thresholds
        self.market_tiers = {
            "skip": {  # Skip these - DCA doesn't work well
                "symbols": ["BTC", "ETH"],
                "threshold": None,
                "reason": "Too stable for DCA in bull market",
            },
            "large_cap": {  # Other large caps
                "symbols": ["SOL", "BNB", "XRP", "ADA", "AVAX", "DOGE", "DOT", "POL"],
                "threshold": 5.0,  # 5% threshold
                "take_profit": 10.0,
                "stop_loss": -8.0,
            },
            "mid_cap": {
                "symbols": [
                    "LINK",
                    "TON",
                    "SHIB",
                    "TRX",
                    "UNI",
                    "ATOM",
                    "BCH",
                    "APT",
                    "NEAR",
                    "ICP",
                    "ARB",
                    "OP",
                    "AAVE",
                    "CRV",
                    "MKR",
                    "LDO",
                    "SUSHI",
                    "COMP",
                    "SNX",
                    "BAL",
                    "INJ",
                    "SEI",
                    "PENDLE",
                    "BLUR",
                    "ENS",
                    "GRT",
                    "RENDER",
                    "FET",
                    "RPL",
                    "SAND",
                    "FIL",
                    "RUNE",
                    "IMX",
                    "FLOW",
                    "MANA",
                    "AXS",
                    "CHZ",
                    "GALA",
                    "LRC",
                    "OCEAN",
                    "QNT",
                    "ALGO",
                    "XLM",
                    "XMR",
                    "ZEC",
                    "DASH",
                    "HBAR",
                    "VET",
                    "THETA",
                    "EOS",
                    "KSM",
                    "STX",
                    "KAS",
                    "TIA",
                    "JTO",
                    "JUP",
                    "PYTH",
                    "DYM",
                    "STRK",
                    "ALT",
                ],
                "threshold": 5.0,  # 5% threshold (better win rate)
                "take_profit": 10.0,
                "stop_loss": -8.0,
            },
            "small_cap": {  # Memecoins and small caps
                "symbols": [
                    "PEPE",
                    "WIF",
                    "BONK",
                    "FLOKI",
                    "MEME",
                    "POPCAT",
                    "MEW",
                    "TURBO",
                    "NEIRO",
                    "PNUT",
                    "GOAT",
                    "ACT",
                    "TRUMP",
                    "FARTCOIN",
                    "MOG",
                    "PONKE",
                    "TREMP",
                    "BRETT",
                    "GIGA",
                    "HIPPO",
                    "PORTAL",
                    "BEAM",
                    "MASK",
                    "API3",
                    "ANKR",
                    "CTSI",
                    "YFI",
                    "AUDIO",
                    "ENJ",
                ],
                "threshold": 3.0,  # 3% threshold (more setups, still good win rate)
                "take_profit": 15.0,  # Higher TP for volatile coins
                "stop_loss": -10.0,
            },
        }

    def get_tier_for_symbol(self, symbol: str) -> Optional[Dict]:
        """Get the tier configuration for a symbol."""
        for tier_name, tier_config in self.market_tiers.items():
            if symbol in tier_config["symbols"]:
                return tier_config
        return None

    def fetch_ohlc_data(self, symbol: str, lookback_days: int):
        """Fetch OHLC data with chunking for large datasets."""
        end_time = datetime.now(tz.UTC)
        start_time = end_time - timedelta(days=lookback_days)

        all_data = []
        current_start = start_time
        chunk_days = 7  # Fetch 7 days at a time

        while current_start < end_time:
            current_end = min(current_start + timedelta(days=chunk_days), end_time)

            result = (
                self.supabase.client.table("ohlc_data")
                .select("timestamp,open,high,low,close,volume,trades")
                .eq("symbol", symbol)
                .eq("timeframe", "15m")
                .gte("timestamp", current_start.isoformat())
                .lt("timestamp", current_end.isoformat())
                .order("timestamp")
                .execute()
            )

            if result.data:
                all_data.extend(result.data)

            current_start = current_end

        if all_data:
            df = pd.DataFrame(all_data)
            df["timestamp"] = pd.to_datetime(df["timestamp"], format="ISO8601")
            df = df.sort_values("timestamp").reset_index(drop=True)
            return df
        return pd.DataFrame()

    def find_dca_setups(
        self, symbol: str, df: pd.DataFrame, threshold: float
    ) -> List[Dict]:
        """Find DCA setups with given threshold."""
        if df.empty or len(df) < 48:
            return []

        setups = []

        # Calculate indicators
        df["volume_ma"] = df["volume"].rolling(window=96, min_periods=1).mean()
        df["volume_ratio"] = df["volume"] / df["volume_ma"]
        df["high_4h"] = (
            df["high"].rolling(window=16, min_periods=1).max()
        )  # 16 * 15min = 4 hours

        i = 48  # Start after we have enough history
        while i < len(df):
            row = df.iloc[i]

            # Calculate drop from 4h high
            if pd.notna(row["high_4h"]) and row["high_4h"] > 0:
                drop_pct = ((row["close"] - row["high_4h"]) / row["high_4h"]) * 100

                if drop_pct <= -threshold:
                    setup = {
                        "symbol": symbol,
                        "timestamp": row["timestamp"],
                        "setup_price": row["close"],
                        "high_4h": row["high_4h"],
                        "drop_pct": drop_pct,
                        "volume": row["volume"],
                        "volume_ratio": row["volume_ratio"],
                    }
                    setups.append(setup)

                    # Skip ahead 60 bars (15 hours) to avoid overlapping setups
                    i += 60
                else:
                    i += 1
            else:
                i += 1

        return setups

    def simulate_outcome(
        self, df: pd.DataFrame, setup: Dict, take_profit: float, stop_loss: float
    ) -> Dict:
        """Simulate the outcome of a DCA setup."""
        setup_idx = df[df["timestamp"] == setup["timestamp"]].index[0]

        if setup_idx >= len(df) - 1:
            return {**setup, "outcome": "UNKNOWN", "exit_price": None, "pnl_pct": None}

        # Look forward up to 72 hours (288 * 15min bars)
        max_look_forward = min(288, len(df) - setup_idx - 1)

        setup_price = setup["setup_price"]

        for i in range(1, max_look_forward + 1):
            current_price = df.iloc[setup_idx + i]["close"]

            # Check take profit
            profit_pct = ((current_price - setup_price) / setup_price) * 100
            if profit_pct >= take_profit:
                return {
                    **setup,
                    "outcome": "WIN",
                    "exit_price": current_price,
                    "pnl_pct": profit_pct,
                    "exit_timestamp": df.iloc[setup_idx + i]["timestamp"],
                }

            # Check stop loss
            if profit_pct <= stop_loss:
                return {
                    **setup,
                    "outcome": "LOSS",
                    "exit_price": current_price,
                    "pnl_pct": profit_pct,
                    "exit_timestamp": df.iloc[setup_idx + i]["timestamp"],
                }

        # Check final outcome
        final_price = df.iloc[setup_idx + max_look_forward]["close"]
        final_pct = ((final_price - setup_price) / setup_price) * 100

        return {
            **setup,
            "outcome": (
                "BREAKEVEN"
                if abs(final_pct) < 2
                else ("BREAKEVEN_POS" if final_pct > 0 else "BREAKEVEN_NEG")
            ),
            "exit_price": final_price,
            "pnl_pct": final_pct,
            "exit_timestamp": df.iloc[setup_idx + max_look_forward]["timestamp"],
        }

    def process_symbol(self, symbol: str, lookback_days: int) -> List[Dict]:
        """Process a single symbol and generate labels."""
        tier_config = self.get_tier_for_symbol(symbol)

        if not tier_config or tier_config.get("threshold") is None:
            logger.info(
                f"Skipping {symbol}: {tier_config.get('reason', 'No configuration')}"
            )
            return []

        logger.info(f"\nProcessing {symbol} (threshold: {tier_config['threshold']}%)")

        # Fetch data
        df = self.fetch_ohlc_data(symbol, lookback_days)
        if df.empty:
            logger.warning(f"No data available for {symbol}")
            return []

        # Find setups
        setups = self.find_dca_setups(symbol, df, tier_config["threshold"])
        logger.info(f"Found {len(setups)} setups for {symbol}")

        if not setups:
            return []

        # Simulate outcomes
        labels = []
        for setup in setups:
            label = self.simulate_outcome(
                df, setup, tier_config["take_profit"], tier_config["stop_loss"]
            )
            label["threshold"] = tier_config["threshold"]
            label["take_profit_target"] = tier_config["take_profit"]
            label["stop_loss_target"] = tier_config["stop_loss"]
            labels.append(label)

        # Calculate statistics
        outcomes = [l["outcome"] for l in labels]
        wins = outcomes.count("WIN")
        losses = outcomes.count("LOSS")
        total = len(outcomes)
        win_rate = (wins / total * 100) if total > 0 else 0

        logger.info(
            f"{symbol} Results: {wins} wins, {losses} losses, {win_rate:.1f}% win rate"
        )

        return labels

    def generate_all_labels(self, lookback_days: int = 180) -> pd.DataFrame:
        """Generate labels for all suitable symbols."""
        all_labels = []

        # Get all symbols to process (excluding skipped ones)
        symbols_to_process = []
        for tier_name, tier_config in self.market_tiers.items():
            if tier_name != "skip" and tier_config.get("threshold"):
                symbols_to_process.extend(tier_config["symbols"])

        logger.info(f"Processing {len(symbols_to_process)} symbols (skipping BTC, ETH)")

        # Process each symbol
        for i, symbol in enumerate(symbols_to_process, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"[{i}/{len(symbols_to_process)}] {symbol}")
            logger.info(f"{'='*60}")

            try:
                labels = self.process_symbol(symbol, lookback_days)
                all_labels.extend(labels)
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                continue

        # Convert to DataFrame
        if all_labels:
            df = pd.DataFrame(all_labels)

            # Add additional features
            df["market_cap_tier"] = df["symbol"].apply(
                lambda s: (
                    "large"
                    if s in self.market_tiers["large_cap"]["symbols"]
                    else (
                        "mid"
                        if s in self.market_tiers["mid_cap"]["symbols"]
                        else "small"
                    )
                )
            )

            # Sort by timestamp
            df = df.sort_values(["symbol", "timestamp"]).reset_index(drop=True)

            return df

        return pd.DataFrame()


def main():
    # Initialize
    logger.info("=" * 80)
    logger.info("ADAPTIVE DCA LABEL GENERATOR")
    logger.info("=" * 80)

    supabase = SupabaseClient()
    generator = AdaptiveDCALabelGenerator(supabase)

    # Generate labels
    logger.info("\nGenerating DCA labels with adaptive thresholds...")
    logger.info("- Skipping BTC, ETH (poor DCA performance)")
    logger.info("- Large/Mid caps: 5% threshold")
    logger.info("- Small caps/Memecoins: 3% threshold")

    df = generator.generate_all_labels(lookback_days=180)

    if not df.empty:
        # Save to CSV
        output_file = "data/dca_labels_adaptive.csv"
        df.to_csv(output_file, index=False)
        logger.success(f"\nSaved {len(df)} labels to {output_file}")

        # Print summary statistics
        logger.info("\n" + "=" * 80)
        logger.info("SUMMARY STATISTICS")
        logger.info("=" * 80)

        # Overall stats
        total_setups = len(df)
        wins = len(df[df["outcome"] == "WIN"])
        losses = len(df[df["outcome"] == "LOSS"])
        win_rate = (wins / total_setups * 100) if total_setups > 0 else 0

        logger.info(f"\nOverall:")
        logger.info(f"  Total setups: {total_setups}")
        logger.info(f"  Wins: {wins} ({wins/total_setups*100:.1f}%)")
        logger.info(f"  Losses: {losses} ({losses/total_setups*100:.1f}%)")
        logger.info(f"  Win rate: {win_rate:.1f}%")

        # Stats by market cap tier
        for tier in df["market_cap_tier"].unique():
            tier_df = df[df["market_cap_tier"] == tier]
            tier_wins = len(tier_df[tier_df["outcome"] == "WIN"])
            tier_total = len(tier_df)
            tier_win_rate = (tier_wins / tier_total * 100) if tier_total > 0 else 0

            logger.info(f"\n{tier.upper()} CAP:")
            logger.info(f"  Setups: {tier_total}")
            logger.info(f"  Win rate: {tier_win_rate:.1f}%")
            logger.info(f"  Symbols: {tier_df['symbol'].nunique()}")

        # Top performing symbols
        logger.info("\n" + "=" * 80)
        logger.info("TOP PERFORMING SYMBOLS")
        logger.info("=" * 80)

        symbol_stats = []
        for symbol in df["symbol"].unique():
            sym_df = df[df["symbol"] == symbol]
            sym_wins = len(sym_df[sym_df["outcome"] == "WIN"])
            sym_total = len(sym_df)
            sym_win_rate = (sym_wins / sym_total * 100) if sym_total > 0 else 0

            if sym_total >= 10:  # Only include symbols with enough setups
                symbol_stats.append(
                    {"symbol": symbol, "setups": sym_total, "win_rate": sym_win_rate}
                )

        symbol_stats = sorted(symbol_stats, key=lambda x: x["win_rate"], reverse=True)[
            :10
        ]

        for stat in symbol_stats:
            logger.info(
                f"  {stat['symbol']}: {stat['setups']} setups, {stat['win_rate']:.1f}% win rate"
            )
    else:
        logger.warning("No labels generated")


if __name__ == "__main__":
    main()
