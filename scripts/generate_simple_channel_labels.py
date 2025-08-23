#!/usr/bin/env python3
"""
Generate simplified training labels for Channel/Range Trading Strategy
Looks for price consolidation patterns that can be traded
"""

import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from loguru import logger
import sys

sys.path.append(".")

from src.data.supabase_client import SupabaseClient

# Configure logger
logger.add("logs/simple_channel_labels.log", rotation="10 MB")


class SimpleChannelLabelGenerator:
    """Generate training labels for range/channel trading"""

    def __init__(self):
        self.supabase = SupabaseClient()

        # Pattern detection parameters
        self.lookback_periods = 50  # Look at 50 bars
        self.min_touches = 2  # Min touches of support/resistance
        self.range_threshold = 0.02  # 2% range threshold
        self.breakout_threshold = 0.01  # 1% breakout threshold

    def fetch_ohlc_data(self, symbol: str, lookback_days: int = 180) -> pd.DataFrame:
        """Fetch OHLC data for a symbol"""
        try:
            start_date = datetime.now() - timedelta(days=lookback_days)

            response = (
                self.supabase.client.table("ohlc_data")
                .select("*")
                .eq("symbol", symbol)
                .gte("timestamp", start_date.isoformat())
                .order("timestamp", desc=False)
                .execute()
            )

            if response.data:
                df = pd.DataFrame(response.data)
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                logger.info(f"Fetched {len(df)} bars for {symbol}")
                return df
            else:
                logger.warning(f"No data found for {symbol}")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()

    def detect_range_patterns(self, symbol: str, df: pd.DataFrame) -> List[Dict]:
        """Detect simple range/consolidation patterns"""
        setups = []

        if len(df) < self.lookback_periods + 50:
            return setups

        # Use rolling windows to find consolidation patterns
        for i in range(self.lookback_periods, len(df) - 50):
            # Get window
            window = df.iloc[i - self.lookback_periods : i]

            # Calculate range statistics
            high_max = window["high"].max()
            low_min = window["low"].min()
            avg_price = window["close"].mean()

            # Calculate range width
            range_width = (high_max - low_min) / avg_price

            # Check if it's a valid range (not too wide, not too narrow)
            if 0.02 <= range_width <= 0.15:  # 2% to 15% range
                # Count touches of support and resistance
                resistance_touches = sum(window["high"] >= high_max * 0.995)
                support_touches = sum(window["low"] <= low_min * 1.005)

                if resistance_touches >= 2 and support_touches >= 2:
                    # We have a range!
                    current_price = window.iloc[-1]["close"]
                    position_in_range = (current_price - low_min) / (high_max - low_min)

                    # Determine signal
                    signal = None
                    if position_in_range <= 0.3:  # Bottom 30% - BUY
                        signal = "BUY"
                        take_profit = high_max * 0.99  # Target top of range
                        stop_loss = low_min * 0.99  # Below range
                    elif position_in_range >= 0.7:  # Top 30% - SELL
                        signal = "SELL"
                        take_profit = low_min * 1.01  # Target bottom of range
                        stop_loss = high_max * 1.01  # Above range

                    if signal:
                        # Calculate risk/reward
                        if signal == "BUY":
                            risk = abs(current_price - stop_loss) / current_price
                            reward = abs(take_profit - current_price) / current_price
                        else:
                            risk = abs(stop_loss - current_price) / current_price
                            reward = abs(current_price - take_profit) / current_price

                        risk_reward = reward / risk if risk > 0 else 0

                        if risk_reward >= 1.5:  # Minimum 1.5:1 R:R
                            setup = {
                                "symbol": symbol,
                                "timestamp": window.iloc[-1]["timestamp"].isoformat(),
                                "signal": signal,
                                "entry_price": current_price,
                                "high_resistance": high_max,
                                "low_support": low_min,
                                "range_width": range_width,
                                "position_in_range": position_in_range,
                                "resistance_touches": int(resistance_touches),
                                "support_touches": int(support_touches),
                                "take_profit": take_profit,
                                "stop_loss": stop_loss,
                                "risk_reward": risk_reward,
                                "features": {
                                    "range_width": range_width,
                                    "position_in_range": position_in_range,
                                    "total_touches": int(resistance_touches + support_touches),
                                    "volatility": float(window["close"].std() / avg_price),
                                    "volume_trend": float(window["volume"].iloc[-10:].mean() / window["volume"].mean()),
                                },
                            }

                            # Calculate outcome
                            outcome = self._calculate_outcome(setup, df.iloc[i : i + 50])  # Look forward 50 bars
                            setup.update(outcome)

                            setups.append(setup)

        return setups

    def _calculate_outcome(self, setup: Dict, future_df: pd.DataFrame) -> Dict:
        """Calculate the outcome of a range trade"""
        entry_price = setup["entry_price"]
        take_profit = setup["take_profit"]
        stop_loss = setup["stop_loss"]
        signal = setup["signal"]

        outcome = {
            "outcome": "EXPIRED",
            "exit_price": entry_price,
            "exit_bars": 0,
            "max_profit_pct": 0.0,
            "max_loss_pct": 0.0,
            "actual_pnl_pct": 0.0,
        }

        if future_df.empty:
            return outcome

        for i, (_, row) in enumerate(future_df.iterrows()):
            if i >= 72:  # Max 72 bars (hours)
                break

            if signal == "BUY":
                # Check if hit take profit
                if row["high"] >= take_profit:
                    outcome["outcome"] = "WIN"
                    outcome["exit_price"] = take_profit
                    outcome["exit_bars"] = i + 1
                    outcome["actual_pnl_pct"] = (take_profit - entry_price) / entry_price * 100
                    break

                # Check if hit stop loss
                if row["low"] <= stop_loss:
                    outcome["outcome"] = "LOSS"
                    outcome["exit_price"] = stop_loss
                    outcome["exit_bars"] = i + 1
                    outcome["actual_pnl_pct"] = (stop_loss - entry_price) / entry_price * 100
                    break

                # Track max profit/loss
                profit = (row["high"] - entry_price) / entry_price * 100
                loss = (row["low"] - entry_price) / entry_price * 100
                outcome["max_profit_pct"] = max(outcome["max_profit_pct"], profit)
                outcome["max_loss_pct"] = min(outcome["max_loss_pct"], loss)

            else:  # SELL signal
                # Check if hit take profit (price goes down)
                if row["low"] <= take_profit:
                    outcome["outcome"] = "WIN"
                    outcome["exit_price"] = take_profit
                    outcome["exit_bars"] = i + 1
                    outcome["actual_pnl_pct"] = (entry_price - take_profit) / entry_price * 100
                    break

                # Check if hit stop loss (price goes up)
                if row["high"] >= stop_loss:
                    outcome["outcome"] = "LOSS"
                    outcome["exit_price"] = stop_loss
                    outcome["exit_bars"] = i + 1
                    outcome["actual_pnl_pct"] = (entry_price - stop_loss) / entry_price * 100
                    break

                # Track max profit/loss
                profit = (entry_price - row["low"]) / entry_price * 100
                loss = (entry_price - row["high"]) / entry_price * 100
                outcome["max_profit_pct"] = max(outcome["max_profit_pct"], profit)
                outcome["max_loss_pct"] = min(outcome["max_loss_pct"], loss)

        # If expired, calculate final P&L
        if outcome["outcome"] == "EXPIRED" and not future_df.empty:
            last_price = future_df.iloc[min(71, len(future_df) - 1)]["close"]
            if signal == "BUY":
                outcome["actual_pnl_pct"] = (last_price - entry_price) / entry_price * 100
            else:
                outcome["actual_pnl_pct"] = (entry_price - last_price) / entry_price * 100
            outcome["exit_price"] = last_price
            outcome["exit_bars"] = min(72, len(future_df))

        return outcome

    def generate_labels(self, symbols: Optional[List[str]] = None):
        """Generate labels for specified symbols"""
        if symbols is None:
            # Use top liquid symbols with good data
            symbols = [
                "BTC",
                "ETH",
                "SOL",
                "XRP",
                "ADA",
                "AVAX",
                "DOGE",
                "DOT",
                "LINK",
                "UNI",
                "ATOM",
                "NEAR",
                "ARB",
                "OP",
                "AAVE",
                "CRV",
                "MKR",
                "LDO",
                "INJ",
                "SEI",
                "RUNE",
                "IMX",
            ]

        all_labels = []

        logger.info(f"Generating simple channel/range labels for {len(symbols)} symbols...")

        for symbol in symbols:
            logger.info(f"Processing {symbol}...")

            # Fetch OHLC data
            df = self.fetch_ohlc_data(symbol)

            if df.empty:
                continue

            # Detect patterns
            setups = self.detect_range_patterns(symbol, df)

            if setups:
                wins = sum(1 for s in setups if s["outcome"] == "WIN")
                losses = sum(1 for s in setups if s["outcome"] == "LOSS")
                expired = sum(1 for s in setups if s["outcome"] == "EXPIRED")

                win_rate = wins / len(setups) * 100 if setups else 0

                logger.info(f"  Found {len(setups)} range setups for {symbol}")
                logger.info(f"  Outcomes: {wins} wins, {losses} losses, {expired} expired")
                logger.info(f"  Win rate: {win_rate:.1f}%")

                # Analyze by signal type
                buy_setups = [s for s in setups if s["signal"] == "BUY"]
                sell_setups = [s for s in setups if s["signal"] == "SELL"]

                if buy_setups:
                    buy_wins = sum(1 for s in buy_setups if s["outcome"] == "WIN")
                    buy_wr = buy_wins / len(buy_setups) * 100
                    logger.info(f"    BUY signals: {len(buy_setups)} setups, {buy_wr:.1f}% win rate")

                if sell_setups:
                    sell_wins = sum(1 for s in sell_setups if s["outcome"] == "WIN")
                    sell_wr = sell_wins / len(sell_setups) * 100
                    logger.info(f"    SELL signals: {len(sell_setups)} setups, {sell_wr:.1f}% win rate")

                all_labels.extend(setups)

        # Save labels
        output_file = "data/channel_labels.json"
        with open(output_file, "w") as f:
            json.dump(
                {
                    "generated_at": datetime.now().isoformat(),
                    "total_setups": len(all_labels),
                    "symbols": symbols,
                    "labels": all_labels,
                },
                f,
                indent=2,
                default=str,
            )

        logger.info(f"\nSaved {len(all_labels)} channel/range labels to {output_file}")

        # Overall statistics
        if all_labels:
            total_wins = sum(1 for s in all_labels if s["outcome"] == "WIN")
            total_losses = sum(1 for s in all_labels if s["outcome"] == "LOSS")
            overall_wr = total_wins / len(all_labels) * 100

            logger.info(f"\nOverall Statistics:")
            logger.info(f"  Total setups: {len(all_labels)}")
            logger.info(f"  Win rate: {overall_wr:.1f}%")
            logger.info(f"  Wins: {total_wins}, Losses: {total_losses}")

            # Average metrics
            avg_rr = np.mean([s["risk_reward"] for s in all_labels])
            avg_range = np.mean([s["range_width"] for s in all_labels]) * 100

            logger.info(f"  Avg risk/reward: {avg_rr:.2f}")
            logger.info(f"  Avg range width: {avg_range:.1f}%")

            # By signal type
            buy_labels = [s for s in all_labels if s["signal"] == "BUY"]
            sell_labels = [s for s in all_labels if s["signal"] == "SELL"]

            if buy_labels:
                buy_wins = sum(1 for s in buy_labels if s["outcome"] == "WIN")
                buy_wr = buy_wins / len(buy_labels) * 100
                logger.info(f"  BUY signals: {len(buy_labels)} total, {buy_wr:.1f}% win rate")

            if sell_labels:
                sell_wins = sum(1 for s in sell_labels if s["outcome"] == "WIN")
                sell_wr = sell_wins / len(sell_labels) * 100
                logger.info(f"  SELL signals: {len(sell_labels)} total, {sell_wr:.1f}% win rate")


def main():
    generator = SimpleChannelLabelGenerator()
    generator.generate_labels()


if __name__ == "__main__":
    main()
