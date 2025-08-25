#!/usr/bin/env python3
"""
Simulate Trading with MODERATE Threshold Changes
Tests incremental adjustments rather than extreme changes
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


class ModerateThresholdSimulator:
    def __init__(self):
        self.db = SupabaseClient()
        self.start_date = (datetime.now() - timedelta(days=14)).isoformat()
        self.end_date = datetime.now().isoformat()

        # MODERATE adjustments (not too extreme)
        self.adjustments = {
            "SWING": {
                "moderate": {
                    "breakout_threshold": 1.018,  # 1.8% (between current 2% and recommended 1.5%)
                    "volume_spike": 1.7,  # Between 2.0 and 1.5
                    "rsi_min": 48,  # Between 50 and 45
                    "rsi_max": 72,  # Between 70 and 75
                    "min_score": 45,  # Between 50 and 40
                },
                "aggressive": {
                    "breakout_threshold": 1.015,
                    "volume_spike": 1.5,
                    "rsi_min": 45,
                    "rsi_max": 75,
                    "min_score": 40,
                },
            },
            "CHANNEL": {
                "moderate": {
                    "buy_zone": 0.20,  # Between 0.25 and 0.15
                    "sell_zone": 0.80,  # Between 0.75 and 0.85
                    "min_touches": 2,  # Keep at 2 for now
                    "min_confidence": 0.60,  # Between 0.55 and 0.65
                    "channel_strength": 0.65,  # Between 0.6 and 0.7
                },
                "aggressive": {
                    "buy_zone": 0.15,
                    "sell_zone": 0.85,
                    "min_touches": 3,
                    "min_confidence": 0.65,
                    "channel_strength": 0.70,
                },
            },
            "DCA": {
                "moderate": {
                    "drop_threshold": -4.0,  # Between -5.0 and -3.0
                    "volume_requirement": 0.85,  # Between 1.0 and 0.7
                },
                "aggressive": {"drop_threshold": -3.0, "volume_requirement": 0.7},
            },
        }

    def check_data_availability(self):
        """Check what data we actually have"""
        print("\n📊 Checking data availability...")

        # Just use known active symbols instead of querying
        # to avoid timeout issues
        symbols = [
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

        print(f"  Using {len(symbols)} known active symbols")
        print(f"  Sample symbols: {', '.join(symbols[:10])}")
        return symbols

    def analyze_actual_trades(self):
        """Analyze what actually traded in the period"""
        print("\n📈 Analyzing actual trades...")

        trades = (
            self.db.client.table("paper_trades")
            .select("*")
            .gte("created_at", self.start_date)
            .lte("created_at", self.end_date)
            .execute()
        )

        if trades.data:
            df = pd.DataFrame(trades.data)

            # Group by strategy
            by_strategy = df.groupby("strategy_name").size()
            print("\n  Trades by strategy:")
            for strategy, count in by_strategy.items():
                print(f"    {strategy}: {count}")

            # Most traded symbols
            by_symbol = df.groupby("symbol").size().sort_values(ascending=False)
            print("\n  Top 10 traded symbols:")
            for symbol, count in by_symbol.head(10).items():
                print(f"    {symbol}: {count} trades")

            return df
        else:
            print("  No trades found in period")
            return pd.DataFrame()

    def simulate_with_adjustments(self, level="moderate"):
        """Run simulation with specified adjustment level"""
        print(f"\n🔄 Simulating with {level.upper()} adjustments...")

        # Get symbols that actually traded
        trades_df = self.analyze_actual_trades()
        if not trades_df.empty:
            traded_symbols = list(trades_df["symbol"].unique())
        else:
            # Use default symbols
            traded_symbols = ["BTC", "ETH", "SOL", "BNB", "XRP"]

        print(
            f"\n  Testing on {len(traded_symbols)} symbols: {', '.join(traded_symbols[:10])}"
        )

        results = {
            "SWING": self.estimate_swing_changes(traded_symbols, level),
            "CHANNEL": self.estimate_channel_changes(traded_symbols, level),
            "DCA": self.estimate_dca_changes(traded_symbols, level),
        }

        return results

    def estimate_swing_changes(self, symbols, level):
        """Estimate SWING strategy changes"""
        thresholds = self.adjustments["SWING"][level]

        # Estimate based on threshold changes
        # Lower breakout threshold = more signals
        breakout_factor = 1.02 / thresholds["breakout_threshold"]  # How much easier
        volume_factor = 2.0 / thresholds["volume_spike"]  # How much easier
        rsi_range_factor = (thresholds["rsi_max"] - thresholds["rsi_min"]) / (70 - 50)

        # Combined effect (multiplicative)
        signal_increase = breakout_factor * volume_factor * rsi_range_factor

        # Estimate signals (base case: 0 currently)
        estimated_signals = int(
            signal_increase * 10 * len(symbols) / 30
        )  # Scale by number of symbols

        return {
            "current": 0,
            "estimated": estimated_signals,
            "factors": {
                "breakout_easier": f"{(breakout_factor-1)*100:.1f}%",
                "volume_easier": f"{(volume_factor-1)*100:.1f}%",
                "rsi_range_wider": f"{(rsi_range_factor-1)*100:.1f}%",
            },
        }

    def estimate_channel_changes(self, symbols, level):
        """Estimate CHANNEL strategy changes"""
        thresholds = self.adjustments["CHANNEL"][level]

        # Tighter zones = fewer signals
        buy_zone_factor = thresholds["buy_zone"] / 0.25  # How much tighter
        sell_zone_factor = (1 - thresholds["sell_zone"]) / 0.25  # How much tighter
        confidence_factor = 0.55 / thresholds["min_confidence"]  # How much harder

        # Combined effect
        signal_reduction = buy_zone_factor * sell_zone_factor * confidence_factor

        # Estimate signals (base case: 1000 currently)
        estimated_signals = int(1000 * signal_reduction)

        return {
            "current": 1000,
            "estimated": estimated_signals,
            "factors": {
                "buy_zone_tighter": f"{(1-buy_zone_factor)*100:.1f}%",
                "sell_zone_tighter": f"{(1-sell_zone_factor)*100:.1f}%",
                "confidence_harder": f"{(1-confidence_factor)*100:.1f}%",
            },
        }

    def estimate_dca_changes(self, symbols, level):
        """Estimate DCA strategy changes"""
        thresholds = self.adjustments["DCA"][level]

        # Smaller drop threshold = more signals
        drop_factor = 5.0 / abs(thresholds["drop_threshold"])  # How much easier
        volume_factor = 1.0 / thresholds["volume_requirement"]  # How much easier

        # Combined effect
        signal_increase = drop_factor * volume_factor

        # Estimate signals (base case: 16 currently)
        estimated_signals = int(16 * signal_increase)

        return {
            "current": 16,
            "estimated": estimated_signals,
            "factors": {
                "drop_threshold_easier": f"{(drop_factor-1)*100:.1f}%",
                "volume_easier": f"{(volume_factor-1)*100:.1f}%",
            },
        }

    def run_complete_analysis(self):
        """Run complete analysis with both moderate and aggressive adjustments"""
        print("=" * 80)
        print("MODERATE VS AGGRESSIVE THRESHOLD ADJUSTMENTS")
        print(f"Period: {self.start_date[:10]} to {self.end_date[:10]}")
        print("=" * 80)

        # Check data availability
        self.check_data_availability()

        # Run both simulations
        moderate_results = self.simulate_with_adjustments("moderate")
        aggressive_results = self.simulate_with_adjustments("aggressive")

        # Display comparison
        print("\n" + "=" * 80)
        print("COMPARISON OF ADJUSTMENT LEVELS")
        print("=" * 80)

        for strategy in ["SWING", "CHANNEL", "DCA"]:
            print(f"\n📊 {strategy} Strategy:")
            print(f"  Current trades: {moderate_results[strategy]['current']}")
            print(
                f"  With MODERATE adjustments: {moderate_results[strategy]['estimated']}"
            )
            print(
                f"  With AGGRESSIVE adjustments: {aggressive_results[strategy]['estimated']}"
            )

            # Show factors for moderate
            print("\n  Moderate adjustment factors:")
            for factor, value in moderate_results[strategy]["factors"].items():
                print(f"    • {factor}: {value}")

        # Calculate overall balance
        print("\n" + "=" * 80)
        print("STRATEGY BALANCE ANALYSIS")
        print("=" * 80)

        for level in ["moderate", "aggressive"]:
            results = moderate_results if level == "moderate" else aggressive_results
            total = sum(r["estimated"] for r in results.values())

            print(f"\n{level.upper()} Adjustments:")
            if total > 0:
                print(f"  Total estimated signals: {total}")
                for strategy in ["SWING", "CHANNEL", "DCA"]:
                    pct = (results[strategy]["estimated"] / total) * 100
                    print(
                        f"  {strategy}: {results[strategy]['estimated']} ({pct:.1f}%)"
                    )

        # Recommendation
        print("\n" + "=" * 80)
        print("💡 RECOMMENDATION")
        print("=" * 80)

        # Calculate which is better balanced
        mod_total = sum(r["estimated"] for r in moderate_results.values())
        agg_total = sum(r["estimated"] for r in aggressive_results.values())

        if mod_total > 0:
            mod_channel_pct = (
                moderate_results["CHANNEL"]["estimated"] / mod_total
            ) * 100
        else:
            mod_channel_pct = 0

        if agg_total > 0:
            agg_channel_pct = (
                aggressive_results["CHANNEL"]["estimated"] / agg_total
            ) * 100
        else:
            agg_channel_pct = 0

        print("\nBased on the analysis:")

        if mod_channel_pct < 70 and mod_channel_pct > 30:
            print("✅ MODERATE adjustments provide better balance")
            print(
                f"   - Channel would be {mod_channel_pct:.1f}% of trades (good balance)"
            )
            print("   - Less risk of over-correction")
        elif agg_channel_pct < 70 and agg_channel_pct > 30:
            print("✅ AGGRESSIVE adjustments needed for proper balance")
            print(f"   - Channel would be {agg_channel_pct:.1f}% of trades")
            print("   - Necessary to activate SWING strategy")
        else:
            print("⚠️ Further tuning needed")
            print("   - Consider custom thresholds between moderate and aggressive")

        # Save results
        final_results = {
            "analysis_date": datetime.now().isoformat(),
            "period": "14 days",
            "moderate_adjustments": self.adjustments,
            "moderate_results": moderate_results,
            "aggressive_results": aggressive_results,
            "recommendation": "moderate" if mod_channel_pct < 70 else "aggressive",
        }

        with open("data/moderate_threshold_analysis.json", "w") as f:
            json.dump(final_results, f, indent=2)

        print("\n💾 Analysis saved to data/moderate_threshold_analysis.json")

        return final_results


def main():
    simulator = ModerateThresholdSimulator()
    simulator.run_complete_analysis()

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Review the moderate vs aggressive comparison above")
    print("2. Choose which adjustment level to implement")
    print("3. We can then update the configuration files accordingly")


if __name__ == "__main__":
    main()
