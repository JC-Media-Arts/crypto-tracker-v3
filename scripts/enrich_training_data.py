#!/usr/bin/env python3
"""
Enrich DCA training labels with historical market context features.
This adds BTC regime, volatility, and other market indicators at the time of each setup.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from dateutil import tz
import pandas as pd
import numpy as np
from typing import Dict, Optional

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from loguru import logger


class TrainingDataEnricher:
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.btc_cache = {}  # Cache BTC data to avoid repeated queries

    def fetch_btc_data(self, timestamp: datetime, lookback_days: int = 210) -> pd.DataFrame:
        """Fetch BTC OHLC data around a specific timestamp."""
        # Round to nearest day for caching
        cache_key = timestamp.date()

        if cache_key in self.btc_cache:
            return self.btc_cache[cache_key]

        # Fetch data with buffer for SMA calculations
        end_time = timestamp + timedelta(days=1)
        start_time = timestamp - timedelta(days=lookback_days)

        all_data = []
        current_start = start_time

        while current_start < end_time:
            current_end = min(current_start + timedelta(days=30), end_time)

            result = (
                self.supabase.client.table("ohlc_data")
                .select("timestamp,open,high,low,close,volume")
                .eq("symbol", "BTC")
                .eq("timeframe", "1d")
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

            # Cache the result
            self.btc_cache[cache_key] = df
            return df

        return pd.DataFrame()

    def calculate_btc_regime(self, timestamp: datetime) -> Dict:
        """Calculate BTC market regime and related metrics at a specific timestamp."""
        btc_data = self.fetch_btc_data(timestamp)

        if btc_data.empty or len(btc_data) < 200:
            return {
                "btc_regime": "UNKNOWN",
                "btc_sma50": None,
                "btc_sma200": None,
                "btc_sma50_distance": None,
                "btc_sma200_distance": None,
                "btc_trend_strength": None,
            }

        # Get data up to the timestamp
        btc_data = btc_data[btc_data["timestamp"] <= timestamp].copy()

        if len(btc_data) < 200:
            return {
                "btc_regime": "UNKNOWN",
                "btc_sma50": None,
                "btc_sma200": None,
                "btc_sma50_distance": None,
                "btc_sma200_distance": None,
                "btc_trend_strength": None,
            }

        # Calculate SMAs
        btc_data["sma50"] = btc_data["close"].rolling(window=50, min_periods=50).mean()
        btc_data["sma200"] = btc_data["close"].rolling(window=200, min_periods=200).mean()

        # Get latest values
        latest = btc_data.iloc[-1]
        current_price = latest["close"]
        sma50 = latest["sma50"]
        sma200 = latest["sma200"]

        # Calculate distances
        sma50_distance = ((current_price - sma50) / sma50) * 100 if sma50 else None
        sma200_distance = ((current_price - sma200) / sma200) * 100 if sma200 else None

        # Determine regime
        if pd.notna(sma50) and pd.notna(sma200):
            if sma50 > sma200 and current_price > sma50:
                regime = "BULL"
            elif sma50 < sma200 and current_price < sma50:
                regime = "BEAR"
            else:
                regime = "NEUTRAL"
        else:
            regime = "UNKNOWN"

        # Calculate trend strength (rate of change over last 30 days)
        if len(btc_data) >= 30:
            price_30d_ago = btc_data.iloc[-30]["close"]
            trend_strength = ((current_price - price_30d_ago) / price_30d_ago) * 100
        else:
            trend_strength = None

        return {
            "btc_regime": regime,
            "btc_price": current_price,
            "btc_sma50": sma50,
            "btc_sma200": sma200,
            "btc_sma50_distance": sma50_distance,
            "btc_sma200_distance": sma200_distance,
            "btc_trend_strength": trend_strength,
        }

    def calculate_volatility(self, timestamp: datetime) -> Dict:
        """Calculate market volatility metrics at a specific timestamp."""
        btc_data = self.fetch_btc_data(timestamp, lookback_days=60)

        if btc_data.empty:
            return {
                "btc_volatility_7d": None,
                "btc_volatility_30d": None,
                "btc_high_low_range_7d": None,
            }

        # Get data up to the timestamp
        btc_data = btc_data[btc_data["timestamp"] <= timestamp].copy()

        # Calculate returns
        btc_data["returns"] = btc_data["close"].pct_change()

        # 7-day volatility
        if len(btc_data) >= 7:
            vol_7d = btc_data["returns"].iloc[-7:].std() * np.sqrt(365) * 100
            high_7d = btc_data["high"].iloc[-7:].max()
            low_7d = btc_data["low"].iloc[-7:].min()
            range_7d = ((high_7d - low_7d) / low_7d) * 100 if low_7d else None
        else:
            vol_7d = None
            range_7d = None

        # 30-day volatility
        if len(btc_data) >= 30:
            vol_30d = btc_data["returns"].iloc[-30:].std() * np.sqrt(365) * 100
        else:
            vol_30d = None

        return {
            "btc_volatility_7d": vol_7d,
            "btc_volatility_30d": vol_30d,
            "btc_high_low_range_7d": range_7d,
        }

    def calculate_symbol_context(self, symbol: str, timestamp: datetime) -> Dict:
        """Calculate symbol-specific context relative to BTC."""
        if symbol == "BTC":
            return {
                "symbol_vs_btc_7d": 0,
                "symbol_vs_btc_30d": 0,
                "symbol_correlation_30d": 1.0,
            }

        # Fetch symbol data
        end_time = timestamp + timedelta(days=1)
        start_time = timestamp - timedelta(days=35)

        # Get symbol data
        symbol_result = (
            self.supabase.client.table("ohlc_data")
            .select("timestamp,close")
            .eq("symbol", symbol)
            .eq("timeframe", "1d")
            .gte("timestamp", start_time.isoformat())
            .lt("timestamp", end_time.isoformat())
            .order("timestamp")
            .execute()
        )

        if not symbol_result.data or len(symbol_result.data) < 7:
            return {
                "symbol_vs_btc_7d": None,
                "symbol_vs_btc_30d": None,
                "symbol_correlation_30d": None,
            }

        # Get BTC data for comparison
        btc_data = self.fetch_btc_data(timestamp, lookback_days=35)
        btc_data = btc_data[btc_data["timestamp"] <= timestamp]

        # Convert symbol data to DataFrame
        symbol_df = pd.DataFrame(symbol_result.data)
        symbol_df["timestamp"] = pd.to_datetime(symbol_df["timestamp"], format="ISO8601")
        symbol_df = symbol_df.sort_values("timestamp")

        # Calculate relative performance
        if len(symbol_df) >= 7 and len(btc_data) >= 7:
            symbol_7d_return = (symbol_df["close"].iloc[-1] / symbol_df["close"].iloc[-7] - 1) * 100
            btc_7d_return = (btc_data["close"].iloc[-1] / btc_data["close"].iloc[-7] - 1) * 100
            vs_btc_7d = symbol_7d_return - btc_7d_return
        else:
            vs_btc_7d = None

        if len(symbol_df) >= 30 and len(btc_data) >= 30:
            symbol_30d_return = (symbol_df["close"].iloc[-1] / symbol_df["close"].iloc[-30] - 1) * 100
            btc_30d_return = (btc_data["close"].iloc[-1] / btc_data["close"].iloc[-30] - 1) * 100
            vs_btc_30d = symbol_30d_return - btc_30d_return

            # Calculate correlation
            symbol_returns = symbol_df["close"].pct_change().iloc[-30:]
            btc_returns = btc_data["close"].pct_change().iloc[-30:]

            # Align the data
            merged = pd.DataFrame({"symbol": symbol_returns.values, "btc": btc_returns.values}).dropna()

            if len(merged) >= 10:
                correlation = merged["symbol"].corr(merged["btc"])
            else:
                correlation = None
        else:
            vs_btc_30d = None
            correlation = None

        return {
            "symbol_vs_btc_7d": vs_btc_7d,
            "symbol_vs_btc_30d": vs_btc_30d,
            "symbol_correlation_30d": correlation,
        }

    def enrich_training_data(self, input_file: str, output_file: str):
        """Enrich the training data with market context features."""
        # Load existing labels
        logger.info(f"Loading training data from {input_file}")
        df = pd.read_csv(input_file)

        # Convert timestamp to datetime
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        logger.info(f"Enriching {len(df)} training examples...")

        # Process in batches to show progress
        batch_size = 100
        enriched_data = []

        for i in range(0, len(df), batch_size):
            batch = df.iloc[i : min(i + batch_size, len(df))]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(df)-1)//batch_size + 1}")

            for idx, row in batch.iterrows():
                timestamp = (
                    row["timestamp"].replace(tzinfo=tz.UTC) if row["timestamp"].tzinfo is None else row["timestamp"]
                )
                symbol = row["symbol"]

                # Get BTC regime and metrics
                btc_metrics = self.calculate_btc_regime(timestamp)

                # Get volatility metrics
                volatility_metrics = self.calculate_volatility(timestamp)

                # Get symbol-specific context
                symbol_context = self.calculate_symbol_context(symbol, timestamp)

                # Combine all features
                enriched_row = {
                    **row.to_dict(),
                    **btc_metrics,
                    **volatility_metrics,
                    **symbol_context,
                }
                enriched_data.append(enriched_row)

        # Create enriched DataFrame
        enriched_df = pd.DataFrame(enriched_data)

        # Add derived features
        enriched_df["is_high_volatility"] = (enriched_df["btc_volatility_7d"] > 50).astype(int)
        enriched_df["is_oversold"] = (enriched_df["btc_sma50_distance"] < -5).astype(int)
        enriched_df["is_overbought"] = (enriched_df["btc_sma50_distance"] > 10).astype(int)

        # Add day of week and hour features
        enriched_df["day_of_week"] = enriched_df["timestamp"].dt.dayofweek
        enriched_df["hour"] = enriched_df["timestamp"].dt.hour

        # Save enriched data
        enriched_df.to_csv(output_file, index=False)
        logger.success(f"Saved enriched training data to {output_file}")

        # Print summary statistics
        logger.info("\n" + "=" * 80)
        logger.info("ENRICHMENT SUMMARY")
        logger.info("=" * 80)

        # Regime distribution
        regime_counts = enriched_df["btc_regime"].value_counts()
        logger.info("\nBTC Regime Distribution:")
        for regime, count in regime_counts.items():
            pct = (count / len(enriched_df)) * 100
            logger.info(f"  {regime}: {count} ({pct:.1f}%)")

        # Win rates by regime
        logger.info("\nWin Rates by BTC Regime:")
        for regime in enriched_df["btc_regime"].unique():
            regime_df = enriched_df[enriched_df["btc_regime"] == regime]
            if "outcome" in regime_df.columns:
                wins = len(regime_df[regime_df["outcome"] == "WIN"])
                total = len(regime_df)
                win_rate = (wins / total * 100) if total > 0 else 0
                logger.info(f"  {regime}: {win_rate:.1f}% ({wins}/{total})")

        # Volatility stats
        logger.info("\nVolatility Statistics:")
        logger.info(f"  Mean 7-day volatility: {enriched_df['btc_volatility_7d'].mean():.1f}%")
        logger.info(f"  Mean 30-day volatility: {enriched_df['btc_volatility_30d'].mean():.1f}%")

        # High volatility win rate
        if "outcome" in enriched_df.columns:
            high_vol = enriched_df[enriched_df["is_high_volatility"] == 1]
            low_vol = enriched_df[enriched_df["is_high_volatility"] == 0]

            if len(high_vol) > 0:
                high_vol_wins = len(high_vol[high_vol["outcome"] == "WIN"])
                high_vol_rate = (high_vol_wins / len(high_vol)) * 100
                logger.info(f"  High volatility win rate: {high_vol_rate:.1f}%")

            if len(low_vol) > 0:
                low_vol_wins = len(low_vol[low_vol["outcome"] == "WIN"])
                low_vol_rate = (low_vol_wins / len(low_vol)) * 100
                logger.info(f"  Low volatility win rate: {low_vol_rate:.1f}%")

        return enriched_df


def main():
    # Initialize
    logger.info("=" * 80)
    logger.info("TRAINING DATA ENRICHMENT")
    logger.info("=" * 80)

    supabase = SupabaseClient()
    enricher = TrainingDataEnricher(supabase)

    # Enrich the adaptive DCA labels
    input_file = "data/dca_labels_adaptive.csv"
    output_file = "data/dca_labels_enriched.csv"

    if not Path(input_file).exists():
        logger.error(f"Input file {input_file} not found!")
        return

    # Run enrichment
    enricher.enrich_training_data(input_file, output_file)

    logger.info("\n" + "=" * 80)
    logger.info("✅ Enrichment complete! Ready for ML training.")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
