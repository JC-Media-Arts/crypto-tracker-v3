"""
Generate training labels for Swing Trading ML model
Scans historical data for breakout patterns and their outcomes
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Tuple
import json
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.supabase_client import SupabaseClient
from src.config.settings import Settings
from loguru import logger

# Configure logging
logging.basicConfig(level=logging.INFO)


class SwingLabelGenerator:
    """Generate labels for swing trading ML model training"""

    def __init__(self):
        self.settings = Settings()
        self.supabase = SupabaseClient()

        # Swing parameters from MASTER_PLAN.md
        self.config = {
            "breakout_threshold": 0.03,  # 3% move
            "volume_surge": 2.0,  # 2x average volume
            "min_rsi": 50,  # Momentum confirmation
            "take_profit": 0.15,  # 15% target
            "stop_loss": 0.05,  # 5% stop
            "max_hold_hours": 48,  # 48 hour time exit
            "lookback_window": 20,  # For resistance calculation
        }

        # Symbols to analyze (exclude stablecoins and new coins)
        self.symbols = [
            "BTC",
            "ETH",
            "SOL",
            "BNB",
            "XRP",
            "ADA",
            "AVAX",
            "DOGE",
            "DOT",
            "MATIC",
            "LINK",
            "SHIB",
            "UNI",
            "ATOM",
            "BCH",
            "NEAR",
            "ICP",
            "FIL",
            "IMX",
            "FLOW",
            "MANA",
            "AXS",
            "CHZ",
            "GALA",
            "LRC",
            "ALGO",
            "XLM",
            "VET",
            "THETA",
            "EOS",
            "AAVE",
            "CRV",
            "MKR",
            "SNX",
            "COMP",
            "YFI",
            "SUSHI",
            "BAL",
            "ENS",
            "GRT",
            "SAND",
            "RENDER",
            "FET",
            "INJ",
            "SEI",
            "ARB",
            "OP",
            "PEPE",
            "WIF",
            "BONK",
            "FLOKI",
            "RUNE",
            "KAS",
            "STX",
            "HBAR",
            "QNT",
            "KSM",
            "ZEC",
            "DASH",
            "XMR",
        ]

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators for swing detection"""

        # Price changes
        df["returns"] = df["close"].pct_change()
        df["price_change_24h"] = df["close"].pct_change(24)

        # Volume
        df["volume_sma"] = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_sma"]

        # RSI
        df["rsi"] = self.calculate_rsi(df["close"])

        # Moving averages
        df["sma_20"] = df["close"].rolling(window=20).mean()
        df["sma_50"] = df["close"].rolling(window=50).mean()

        # Resistance (20-period high)
        df["resistance"] = (
            df["high"].rolling(window=self.config["lookback_window"]).max()
        )

        # Support (20-period low)
        df["support"] = df["low"].rolling(window=self.config["lookback_window"]).min()

        # Breakout signal
        df["above_resistance"] = df["close"] > df["resistance"].shift(1)

        # Trend
        df["uptrend"] = (df["sma_20"] > df["sma_50"]) & (df["close"] > df["sma_20"])

        # Volatility
        df["volatility"] = df["returns"].rolling(window=20).std()

        # ATR for stop loss
        df["atr"] = self.calculate_atr(df)

        return df

    def detect_swing_setups(self, df: pd.DataFrame) -> List[Dict]:
        """Detect swing trading setups in historical data"""

        setups = []

        # Need enough data for indicators
        if len(df) < 100:
            return setups

        # Scan through data looking for breakouts
        for i in range(100, len(df) - 48):  # Leave room for outcome
            # Check breakout conditions
            if (
                df.iloc[i]["close"]
                > df.iloc[i - 1]["resistance"] * (1 + self.config["breakout_threshold"])
                and df.iloc[i]["volume_ratio"] > self.config["volume_surge"]
                and df.iloc[i]["rsi"] > self.config["min_rsi"]
                and df.iloc[i]["uptrend"]
            ):
                # Found a setup, now track outcome
                entry_price = df.iloc[i]["close"]
                entry_time = df.iloc[i]["timestamp"]

                # Calculate targets
                take_profit_price = entry_price * (1 + self.config["take_profit"])
                stop_loss_price = entry_price * (1 - self.config["stop_loss"])

                # Track for next 48 hours
                outcome = self.track_outcome(
                    df.iloc[i : i + 49],  # Next 48 hours
                    entry_price,
                    take_profit_price,
                    stop_loss_price,
                )

                # Calculate features at setup time
                features = {
                    "breakout_strength": (
                        df.iloc[i]["close"] - df.iloc[i - 1]["resistance"]
                    )
                    / df.iloc[i - 1]["resistance"],
                    "volume_ratio": df.iloc[i]["volume_ratio"],
                    "rsi": df.iloc[i]["rsi"],
                    "price_change_24h": df.iloc[i]["price_change_24h"],
                    "distance_from_sma20": (df.iloc[i]["close"] - df.iloc[i]["sma_20"])
                    / df.iloc[i]["sma_20"],
                    "distance_from_sma50": (df.iloc[i]["close"] - df.iloc[i]["sma_50"])
                    / df.iloc[i]["sma_50"],
                    "volatility": df.iloc[i]["volatility"],
                    "trend_strength": (df.iloc[i]["sma_20"] - df.iloc[i]["sma_50"])
                    / df.iloc[i]["sma_50"],
                    "resistance_tests": self.count_resistance_tests(
                        df.iloc[i - 20 : i], df.iloc[i - 1]["resistance"]
                    ),
                }

                setup = {
                    "timestamp": entry_time,
                    "symbol": df.iloc[i].get("symbol", "UNKNOWN"),
                    "entry_price": entry_price,
                    "take_profit_price": take_profit_price,
                    "stop_loss_price": stop_loss_price,
                    "outcome": outcome["result"],
                    "exit_price": outcome["exit_price"],
                    "exit_time": outcome["exit_time"],
                    "pnl_percent": outcome["pnl_percent"],
                    "hold_hours": outcome["hold_hours"],
                    "max_profit": outcome["max_profit"],
                    "max_loss": outcome["max_loss"],
                    "features": features,
                }

                setups.append(setup)

        return setups

    def track_outcome(
        self,
        future_df: pd.DataFrame,
        entry_price: float,
        take_profit: float,
        stop_loss: float,
    ) -> Dict:
        """Track the outcome of a swing setup"""

        result = "TIMEOUT"
        exit_price = entry_price
        exit_time = None
        hold_hours = 48
        max_profit = 0
        max_loss = 0

        for j in range(len(future_df)):
            current_price = future_df.iloc[j]["close"]
            high_price = future_df.iloc[j]["high"]
            low_price = future_df.iloc[j]["low"]

            # Track extremes
            profit = (high_price - entry_price) / entry_price
            loss = (low_price - entry_price) / entry_price
            max_profit = max(max_profit, profit)
            max_loss = min(max_loss, loss)

            # Check exit conditions
            if high_price >= take_profit:
                result = "WIN"
                exit_price = take_profit
                exit_time = future_df.iloc[j]["timestamp"]
                hold_hours = j + 1
                break
            elif low_price <= stop_loss:
                result = "LOSS"
                exit_price = stop_loss
                exit_time = future_df.iloc[j]["timestamp"]
                hold_hours = j + 1
                break

        # If no exit triggered, use final price
        if result == "TIMEOUT":
            exit_price = future_df.iloc[-1]["close"]
            exit_time = future_df.iloc[-1]["timestamp"]

            # Determine if it was profitable
            pnl = (exit_price - entry_price) / entry_price
            if pnl > 0.02:  # 2% profit threshold
                result = "SMALL_WIN"
            elif pnl < -0.02:
                result = "SMALL_LOSS"
            else:
                result = "BREAKEVEN"

        pnl_percent = ((exit_price - entry_price) / entry_price) * 100

        return {
            "result": result,
            "exit_price": exit_price,
            "exit_time": exit_time,
            "pnl_percent": pnl_percent,
            "hold_hours": hold_hours,
            "max_profit": max_profit * 100,
            "max_loss": max_loss * 100,
        }

    def count_resistance_tests(self, df: pd.DataFrame, resistance: float) -> int:
        """Count how many times price tested resistance level"""
        tests = 0
        for i in range(len(df)):
            if df.iloc[i]["high"] > resistance * 0.98:  # Within 2% of resistance
                tests += 1
        return tests

    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        high_low = df["high"] - df["low"]
        high_close = abs(df["high"] - df["close"].shift())
        low_close = abs(df["low"] - df["close"].shift())

        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        atr = true_range.rolling(window=period).mean()

        return atr

    def fetch_ohlc_data(self, symbol: str) -> pd.DataFrame:
        """Fetch OHLC data for a symbol"""
        try:
            # Fetch hourly data for swing analysis
            response = (
                self.supabase.client.table("ohlc_data")
                .select("*")
                .eq("symbol", symbol)
                .gte("timestamp", (datetime.now() - timedelta(days=180)).isoformat())
                .order("timestamp")
                .execute()
            )

            if response.data:
                df = pd.DataFrame(response.data)
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df["symbol"] = symbol
                return df
            else:
                logger.warning(f"No data found for {symbol}")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()

    def generate_labels(self):
        """Generate swing trading labels for all symbols"""

        all_setups = []
        summary = {
            "total_setups": 0,
            "wins": 0,
            "losses": 0,
            "breakeven": 0,
            "by_symbol": {},
        }

        logger.info(f"Generating swing labels for {len(self.symbols)} symbols...")

        for symbol in self.symbols:
            logger.info(f"Processing {symbol}...")

            # Fetch data
            df = self.fetch_ohlc_data(symbol)

            if df.empty:
                continue

            # Calculate indicators
            df = self.calculate_indicators(df)

            # Detect setups
            setups = self.detect_swing_setups(df)

            if setups:
                logger.info(f"  Found {len(setups)} setups for {symbol}")

                # Calculate statistics
                wins = sum(1 for s in setups if s["outcome"] in ["WIN", "SMALL_WIN"])
                losses = sum(
                    1 for s in setups if s["outcome"] in ["LOSS", "SMALL_LOSS"]
                )
                win_rate = (wins / len(setups)) * 100 if setups else 0

                avg_win = (
                    np.mean(
                        [
                            s["pnl_percent"]
                            for s in setups
                            if s["outcome"] in ["WIN", "SMALL_WIN"]
                        ]
                    )
                    if wins > 0
                    else 0
                )
                avg_loss = (
                    np.mean(
                        [
                            s["pnl_percent"]
                            for s in setups
                            if s["outcome"] in ["LOSS", "SMALL_LOSS"]
                        ]
                    )
                    if losses > 0
                    else 0
                )

                logger.info(f"  Win rate: {win_rate:.1f}% ({wins}W/{losses}L)")
                logger.info(f"  Avg win: {avg_win:.2f}%, Avg loss: {avg_loss:.2f}%")

                summary["by_symbol"][symbol] = {
                    "setups": len(setups),
                    "wins": wins,
                    "losses": losses,
                    "win_rate": win_rate,
                    "avg_win": avg_win,
                    "avg_loss": avg_loss,
                }

                all_setups.extend(setups)

        # Overall summary
        summary["total_setups"] = len(all_setups)
        summary["wins"] = sum(
            1 for s in all_setups if s["outcome"] in ["WIN", "SMALL_WIN"]
        )
        summary["losses"] = sum(
            1 for s in all_setups if s["outcome"] in ["LOSS", "SMALL_LOSS"]
        )
        summary["breakeven"] = sum(
            1 for s in all_setups if s["outcome"] in ["BREAKEVEN", "TIMEOUT"]
        )

        overall_win_rate = (
            (summary["wins"] / summary["total_setups"]) * 100
            if summary["total_setups"] > 0
            else 0
        )

        logger.info("\n" + "=" * 60)
        logger.info("SWING LABEL GENERATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Total setups found: {summary['total_setups']}")
        logger.info(f"Overall win rate: {overall_win_rate:.1f}%")
        logger.info(
            f"Wins: {summary['wins']}, Losses: {summary['losses']}, Breakeven: {summary['breakeven']}"
        )

        # Save labels
        if all_setups:
            # Save to JSON
            output_file = "data/swing_training_labels.json"
            os.makedirs("data", exist_ok=True)

            with open(output_file, "w") as f:
                json.dump(
                    {
                        "labels": all_setups,
                        "summary": summary,
                        "config": self.config,
                        "generated_at": datetime.now().isoformat(),
                    },
                    f,
                    indent=2,
                    default=str,
                )

            logger.info(f"\nLabels saved to {output_file}")

            # Also save as CSV for easier analysis
            df_labels = pd.DataFrame(all_setups)

            # Flatten features into columns
            features_df = pd.DataFrame([s["features"] for s in all_setups])
            df_labels = pd.concat(
                [df_labels.drop("features", axis=1), features_df], axis=1
            )

            csv_file = "data/swing_training_labels.csv"
            df_labels.to_csv(csv_file, index=False)
            logger.info(f"CSV saved to {csv_file}")

            # Save to database for ML training
            logger.info("\nSaving labels to strategy_swing_labels table...")
            saved_count = 0
            skipped_count = 0

            for setup in all_setups:
                # Prepare data for strategy_swing_labels table
                label_data = {
                    "symbol": setup["symbol"],
                    "timestamp": setup["timestamp"],
                    "breakout_detected": True,
                    "breakout_strength": float(
                        setup["features"].get("breakout_pct", 0) * 100
                    ),
                    "volume_surge": float(setup["features"].get("volume_ratio", 1.0)),
                    "momentum_score": float(setup["features"].get("rsi", 50)),
                    "trend_alignment": (
                        "UPTREND"
                        if setup["features"].get("sma_trend", 0) > 0
                        else "DOWNTREND"
                    ),
                    "outcome": setup["outcome"],
                    "optimal_take_profit": float(setup.get("take_profit", 15.0)),
                    "optimal_stop_loss": float(setup.get("stop_loss", -5.0)),
                    "actual_return": float(setup["actual_return"]) * 100,
                    "hold_time_hours": int(setup["hold_hours"]),
                    "features": setup["features"],
                }

                try:
                    # Use upsert to handle duplicates gracefully
                    result = (
                        self.supabase.client.table("strategy_swing_labels")
                        .upsert(label_data, on_conflict="symbol,timestamp")
                        .execute()
                    )
                    if result.data:
                        saved_count += 1
                except Exception as e:
                    if "duplicate" in str(e).lower():
                        skipped_count += 1
                    else:
                        logger.error(
                            f"Error saving label for {setup['symbol']} at {setup['timestamp']}: {e}"
                        )

            logger.info(f"Saved {saved_count} labels to strategy_swing_labels table")
            if skipped_count > 0:
                logger.info(f"Skipped {skipped_count} duplicate labels")

        return all_setups, summary


def main():
    """Main execution"""
    generator = SwingLabelGenerator()
    labels, summary = generator.generate_labels()

    # Print top performing symbols
    if summary["by_symbol"]:
        logger.info("\nTop performing symbols by win rate:")
        sorted_symbols = sorted(
            summary["by_symbol"].items(), key=lambda x: x[1]["win_rate"], reverse=True
        )[:10]

        for symbol, stats in sorted_symbols:
            logger.info(
                f"  {symbol}: {stats['win_rate']:.1f}% ({stats['wins']}W/{stats['losses']}L)"
            )


if __name__ == "__main__":
    main()
