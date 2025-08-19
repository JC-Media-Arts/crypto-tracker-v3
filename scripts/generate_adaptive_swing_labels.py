"""
Generate adaptive training labels for Swing Trading ML model
Uses more realistic targets based on market conditions
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


class AdaptiveSwingLabelGenerator:
    """Generate adaptive labels for swing trading ML model training"""

    def __init__(self):
        self.settings = Settings()
        self.supabase = SupabaseClient()

        # More realistic adaptive parameters
        self.config = {
            "breakout_thresholds": [0.015, 0.02, 0.025, 0.03],  # 1.5-3% moves
            "volume_surges": [1.5, 2.0, 2.5],  # Different volume levels
            "min_rsi": 45,  # Lower threshold for more setups
            "adaptive_targets": {
                "conservative": {"tp": 0.05, "sl": 0.03},  # 5% TP, 3% SL
                "moderate": {"tp": 0.08, "sl": 0.04},  # 8% TP, 4% SL
                "aggressive": {"tp": 0.12, "sl": 0.05},  # 12% TP, 5% SL
            },
            "max_hold_hours": 72,  # Extended to 72 hours
            "lookback_window": 20,
        }

        # Categorize symbols by volatility
        self.symbol_categories = {
            "stable": ["BTC", "ETH", "BNB", "XRP", "ADA"],
            "moderate": ["SOL", "AVAX", "DOT", "MATIC", "LINK", "UNI", "ATOM"],
            "volatile": ["DOGE", "SHIB", "PEPE", "WIF", "BONK", "FLOKI"],
            "other": [],  # Will be categorized dynamically
        }

        # All symbols to analyze
        self.symbols = [
            "BTC",
            "ETH",
            "SOL",
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
            "MANA",
            "AXS",
            "CHZ",
            "GALA",
            "LRC",
            "ALGO",
            "XLM",
            "VET",
            "THETA",
            "AAVE",
            "CRV",
            "MKR",
            "SNX",
            "COMP",
            "YFI",
            "SUSHI",
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
        ]

    def get_symbol_category(self, symbol: str, volatility: float) -> str:
        """Categorize symbol based on known categories or volatility"""
        for category, symbols in self.symbol_categories.items():
            if symbol in symbols:
                return category

        # Categorize based on volatility
        if volatility < 0.03:
            return "stable"
        elif volatility < 0.05:
            return "moderate"
        else:
            return "volatile"

    def get_adaptive_targets(
        self, symbol: str, volatility: float, market_condition: str
    ) -> Dict:
        """Get adaptive targets based on symbol and market conditions"""
        category = self.get_symbol_category(symbol, volatility)

        # Adjust based on category
        if category == "stable":
            base_config = self.config["adaptive_targets"]["conservative"]
        elif category == "moderate":
            base_config = self.config["adaptive_targets"]["moderate"]
        else:
            base_config = self.config["adaptive_targets"]["aggressive"]

        # Further adjust based on market condition
        if market_condition == "trending":
            # Wider targets in trending markets
            return {
                "take_profit": base_config["tp"] * 1.2,
                "stop_loss": base_config["sl"] * 1.1,
            }
        elif market_condition == "choppy":
            # Tighter targets in choppy markets
            return {
                "take_profit": base_config["tp"] * 0.8,
                "stop_loss": base_config["sl"] * 0.9,
            }
        else:
            return {"take_profit": base_config["tp"], "stop_loss": base_config["sl"]}

    def calculate_market_condition(self, df: pd.DataFrame, i: int) -> str:
        """Determine market condition at a point in time"""
        if i < 50:
            return "neutral"

        # Look at recent price action
        recent = df.iloc[i - 50 : i]

        # Calculate trend strength
        sma_20 = recent["close"].rolling(20).mean().iloc[-1]
        sma_50 = recent["close"].rolling(50).mean().iloc[-1]

        if sma_20 > sma_50 * 1.02:
            return "trending"
        elif abs(sma_20 - sma_50) / sma_50 < 0.01:
            return "choppy"
        else:
            return "neutral"

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

        # Resistance and support
        df["resistance"] = (
            df["high"].rolling(window=self.config["lookback_window"]).max()
        )
        df["support"] = df["low"].rolling(window=self.config["lookback_window"]).min()

        # Volatility
        df["volatility"] = df["returns"].rolling(window=20).std()

        # ATR
        df["atr"] = self.calculate_atr(df)

        # Bollinger Bands
        (
            df["bb_upper"],
            df["bb_middle"],
            df["bb_lower"],
        ) = self.calculate_bollinger_bands(df["close"])

        # MACD
        exp1 = df["close"].ewm(span=12, adjust=False).mean()
        exp2 = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = exp1 - exp2
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()

        return df

    def detect_swing_setups(self, df: pd.DataFrame, symbol: str) -> List[Dict]:
        """Detect swing trading setups with adaptive parameters"""

        setups = []

        if len(df) < 100:
            return setups

        # Try different parameter combinations
        for breakout_threshold in self.config["breakout_thresholds"]:
            for volume_surge in self.config["volume_surges"]:
                for i in range(100, len(df) - 72):  # Leave room for 72-hour outcome
                    # Basic breakout conditions
                    price_above_resistance = df.iloc[i]["close"] > df.iloc[i - 1][
                        "resistance"
                    ] * (1 + breakout_threshold)
                    volume_confirmed = df.iloc[i]["volume_ratio"] > volume_surge
                    rsi_positive = df.iloc[i]["rsi"] > self.config["min_rsi"]

                    # Additional filters
                    above_sma20 = df.iloc[i]["close"] > df.iloc[i]["sma_20"]
                    macd_positive = df.iloc[i]["macd"] > df.iloc[i]["macd_signal"]

                    if (
                        price_above_resistance
                        and volume_confirmed
                        and rsi_positive
                        and above_sma20
                    ):
                        # Get adaptive targets
                        volatility = df.iloc[i]["volatility"]
                        market_condition = self.calculate_market_condition(df, i)
                        targets = self.get_adaptive_targets(
                            symbol, volatility, market_condition
                        )

                        entry_price = df.iloc[i]["close"]
                        entry_time = df.iloc[i]["timestamp"]

                        take_profit_price = entry_price * (1 + targets["take_profit"])
                        stop_loss_price = entry_price * (1 - targets["stop_loss"])

                        # Track outcome
                        outcome = self.track_outcome(
                            df.iloc[i : i + 73],  # Next 72 hours
                            entry_price,
                            take_profit_price,
                            stop_loss_price,
                        )

                        # Calculate features
                        features = {
                            "breakout_strength": (
                                df.iloc[i]["close"] - df.iloc[i - 1]["resistance"]
                            )
                            / df.iloc[i - 1]["resistance"],
                            "volume_ratio": df.iloc[i]["volume_ratio"],
                            "rsi": df.iloc[i]["rsi"],
                            "price_change_24h": df.iloc[i]["price_change_24h"],
                            "distance_from_sma20": (
                                df.iloc[i]["close"] - df.iloc[i]["sma_20"]
                            )
                            / df.iloc[i]["sma_20"],
                            "distance_from_sma50": (
                                df.iloc[i]["close"] - df.iloc[i]["sma_50"]
                            )
                            / df.iloc[i]["sma_50"],
                            "volatility": volatility,
                            "macd_histogram": df.iloc[i]["macd"]
                            - df.iloc[i]["macd_signal"],
                            "bb_position": (
                                df.iloc[i]["close"] - df.iloc[i]["bb_lower"]
                            )
                            / (df.iloc[i]["bb_upper"] - df.iloc[i]["bb_lower"]),
                            "atr_ratio": df.iloc[i]["atr"] / df.iloc[i]["close"],
                            "breakout_threshold_used": breakout_threshold,
                            "volume_surge_used": volume_surge,
                        }

                        setup = {
                            "timestamp": entry_time,
                            "symbol": symbol,
                            "entry_price": entry_price,
                            "take_profit_price": take_profit_price,
                            "stop_loss_price": stop_loss_price,
                            "take_profit_pct": targets["take_profit"] * 100,
                            "stop_loss_pct": targets["stop_loss"] * 100,
                            "outcome": outcome["result"],
                            "exit_price": outcome["exit_price"],
                            "exit_time": outcome["exit_time"],
                            "pnl_percent": outcome["pnl_percent"],
                            "hold_hours": outcome["hold_hours"],
                            "max_profit": outcome["max_profit"],
                            "max_loss": outcome["max_loss"],
                            "market_condition": market_condition,
                            "symbol_category": self.get_symbol_category(
                                symbol, volatility
                            ),
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
        hold_hours = 72
        max_profit = 0
        max_loss = 0

        for j in range(min(len(future_df), 72)):
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

        # If no exit triggered, check final price
        if result == "TIMEOUT":
            final_idx = min(71, len(future_df) - 1)
            exit_price = future_df.iloc[final_idx]["close"]
            exit_time = future_df.iloc[final_idx]["timestamp"]

            pnl = (exit_price - entry_price) / entry_price
            if pnl > 0.02:
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

    def calculate_bollinger_bands(
        self, prices: pd.Series, period: int = 20, std: int = 2
    ):
        """Calculate Bollinger Bands"""
        middle = prices.rolling(window=period).mean()
        std_dev = prices.rolling(window=period).std()
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        return upper, middle, lower

    def fetch_ohlc_data(self, symbol: str) -> pd.DataFrame:
        """Fetch OHLC data for a symbol"""
        try:
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
                return df
            else:
                logger.warning(f"No data found for {symbol}")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()

    def generate_labels(self):
        """Generate adaptive swing trading labels"""

        all_setups = []
        summary = {
            "total_setups": 0,
            "wins": 0,
            "losses": 0,
            "by_category": {},
            "by_symbol": {},
        }

        logger.info(
            f"Generating adaptive swing labels for {len(self.symbols)} symbols..."
        )

        for symbol in self.symbols:
            logger.info(f"Processing {symbol}...")

            df = self.fetch_ohlc_data(symbol)

            if df.empty:
                continue

            df = self.calculate_indicators(df)
            setups = self.detect_swing_setups(df, symbol)

            if setups:
                logger.info(f"  Found {len(setups)} setups for {symbol}")

                wins = sum(1 for s in setups if s["outcome"] in ["WIN", "SMALL_WIN"])
                losses = sum(
                    1 for s in setups if s["outcome"] in ["LOSS", "SMALL_LOSS"]
                )
                win_rate = (wins / len(setups)) * 100 if setups else 0

                logger.info(f"  Win rate: {win_rate:.1f}% ({wins}W/{losses}L)")

                summary["by_symbol"][symbol] = {
                    "setups": len(setups),
                    "wins": wins,
                    "losses": losses,
                    "win_rate": win_rate,
                }

                all_setups.extend(setups)

        # Summarize by category
        for setup in all_setups:
            category = setup["symbol_category"]
            if category not in summary["by_category"]:
                summary["by_category"][category] = {"wins": 0, "losses": 0, "total": 0}

            summary["by_category"][category]["total"] += 1
            if setup["outcome"] in ["WIN", "SMALL_WIN"]:
                summary["by_category"][category]["wins"] += 1
            elif setup["outcome"] in ["LOSS", "SMALL_LOSS"]:
                summary["by_category"][category]["losses"] += 1

        summary["total_setups"] = len(all_setups)
        summary["wins"] = sum(
            1 for s in all_setups if s["outcome"] in ["WIN", "SMALL_WIN"]
        )
        summary["losses"] = sum(
            1 for s in all_setups if s["outcome"] in ["LOSS", "SMALL_LOSS"]
        )

        overall_win_rate = (
            (summary["wins"] / summary["total_setups"]) * 100
            if summary["total_setups"] > 0
            else 0
        )

        logger.info("\n" + "=" * 60)
        logger.info("ADAPTIVE SWING LABEL GENERATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Total setups found: {summary['total_setups']}")
        logger.info(f"Overall win rate: {overall_win_rate:.1f}%")
        logger.info(f"Wins: {summary['wins']}, Losses: {summary['losses']}")

        # Save labels
        if all_setups:
            output_file = "data/adaptive_swing_labels.json"
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

            # Save CSV
            df_labels = pd.DataFrame(all_setups)
            features_df = pd.DataFrame([s["features"] for s in all_setups])
            df_labels = pd.concat(
                [df_labels.drop("features", axis=1), features_df], axis=1
            )

            csv_file = "data/adaptive_swing_labels.csv"
            df_labels.to_csv(csv_file, index=False)
            logger.info(f"CSV saved to {csv_file}")

        return all_setups, summary


def main():
    """Main execution"""
    generator = AdaptiveSwingLabelGenerator()
    labels, summary = generator.generate_labels()

    # Print category performance
    if summary["by_category"]:
        logger.info("\nPerformance by category:")
        for category, stats in summary["by_category"].items():
            if stats["total"] > 0:
                win_rate = (stats["wins"] / stats["total"]) * 100
                logger.info(
                    f"  {category}: {win_rate:.1f}% ({stats['wins']}W/{stats['losses']}L)"
                )


if __name__ == "__main__":
    main()
