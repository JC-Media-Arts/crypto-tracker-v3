#!/usr/bin/env python3
"""
Simulate Trading with Recommended Threshold Changes
Tests what would happen with the new thresholds on the last 14 days of data
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # noqa: E402

import pandas as pd  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402
from src.data.supabase_client import SupabaseClient  # noqa: E402
import json  # noqa: E402


class ThresholdSimulator:
    def __init__(self):
        self.db = SupabaseClient()
        self.start_date = (datetime.now() - timedelta(days=14)).isoformat()
        self.end_date = datetime.now().isoformat()

        # Current thresholds
        self.current_thresholds = {
            "SWING": {
                "breakout_threshold": 1.02,
                "volume_spike": 2.0,
                "rsi_min": 50,
                "rsi_max": 70,
                "min_score": 50,
            },
            "CHANNEL": {
                "buy_zone": 0.25,
                "sell_zone": 0.75,
                "min_touches": 2,
                "min_confidence": 0.55,
                "channel_strength": 0.6,
            },
            "DCA": {"drop_threshold": -5.0, "volume_requirement": 1.0},
        }

        # Recommended thresholds
        self.new_thresholds = {
            "SWING": {
                "breakout_threshold": 1.015,
                "volume_spike": 1.5,
                "rsi_min": 45,
                "rsi_max": 75,
                "min_score": 40,
            },
            "CHANNEL": {
                "buy_zone": 0.15,
                "sell_zone": 0.85,
                "min_touches": 3,
                "min_confidence": 0.65,
                "channel_strength": 0.7,
            },
            "DCA": {"drop_threshold": -3.0, "volume_requirement": 0.7},
        }

    def get_ohlc_data(self, symbol, timeframe="15min"):
        """Get OHLC data for a symbol"""
        ohlc = (
            self.db.client.table("ohlc_recent")
            .select("*")
            .eq("symbol", symbol)
            .eq("timeframe", timeframe)
            .gte("timestamp", self.start_date)
            .lte("timestamp", self.end_date)
            .order("timestamp")
            .execute()
        )
        if ohlc.data:
            df = pd.DataFrame(ohlc.data)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            return df
        return pd.DataFrame()

    def get_all_symbols(self):
        """Get all symbols with recent data"""
        # Get distinct symbols from paper_trades first
        result = (
            self.db.client.table("paper_trades")
            .select("symbol")
            .gte("created_at", self.start_date)
            .execute()
        )

        traded_symbols = []
        if result.data:
            traded_symbols = list(set([r["symbol"] for r in result.data]))

        # If we have traded symbols, use those
        if traded_symbols:
            return traded_symbols[:30]

        # Otherwise, use a default list of active symbols
        return [
            "BTC",
            "ETH",
            "SOL",
            "BNB",
            "XRP",
            "ADA",
            "AVAX",
            "DOGE",
            "MATIC",
            "DOT",
            "LINK",
            "UNI",
            "ATOM",
            "LTC",
            "BCH",
            "XLM",
            "NEAR",
            "ICP",
            "FIL",
            "APT",
            "ARB",
            "OP",
            "INJ",
            "SEI",
        ]

    def simulate_swing_signals(self, symbols):
        """Simulate SWING signals with new thresholds"""
        signals = []

        for symbol in symbols:
            df = self.get_ohlc_data(symbol)
            if df.empty or len(df) < 50:
                continue

            # Calculate indicators
            df["sma_20"] = df["close"].rolling(window=20).mean()
            df["sma_50"] = df["close"].rolling(window=50).mean()
            df["volume_avg"] = df["volume"].rolling(window=20).mean()
            df["rsi"] = self.calculate_rsi(df["close"])

            # Find resistance levels (20-period high)
            df["resistance"] = df["high"].rolling(window=20).max()

            # Check for breakouts with NEW thresholds
            for i in range(50, len(df)):
                current = df.iloc[i]
                prev = df.iloc[i - 1]

                # Breakout detection with new threshold
                if (
                    current["close"]
                    > prev["resistance"]
                    * self.new_thresholds["SWING"]["breakout_threshold"]
                ):
                    # Volume confirmation with new threshold
                    if (
                        current["volume"]
                        > current["volume_avg"]
                        * self.new_thresholds["SWING"]["volume_spike"]
                    ):
                        # RSI check with new range
                        if (
                            self.new_thresholds["SWING"]["rsi_min"]
                            < current["rsi"]
                            < self.new_thresholds["SWING"]["rsi_max"]
                        ):
                            # Trend alignment
                            if current["close"] > current["sma_20"] > current["sma_50"]:
                                # Calculate score (simplified)
                                score = 0
                                score += 30  # Breakout
                                score += (
                                    20
                                    if current["volume"] > current["volume_avg"] * 2
                                    else 10
                                )
                                score += 20 if current["rsi"] > 50 else 10

                                if score >= self.new_thresholds["SWING"]["min_score"]:
                                    signals.append(
                                        {
                                            "symbol": symbol,
                                            "timestamp": current["timestamp"],
                                            "price": current["close"],
                                            "type": "BREAKOUT",
                                            "score": score,
                                        }
                                    )

        return signals

    def simulate_channel_signals(self, symbols):
        """Simulate CHANNEL signals with new thresholds"""
        signals = []

        for symbol in symbols:
            df = self.get_ohlc_data(symbol)
            if df.empty or len(df) < 100:
                continue

            # Simple channel detection (using Bollinger Bands as proxy)
            df["sma"] = df["close"].rolling(window=20).mean()
            df["std"] = df["close"].rolling(window=20).std()
            df["upper_band"] = df["sma"] + (df["std"] * 2)
            df["lower_band"] = df["sma"] - (df["std"] * 2)

            # Calculate position in channel
            df["channel_position"] = (df["close"] - df["lower_band"]) / (
                df["upper_band"] - df["lower_band"]
            )
            df["channel_position"] = df["channel_position"].clip(0, 1)

            # Count touches (simplified)
            touches_upper = 0
            touches_lower = 0
            for i in range(20, len(df)):
                if df.iloc[i]["high"] >= df.iloc[i]["upper_band"] * 0.98:
                    touches_upper += 1
                if df.iloc[i]["low"] <= df.iloc[i]["lower_band"] * 1.02:
                    touches_lower += 1

            # Apply NEW thresholds
            min_touches = self.new_thresholds["CHANNEL"]["min_touches"]

            if touches_upper >= min_touches and touches_lower >= min_touches:
                # Channel is valid, check for signals
                for i in range(100, len(df)):
                    current = df.iloc[i]

                    # Calculate confidence (simplified)
                    channel_width = (
                        current["upper_band"] - current["lower_band"]
                    ) / current["sma"]
                    strength = min(1.0, (touches_upper + touches_lower) / 10)

                    # Apply new strength requirement
                    if strength < self.new_thresholds["CHANNEL"]["channel_strength"]:
                        continue

                    confidence = (
                        0.5 + (strength * 0.3) + (0.2 if channel_width > 0.02 else 0)
                    )

                    # Check confidence threshold
                    if confidence < self.new_thresholds["CHANNEL"]["min_confidence"]:
                        continue

                    # Buy signal with new zone
                    if (
                        current["channel_position"]
                        <= self.new_thresholds["CHANNEL"]["buy_zone"]
                    ):
                        signals.append(
                            {
                                "symbol": symbol,
                                "timestamp": current["timestamp"],
                                "price": current["close"],
                                "type": "BUY",
                                "position": current["channel_position"],
                                "confidence": confidence,
                            }
                        )

                    # Sell signal with new zone
                    elif (
                        current["channel_position"]
                        >= self.new_thresholds["CHANNEL"]["sell_zone"]
                    ):
                        signals.append(
                            {
                                "symbol": symbol,
                                "timestamp": current["timestamp"],
                                "price": current["close"],
                                "type": "SELL",
                                "position": current["channel_position"],
                                "confidence": confidence,
                            }
                        )

        return signals

    def simulate_dca_signals(self, symbols):
        """Simulate DCA signals with new thresholds"""
        signals = []

        for symbol in symbols:
            df = self.get_ohlc_data(symbol)
            if df.empty or len(df) < 20:
                continue

            # Calculate metrics
            df["high_4h"] = df["high"].rolling(window=16).max()  # 16 * 15min = 4 hours
            df["drop_pct"] = ((df["close"] - df["high_4h"]) / df["high_4h"]) * 100
            df["volume_avg"] = df["volume"].rolling(window=20).mean()
            df["volume_ratio"] = df["volume"] / df["volume_avg"]

            # Check for DCA opportunities with NEW thresholds
            for i in range(16, len(df)):
                current = df.iloc[i]

                # Check drop threshold
                if current["drop_pct"] <= self.new_thresholds["DCA"]["drop_threshold"]:
                    # Check volume requirement
                    if (
                        current["volume_ratio"]
                        >= self.new_thresholds["DCA"]["volume_requirement"]
                    ):
                        signals.append(
                            {
                                "symbol": symbol,
                                "timestamp": current["timestamp"],
                                "price": current["close"],
                                "drop_pct": current["drop_pct"],
                                "volume_ratio": current["volume_ratio"],
                            }
                        )

        return signals

    def calculate_rsi(self, prices, period=14):
        """Calculate RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def run_simulation(self):
        """Run complete simulation with new thresholds"""
        print("=" * 80)
        print("THRESHOLD CHANGE SIMULATION")
        print(f"Period: {self.start_date[:10]} to {self.end_date[:10]}")
        print("=" * 80)

        # Get symbols to analyze
        print("\n📊 Loading symbols...")
        symbols = self.get_all_symbols()
        print(f"Analyzing {len(symbols)} symbols")

        # Simulate each strategy
        print("\n🔄 Simulating with NEW thresholds...")

        # SWING simulation
        print("\n" + "-" * 40)
        print("SWING STRATEGY SIMULATION")
        print("-" * 40)
        swing_signals = self.simulate_swing_signals(symbols)

        # Group by day
        swing_df = pd.DataFrame(swing_signals)
        if not swing_df.empty:
            swing_df["date"] = pd.to_datetime(swing_df["timestamp"]).dt.date
            signals_per_day = swing_df.groupby("date").size()

            print(
                f"✅ Potential SWING signals with new thresholds: {len(swing_signals)}"
            )
            print(f"   Average per day: {signals_per_day.mean():.1f}")
            print(f"   Days with signals: {len(signals_per_day)}/14")
            print(
                f"   Top symbols: {', '.join(swing_df['symbol'].value_counts().head(5).index)}"
            )
        else:
            print("❌ Still no SWING signals even with new thresholds")
            print("   Consider even looser thresholds or check market conditions")

        # CHANNEL simulation
        print("\n" + "-" * 40)
        print("CHANNEL STRATEGY SIMULATION")
        print("-" * 40)
        channel_signals = self.simulate_channel_signals(symbols)

        channel_df = pd.DataFrame(channel_signals)
        if not channel_df.empty:
            channel_df["date"] = pd.to_datetime(channel_df["timestamp"]).dt.date
            signals_per_day = channel_df.groupby("date").size()

            print(
                f"✅ Potential CHANNEL signals with new thresholds: {len(channel_signals)}"
            )
            print(f"   Average per day: {signals_per_day.mean():.1f}")
            print(f"   Days with signals: {len(signals_per_day)}/14")

            # Compare with current
            reduction = ((1000 - len(channel_signals)) / 1000) * 100
            print(
                f"   Reduction from current: {reduction:.1f}% (1000 → {len(channel_signals)})"
            )

            # Signal distribution
            buy_signals = len(channel_df[channel_df["type"] == "BUY"])
            sell_signals = len(channel_df[channel_df["type"] == "SELL"])
            print(f"   Buy/Sell ratio: {buy_signals}/{sell_signals}")
        else:
            print("❌ No CHANNEL signals with new thresholds (too restrictive)")

        # DCA simulation
        print("\n" + "-" * 40)
        print("DCA STRATEGY SIMULATION")
        print("-" * 40)
        dca_signals = self.simulate_dca_signals(symbols)

        dca_df = pd.DataFrame(dca_signals)
        if not dca_df.empty:
            dca_df["date"] = pd.to_datetime(dca_df["timestamp"]).dt.date
            signals_per_day = dca_df.groupby("date").size()

            print(f"✅ Potential DCA signals with new thresholds: {len(dca_signals)}")
            print(f"   Average per day: {signals_per_day.mean():.1f}")
            print(f"   Days with signals: {len(signals_per_day)}/14")

            # Compare with current
            increase = ((len(dca_signals) - 16) / 16) * 100 if 16 > 0 else 0
            print(
                f"   Increase from current: {increase:.1f}% (16 → {len(dca_signals)})"
            )

            # Average drop percentage
            avg_drop = dca_df["drop_pct"].mean()
            print(f"   Average drop when triggered: {avg_drop:.1f}%")
        else:
            print("❌ No DCA signals with new thresholds")

        # Summary comparison
        print("\n" + "=" * 80)
        print("COMPARISON SUMMARY")
        print("=" * 80)

        total_new_signals = len(swing_signals) + len(channel_signals) + len(dca_signals)

        print("\n📊 Signal Distribution:")
        print("                  Current    →    Simulated    (Change)")
        print(
            f"  SWING:          0              {len(swing_signals):4d}         (+{len(swing_signals)})"
        )
        print(
            f"  CHANNEL:        1000           {len(channel_signals):4d}         ({len(channel_signals)-1000:+d})"
        )
        print(
            f"  DCA:            16             {len(dca_signals):4d}         ({len(dca_signals)-16:+d})"
        )
        print(
            f"  TOTAL:          1016           {total_new_signals:4d}         ({total_new_signals-1016:+d})"
        )

        # Balance assessment
        print("\n⚖️ Balance Assessment:")
        if total_new_signals > 0:
            swing_pct = (len(swing_signals) / total_new_signals) * 100
            channel_pct = (len(channel_signals) / total_new_signals) * 100
            dca_pct = (len(dca_signals) / total_new_signals) * 100

            print(f"  SWING:    {swing_pct:.1f}% of total signals")
            print(f"  CHANNEL:  {channel_pct:.1f}% of total signals")
            print(f"  DCA:      {dca_pct:.1f}% of total signals")

            if channel_pct < 70:
                print("\n✅ Much better balance! CHANNEL no longer dominating")
            if swing_pct > 5:
                print("✅ SWING strategy now active")
            if dca_pct > 5:
                print("✅ DCA strategy more active")

        # Save results
        results = {
            "simulation_date": datetime.now().isoformat(),
            "period": "14 days",
            "results": {
                "SWING": {
                    "current_trades": 0,
                    "simulated_signals": len(swing_signals),
                    "change": len(swing_signals),
                },
                "CHANNEL": {
                    "current_trades": 1000,
                    "simulated_signals": len(channel_signals),
                    "change": len(channel_signals) - 1000,
                },
                "DCA": {
                    "current_trades": 16,
                    "simulated_signals": len(dca_signals),
                    "change": len(dca_signals) - 16,
                },
            },
            "thresholds_used": self.new_thresholds,
        }

        with open("data/threshold_simulation_results.json", "w") as f:
            json.dump(results, f, indent=2)

        print("\n💾 Simulation results saved to data/threshold_simulation_results.json")

        return results


def main():
    simulator = ThresholdSimulator()
    simulator.run_simulation()

    print("\n" + "=" * 80)
    print("SIMULATION COMPLETE")
    print("=" * 80)
    print("\nThe simulation shows what would happen with the recommended thresholds.")
    print(
        "Review the results above to decide if you want to proceed with implementation."
    )


if __name__ == "__main__":
    main()
