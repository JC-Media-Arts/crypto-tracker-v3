#!/usr/bin/env python3
"""
Generate training labels for Channel Trading Strategy
Identifies historical channel patterns and their outcomes
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
from src.strategies.channel.detector import ChannelDetector, Channel

# Configure logger
logger.add("logs/channel_label_generation.log", rotation="10 MB")


class ChannelLabelGenerator:
    """Generate training labels for Channel ML model"""

    def __init__(self):
        self.supabase = SupabaseClient()
        self.detector = ChannelDetector(
            {
                "min_touches": 2,
                "lookback_periods": 50,  # Reduced from 100
                "touch_tolerance": 0.005,  # Increased from 0.3% to 0.5%
                "min_channel_width": 0.01,  # Reduced from 2% to 1%
                "max_channel_width": 0.20,  # Increased from 15% to 20%
                "buy_zone": 0.30,  # Bottom 30%
                "sell_zone": 0.70,  # Top 30%
            }
        )

        # Outcome parameters
        self.min_hold_hours = 4
        self.max_hold_hours = 72

        # Risk/reward thresholds
        self.min_risk_reward = 1.5

    def fetch_ohlc_data(self, symbol: str, lookback_days: int = 180) -> List[Dict]:
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
                logger.info(f"Fetched {len(response.data)} bars for {symbol}")
                return response.data
            else:
                logger.warning(f"No data found for {symbol}")
                return []

        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return []

    def detect_channel_setups(self, symbol: str, ohlc_data: List[Dict]) -> List[Dict]:
        """Detect all channel setups in historical data"""
        setups = []

        if len(ohlc_data) < self.detector.lookback_periods + 100:
            logger.warning(f"Insufficient data for {symbol}")
            return setups

        # Slide through history looking for channels
        for i in range(self.detector.lookback_periods, len(ohlc_data) - 100):
            # Get window of data
            window_data = ohlc_data[i - self.detector.lookback_periods : i]

            # Convert to format expected by detector (most recent first)
            window_reversed = list(reversed(window_data))

            # Detect channel
            channel = self.detector.detect_channel(symbol, window_reversed)

            if channel and channel.is_valid:
                # Get trading signal
                signal = self.detector.get_trading_signal(channel)

                if signal:
                    current_price = window_data[-1]["close"]
                    targets = self.detector.calculate_targets(
                        channel, current_price, signal
                    )

                    # Check risk/reward
                    if targets.get("risk_reward", 0) >= self.min_risk_reward:
                        setup = {
                            "symbol": symbol,
                            "timestamp": window_data[-1]["timestamp"],
                            "channel_type": channel.channel_type,
                            "channel_width": channel.width,
                            "channel_strength": channel.strength,
                            "position_in_channel": channel.current_position,
                            "signal": signal,
                            "entry_price": current_price,
                            "upper_line": channel.upper_line,
                            "lower_line": channel.lower_line,
                            "take_profit": targets["take_profit"],
                            "stop_loss": targets["stop_loss"],
                            "risk_reward": targets["risk_reward"],
                            "touches_upper": channel.touches_upper,
                            "touches_lower": channel.touches_lower,
                            "features": self._extract_features(window_data, channel),
                        }

                        # Calculate outcome
                        outcome = self._calculate_outcome(
                            setup, ohlc_data[i : i + 100]  # Look forward 100 bars
                        )
                        setup.update(outcome)

                        setups.append(setup)

        return setups

    def _extract_features(self, window_data: List[Dict], channel: Channel) -> Dict:
        """Extract features for ML training"""
        # Calculate additional features
        prices = [d["close"] for d in window_data]
        volumes = [d["volume"] for d in window_data]

        # Price features
        price_volatility = np.std(prices) / np.mean(prices)
        price_trend = (prices[-1] - prices[0]) / prices[0]

        # Volume features
        volume_avg = np.mean(volumes)
        volume_trend = (
            (np.mean(volumes[-10:]) - np.mean(volumes[:10])) / volume_avg
            if volume_avg > 0
            else 0
        )

        # Channel features
        channel_age = len(window_data) / self.detector.lookback_periods
        total_touches = channel.touches_upper + channel.touches_lower

        return {
            "channel_width": channel.width,
            "channel_strength": channel.strength,
            "position_in_channel": channel.current_position,
            "channel_slope": channel.slope,
            "touches_upper": channel.touches_upper,
            "touches_lower": channel.touches_lower,
            "total_touches": total_touches,
            "price_volatility": price_volatility,
            "price_trend": price_trend,
            "volume_trend": volume_trend,
            "channel_age": channel_age,
        }

    def _calculate_outcome(self, setup: Dict, future_data: List[Dict]) -> Dict:
        """Calculate the outcome of a channel trade"""
        entry_price = setup["entry_price"]
        take_profit = setup["take_profit"]
        stop_loss = setup["stop_loss"]
        signal = setup["signal"]

        outcome = {
            "outcome": "EXPIRED",
            "exit_price": entry_price,
            "exit_bars": 0,
            "max_profit": 0.0,
            "max_loss": 0.0,
            "actual_pnl": 0.0,
            "channel_held": False,
        }

        if not future_data:
            return outcome

        max_profit = 0
        max_loss = 0
        channel_breaks = 0

        for i, bar in enumerate(future_data[: self.max_hold_hours]):
            high = bar["high"]
            low = bar["low"]
            close = bar["close"]

            if signal == "BUY":
                # Long position
                profit = (high - entry_price) / entry_price * 100
                loss = (low - entry_price) / entry_price * 100

                max_profit = max(max_profit, profit)
                max_loss = min(max_loss, loss)

                # Check take profit
                if high >= take_profit:
                    outcome["outcome"] = "WIN"
                    outcome["exit_price"] = take_profit
                    outcome["exit_bars"] = i + 1
                    outcome["actual_pnl"] = (
                        (take_profit - entry_price) / entry_price * 100
                    )
                    break

                # Check stop loss
                if low <= stop_loss:
                    outcome["outcome"] = "LOSS"
                    outcome["exit_price"] = stop_loss
                    outcome["exit_bars"] = i + 1
                    outcome["actual_pnl"] = (
                        (stop_loss - entry_price) / entry_price * 100
                    )
                    break

                # Check if price breaks channel
                if (
                    close > setup["upper_line"] * 1.02
                    or close < setup["lower_line"] * 0.98
                ):
                    channel_breaks += 1
                    if channel_breaks >= 3:  # Channel broken
                        outcome["channel_held"] = False
                        break

            else:  # SELL signal (short)
                # Short position
                profit = (entry_price - low) / entry_price * 100
                loss = (entry_price - high) / entry_price * 100

                max_profit = max(max_profit, profit)
                max_loss = min(max_loss, loss)

                # Check take profit (price goes down)
                if low <= take_profit:
                    outcome["outcome"] = "WIN"
                    outcome["exit_price"] = take_profit
                    outcome["exit_bars"] = i + 1
                    outcome["actual_pnl"] = (
                        (entry_price - take_profit) / entry_price * 100
                    )
                    break

                # Check stop loss (price goes up)
                if high >= stop_loss:
                    outcome["outcome"] = "LOSS"
                    outcome["exit_price"] = stop_loss
                    outcome["exit_bars"] = i + 1
                    outcome["actual_pnl"] = (
                        (entry_price - stop_loss) / entry_price * 100
                    )
                    break

        outcome["max_profit"] = max_profit
        outcome["max_loss"] = max_loss
        outcome["channel_held"] = channel_breaks < 3

        # If no exit triggered, calculate time exit
        if outcome["outcome"] == "EXPIRED" and future_data:
            last_price = future_data[
                min(self.max_hold_hours - 1, len(future_data) - 1)
            ]["close"]
            if signal == "BUY":
                outcome["actual_pnl"] = (last_price - entry_price) / entry_price * 100
            else:
                outcome["actual_pnl"] = (entry_price - last_price) / entry_price * 100
            outcome["exit_price"] = last_price
            outcome["exit_bars"] = min(self.max_hold_hours, len(future_data))

        return outcome

    def generate_labels(self, symbols: Optional[List[str]] = None):
        """Generate labels for specified symbols"""
        if symbols is None:
            # Use top liquid symbols
            symbols = [
                "BTC",
                "ETH",
                "SOL",
                "BNB",
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

        logger.info(f"Generating channel labels for {len(symbols)} symbols...")

        for symbol in symbols:
            logger.info(f"Processing {symbol}...")

            # Fetch OHLC data
            ohlc_data = self.fetch_ohlc_data(symbol)

            if not ohlc_data:
                continue

            # Detect setups
            setups = self.detect_channel_setups(symbol, ohlc_data)

            if setups:
                wins = sum(1 for s in setups if s["outcome"] == "WIN")
                losses = sum(1 for s in setups if s["outcome"] == "LOSS")
                expired = sum(1 for s in setups if s["outcome"] == "EXPIRED")

                win_rate = wins / len(setups) * 100 if setups else 0

                logger.info(f"  Found {len(setups)} setups for {symbol}")
                logger.info(
                    f"  Outcomes: {wins} wins, {losses} losses, {expired} expired"
                )
                logger.info(f"  Win rate: {win_rate:.1f}%")

                # Analyze by channel type
                for channel_type in ["HORIZONTAL", "ASCENDING", "DESCENDING"]:
                    type_setups = [
                        s for s in setups if s["channel_type"] == channel_type
                    ]
                    if type_setups:
                        type_wins = sum(1 for s in type_setups if s["outcome"] == "WIN")
                        type_wr = type_wins / len(type_setups) * 100
                        logger.info(
                            f"    {channel_type}: {len(type_setups)} setups, {type_wr:.1f}% win rate"
                        )

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

        logger.info(f"\nSaved {len(all_labels)} channel labels to {output_file}")

        # Overall statistics
        if all_labels:
            total_wins = sum(1 for s in all_labels if s["outcome"] == "WIN")
            total_losses = sum(1 for s in all_labels if s["outcome"] == "LOSS")
            overall_wr = total_wins / len(all_labels) * 100

            logger.info(f"\nOverall Statistics:")
            logger.info(f"  Total setups: {len(all_labels)}")
            logger.info(f"  Win rate: {overall_wr:.1f}%")
            logger.info(
                f"  Avg risk/reward: {np.mean([s['risk_reward'] for s in all_labels]):.2f}"
            )

            # By channel type
            for channel_type in ["HORIZONTAL", "ASCENDING", "DESCENDING"]:
                type_setups = [
                    s for s in all_labels if s["channel_type"] == channel_type
                ]
                if type_setups:
                    type_wins = sum(1 for s in type_setups if s["outcome"] == "WIN")
                    type_wr = type_wins / len(type_setups) * 100
                    logger.info(
                        f"  {channel_type}: {len(type_setups)} setups, {type_wr:.1f}% win rate"
                    )


def main():
    generator = ChannelLabelGenerator()
    generator.generate_labels()


if __name__ == "__main__":
    main()
