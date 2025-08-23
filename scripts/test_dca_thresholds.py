#!/usr/bin/env python3
"""
Test DCA strategy with different drop thresholds across market cap tiers
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from dateutil import tz
import pandas as pd

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from src.strategies.dca.detector import DCADetector
from src.strategies.dca.grid import GridCalculator
from loguru import logger


class DCAThresholdTester:
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.detector = DCADetector(supabase_client)

        # Test symbols by market cap
        self.test_symbols = {
            "large_cap": "BTC",  # Bitcoin - largest cap
            "mid_cap": "AVAX",  # Avalanche - mid cap
            "small_cap": "PEPE",  # Pepe - small cap memecoin
        }

        # Test thresholds
        self.thresholds = [3.0, 5.0]

    def fetch_ohlc_data(self, symbol: str, lookback_days: int = 180):
        """Fetch OHLC data for analysis"""
        end_time = datetime.now(tz.UTC)
        start_time = end_time - timedelta(days=lookback_days)

        all_data = []
        current_start = start_time

        while current_start < end_time:
            current_end = min(current_start + timedelta(days=7), end_time)

            result = (
                self.supabase.client.table("ohlc_data")
                .select("timestamp,close,high,low,volume")
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
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp").reset_index(drop=True)
            return df
        return pd.DataFrame()

    def find_dca_setups(self, df: pd.DataFrame, threshold: float):
        """Find DCA setups with given threshold"""
        if df.empty or len(df) < 48:  # Need at least 4 hours of data
            return []

        setups = []

        # Calculate 4-hour rolling high
        df["high_4h"] = df["high"].rolling(window=16, min_periods=1).max()  # 16 * 15min = 4 hours

        # Look for drops
        i = 16  # Start after we have 4h of history
        while i < len(df):
            current_close = df.iloc[i]["close"]
            high_4h = df.iloc[i]["high_4h"]

            if pd.notna(high_4h) and high_4h > 0:
                drop_pct = ((current_close - high_4h) / high_4h) * 100

                if drop_pct <= -threshold:
                    setup = {
                        "timestamp": df.iloc[i]["timestamp"],
                        "setup_price": current_close,
                        "high_4h": high_4h,
                        "drop_pct": drop_pct,
                        "volume": df.iloc[i]["volume"],
                    }
                    setups.append(setup)

                    # Skip ahead 4 hours to avoid overlapping setups
                    i += 16
                else:
                    i += 1
            else:
                i += 1

        return setups

    def simulate_dca_outcome(
        self,
        df: pd.DataFrame,
        setup: dict,
        take_profit: float = 10.0,
        stop_loss: float = -8.0,
    ):
        """Simulate the outcome of a DCA setup"""
        setup_idx = df[df["timestamp"] == setup["timestamp"]].index[0]

        if setup_idx >= len(df) - 1:
            return "UNKNOWN"

        # Look forward up to 72 hours (288 * 15min bars)
        max_look_forward = min(288, len(df) - setup_idx - 1)

        setup_price = setup["setup_price"]
        highest_price = setup_price
        lowest_price = setup_price

        for i in range(1, max_look_forward + 1):
            current_price = df.iloc[setup_idx + i]["close"]
            highest_price = max(highest_price, current_price)
            lowest_price = min(lowest_price, current_price)

            # Check take profit
            profit_pct = ((current_price - setup_price) / setup_price) * 100
            if profit_pct >= take_profit:
                return "WIN"

            # Check stop loss
            if profit_pct <= stop_loss:
                return "LOSS"

        # Check final outcome
        final_price = df.iloc[setup_idx + max_look_forward]["close"]
        final_pct = ((final_price - setup_price) / setup_price) * 100

        if final_pct > 0:
            return "BREAKEVEN_POSITIVE"
        else:
            return "BREAKEVEN_NEGATIVE"

    def test_symbol(self, symbol: str, cap_tier: str):
        """Test a symbol with different thresholds"""
        print(f"\n{'='*60}")
        print(f"Testing {symbol} ({cap_tier})")
        print(f"{'='*60}")

        # Fetch data
        df = self.fetch_ohlc_data(symbol, lookback_days=180)

        if df.empty:
            print(f"No data available for {symbol}")
            return

        print(f"Data range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        print(f"Total bars: {len(df)}")

        # Calculate price statistics
        price_changes = df["close"].pct_change() * 100
        print(f"\nPrice Statistics (15-min bars):")
        print(f"  Max gain: {price_changes.max():.2f}%")
        print(f"  Max drop: {price_changes.min():.2f}%")
        print(f"  Volatility (std): {price_changes.std():.2f}%")

        # Test each threshold
        results = {}
        for threshold in self.thresholds:
            print(f"\n--- Testing {threshold}% drop threshold ---")

            setups = self.find_dca_setups(df, threshold)
            print(f"Found {len(setups)} setups")

            if setups:
                # Simulate outcomes
                outcomes = []
                for setup in setups:
                    outcome = self.simulate_dca_outcome(df, setup)
                    outcomes.append(outcome)
                    print(f"  {setup['timestamp']}: Drop {setup['drop_pct']:.2f}% → {outcome}")

                # Calculate statistics
                wins = outcomes.count("WIN")
                losses = outcomes.count("LOSS")
                breakeven_pos = outcomes.count("BREAKEVEN_POSITIVE")
                breakeven_neg = outcomes.count("BREAKEVEN_NEGATIVE")

                total = len(outcomes)
                win_rate = (wins / total * 100) if total > 0 else 0

                print(f"\nResults for {threshold}% threshold:")
                print(f"  Wins: {wins} ({wins/total*100:.1f}%)")
                print(f"  Losses: {losses} ({losses/total*100:.1f}%)")
                print(f"  Breakeven+: {breakeven_pos} ({breakeven_pos/total*100:.1f}%)")
                print(f"  Breakeven-: {breakeven_neg} ({breakeven_neg/total*100:.1f}%)")
                print(f"  Win Rate: {win_rate:.1f}%")

                results[threshold] = {
                    "setups": len(setups),
                    "wins": wins,
                    "losses": losses,
                    "win_rate": win_rate,
                }
            else:
                results[threshold] = {
                    "setups": 0,
                    "wins": 0,
                    "losses": 0,
                    "win_rate": 0,
                }

        return results

    def run_test(self):
        """Run the complete test"""
        print("=" * 80)
        print("DCA THRESHOLD TESTING")
        print("=" * 80)
        print(f"Testing thresholds: {self.thresholds}")
        print(f"Lookback period: 180 days")
        print(f"Take profit: 10% | Stop loss: -8%")

        all_results = {}

        for cap_tier, symbol in self.test_symbols.items():
            results = self.test_symbol(symbol, cap_tier)
            all_results[symbol] = results

        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)

        for symbol in self.test_symbols.values():
            if symbol in all_results:
                print(f"\n{symbol}:")
                for threshold, stats in all_results[symbol].items():
                    print(f"  {threshold}% threshold: {stats['setups']} setups, " f"{stats['win_rate']:.1f}% win rate")

        # Recommendations
        print("\n" + "=" * 80)
        print("RECOMMENDATIONS")
        print("=" * 80)

        for cap_tier, symbol in self.test_symbols.items():
            if symbol in all_results:
                best_threshold = None
                best_score = -1

                for threshold, stats in all_results[symbol].items():
                    # Score based on number of setups and win rate
                    if stats["setups"] > 0:
                        score = stats["setups"] * stats["win_rate"]
                        if score > best_score:
                            best_score = score
                            best_threshold = threshold

                if best_threshold:
                    print(f"{cap_tier.upper()} ({symbol}): Use {best_threshold}% threshold")
                else:
                    print(f"{cap_tier.upper()} ({symbol}): No viable threshold found")


def main():
    # Initialize
    supabase = SupabaseClient()
    tester = DCAThresholdTester(supabase)

    # Run test
    tester.run_test()


if __name__ == "__main__":
    main()
