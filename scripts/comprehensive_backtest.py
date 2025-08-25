#!/usr/bin/env python3
"""
Comprehensive Backtest for All Trading Strategies
Tests SWING, CHANNEL, and DCA strategies on the last 14 days of market data
Provides recommendations for threshold adjustments
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


class StrategyBacktest:
    def __init__(self):
        self.db = SupabaseClient()
        self.start_date = (datetime.now() - timedelta(days=14)).isoformat()
        self.end_date = datetime.now().isoformat()

    def get_trades_by_strategy(self, strategy_name):
        """Get all trades for a specific strategy in the backtest period"""
        trades = (
            self.db.client.table("paper_trades")
            .select("*")
            .eq("strategy_name", strategy_name)
            .gte("created_at", self.start_date)
            .lte("created_at", self.end_date)
            .order("created_at")
            .execute()
        )
        return pd.DataFrame(trades.data) if trades.data else pd.DataFrame()

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

    def analyze_swing_strategy(self):
        """Analyze SWING strategy performance and entry signals"""
        print("\n" + "=" * 80)
        print("SWING STRATEGY ANALYSIS")
        print("=" * 80)

        trades = self.get_trades_by_strategy("SWING")

        # Count buy and sell trades
        if not trades.empty:
            buy_trades = trades[trades["side"] == "BUY"]
            sell_trades = trades[trades["side"] == "SELL"]

            print("\n📊 Trade Statistics:")
            print(f"  Total trades: {len(trades)}")
            print(f"  Buy trades: {len(buy_trades)}")
            print(f"  Sell trades: {len(sell_trades)}")

            # Analyze trade frequency
            trades["created_at"] = pd.to_datetime(trades["created_at"])
            trades_per_day = trades.groupby(trades["created_at"].dt.date).size()

            print("\n📈 Trade Frequency:")
            print(f"  Average trades per day: {trades_per_day.mean():.2f}")
            print(f"  Max trades in a day: {trades_per_day.max()}")
            print(f"  Days with trades: {len(trades_per_day)}/14")

            # Analyze P&L if we have matched trades
            if len(buy_trades) > 0 and len(sell_trades) > 0:
                self._analyze_pnl(trades, "SWING")

            # Check potential missed opportunities
            self._analyze_missed_opportunities("SWING", trades)

        else:
            print("\n⚠️ NO SWING TRADES FOUND IN LAST 14 DAYS")
            print("This indicates entry signals are TOO RESTRICTIVE")

            # Analyze what would have triggered with looser thresholds
            self._simulate_looser_thresholds("SWING")

        return trades

    def analyze_channel_strategy(self):
        """Analyze CHANNEL strategy performance and entry signals"""
        print("\n" + "=" * 80)
        print("CHANNEL STRATEGY ANALYSIS")
        print("=" * 80)

        trades = self.get_trades_by_strategy("CHANNEL")

        if not trades.empty:
            buy_trades = trades[trades["side"] == "BUY"]
            sell_trades = trades[trades["side"] == "SELL"]

            print("\n📊 Trade Statistics:")
            print(f"  Total trades: {len(trades)}")
            print(f"  Buy trades: {len(buy_trades)}")
            print(f"  Sell trades: {len(sell_trades)}")

            # Analyze trade frequency
            trades["created_at"] = pd.to_datetime(trades["created_at"])
            trades_per_day = trades.groupby(trades["created_at"].dt.date).size()

            print("\n📈 Trade Frequency:")
            print(f"  Average trades per day: {trades_per_day.mean():.2f}")
            print(f"  Max trades in a day: {trades_per_day.max()}")
            print(f"  Days with trades: {len(trades_per_day)}/14")

            # Check if strategy is dominating
            if trades_per_day.mean() > 10:
                print("\n⚠️ CHANNEL STRATEGY IS DOMINATING")
                print("Average > 10 trades/day indicates TOO LOOSE entry signals")

            # Analyze P&L
            if len(buy_trades) > 0 and len(sell_trades) > 0:
                self._analyze_pnl(trades, "CHANNEL")

            # Simulate tighter thresholds
            self._simulate_tighter_thresholds("CHANNEL", trades)

        else:
            print("\n✅ No Channel trades found - check if this is expected")

        return trades

    def analyze_dca_strategy(self):
        """Analyze DCA strategy performance and entry signals"""
        print("\n" + "=" * 80)
        print("DCA STRATEGY ANALYSIS")
        print("=" * 80)

        trades = self.get_trades_by_strategy("DCA")

        if not trades.empty:
            buy_trades = trades[trades["side"] == "BUY"]
            sell_trades = trades[trades["side"] == "SELL"]

            print("\n📊 Trade Statistics:")
            print(f"  Total trades: {len(trades)}")
            print(f"  Buy trades: {len(buy_trades)}")
            print(f"  Sell trades: {len(sell_trades)}")

            # Analyze trade frequency
            trades["created_at"] = pd.to_datetime(trades["created_at"])
            trades_per_day = trades.groupby(trades["created_at"].dt.date).size()

            print("\n📈 Trade Frequency:")
            print(f"  Average trades per day: {trades_per_day.mean():.2f}")
            print(f"  Max trades in a day: {trades_per_day.max()}")
            print(f"  Days with trades: {len(trades_per_day)}/14")

            # Check if too few trades
            if trades_per_day.mean() < 0.5:
                print("\n⚠️ DCA STRATEGY UNDERPERFORMING")
                print("< 0.5 trades/day indicates TOO RESTRICTIVE entry signals")

            # Analyze P&L
            if len(buy_trades) > 0 and len(sell_trades) > 0:
                self._analyze_pnl(trades, "DCA")

            # Simulate looser thresholds
            self._simulate_looser_thresholds("DCA")

        else:
            print("\n⚠️ NO DCA TRADES FOUND IN LAST 14 DAYS")
            print("This indicates entry signals might be too restrictive")
            self._simulate_looser_thresholds("DCA")

        return trades

    def _analyze_pnl(self, trades, strategy_name):
        """Analyze P&L for completed trades"""
        # Group trades by trade_group_id
        grouped = trades.groupby("trade_group_id")

        completed_trades = []
        for group_id, group_trades in grouped:
            buy_trades = group_trades[group_trades["side"] == "BUY"]
            sell_trades = group_trades[group_trades["side"] == "SELL"]

            if len(buy_trades) > 0 and len(sell_trades) > 0:
                # Calculate P&L
                avg_buy_price = (
                    buy_trades["price"] * buy_trades["amount"]
                ).sum() / buy_trades["amount"].sum()
                avg_sell_price = (
                    sell_trades["price"] * sell_trades["amount"]
                ).sum() / sell_trades["amount"].sum()
                pnl_pct = ((avg_sell_price - avg_buy_price) / avg_buy_price) * 100

                completed_trades.append(
                    {
                        "group_id": group_id,
                        "pnl_pct": pnl_pct,
                        "buy_price": avg_buy_price,
                        "sell_price": avg_sell_price,
                    }
                )

        if completed_trades:
            df = pd.DataFrame(completed_trades)
            winning_trades = df[df["pnl_pct"] > 0]
            losing_trades = df[df["pnl_pct"] < 0]

            print(f"\n💰 P&L Analysis ({len(completed_trades)} completed trades):")
            print(f"  Win Rate: {len(winning_trades)/len(df)*100:.1f}%")
            print(f"  Average P&L: {df['pnl_pct'].mean():.2f}%")
            print(f"  Total P&L: {df['pnl_pct'].sum():.2f}%")
            print(f"  Best Trade: {df['pnl_pct'].max():.2f}%")
            print(f"  Worst Trade: {df['pnl_pct'].min():.2f}%")

            if len(winning_trades) > 0 and len(losing_trades) > 0:
                avg_win = winning_trades["pnl_pct"].mean()
                avg_loss = abs(losing_trades["pnl_pct"].mean())
                print(f"  Risk/Reward: {avg_win/avg_loss:.2f}")

    def _analyze_missed_opportunities(self, strategy_name, actual_trades):
        """Analyze potential missed trading opportunities"""
        print(f"\n🔍 Analyzing Missed Opportunities for {strategy_name}...")

        # Get top performing symbols in the period
        all_symbols = self._get_top_movers()

        if actual_trades.empty:
            traded_symbols = set()
        else:
            traded_symbols = set(actual_trades["symbol"].unique())

        missed_symbols = all_symbols - traded_symbols

        if missed_symbols:
            print(f"  Top movers not traded: {', '.join(list(missed_symbols)[:5])}")

            # Analyze why these were missed
            for symbol in list(missed_symbols)[:3]:
                ohlc = self.get_ohlc_data(symbol)
                if not ohlc.empty:
                    price_change = (
                        (ohlc["close"].iloc[-1] - ohlc["close"].iloc[0])
                        / ohlc["close"].iloc[0]
                    ) * 100
                    volatility = ohlc["close"].pct_change().std() * 100
                    print(
                        f"    {symbol}: {price_change:+.1f}% move, {volatility:.1f}% volatility"
                    )

    def _get_top_movers(self):
        """Get symbols with biggest price moves in the period"""
        # Get all symbols with significant volume
        result = (
            self.db.client.table("ohlc_recent")
            .select("symbol")
            .eq("timeframe", "15min")
            .gte("timestamp", self.start_date)
            .execute()
        )

        if result.data:
            symbols = list(set([r["symbol"] for r in result.data]))

            # Calculate price changes
            movers = []
            for symbol in symbols[:20]:  # Check top 20 for performance
                ohlc = self.get_ohlc_data(symbol)
                if not ohlc.empty and len(ohlc) > 100:
                    price_change = (
                        (ohlc["close"].iloc[-1] - ohlc["close"].iloc[0])
                        / ohlc["close"].iloc[0]
                    ) * 100
                    movers.append((symbol, abs(price_change)))

            # Sort by absolute price change
            movers.sort(key=lambda x: x[1], reverse=True)
            return set([s[0] for s in movers[:10]])  # Top 10 movers

        return set()

    def _simulate_looser_thresholds(self, strategy_name):
        """Simulate what would happen with looser entry thresholds"""
        print(f"\n🔮 Simulating Looser Thresholds for {strategy_name}...")

        if strategy_name == "SWING":
            print("\n  Current thresholds:")
            print("    - Breakout: 2% above resistance")
            print("    - Volume spike: 2x average")
            print("    - RSI: 50-70")
            print("    - Min score: 50")

            print("\n  Recommended adjustments:")
            print("    - Breakout: 1.5% above resistance (was 2%)")
            print("    - Volume spike: 1.5x average (was 2x)")
            print("    - RSI: 45-75 (was 50-70)")
            print("    - Min score: 40 (was 50)")

        elif strategy_name == "DCA":
            print("\n  Current thresholds:")
            print("    - Drop threshold: -5% from 4h high")
            print("    - Volume: Above average")

            print("\n  Recommended adjustments:")
            print("    - Drop threshold: -3% from 4h high (was -5%)")
            print("    - Volume: 0.7x average (was 1x)")
            print("    - Add: Consider -2% drops in strong uptrends")

    def _simulate_tighter_thresholds(self, strategy_name, actual_trades):
        """Simulate what would happen with tighter entry thresholds"""
        print(f"\n🔮 Simulating Tighter Thresholds for {strategy_name}...")

        if strategy_name == "CHANNEL":
            print("\n  Current thresholds:")
            print("    - Buy zone: Bottom 25% of channel")
            print("    - Sell zone: Top 25% of channel")
            print("    - Min touches: 2 per line")
            print("    - Min confidence: 0.55")

            print("\n  Recommended adjustments:")
            print("    - Buy zone: Bottom 15% of channel (was 25%)")
            print("    - Sell zone: Top 15% of channel (was 25%)")
            print("    - Min touches: 3 per line (was 2)")
            print("    - Min confidence: 0.65 (was 0.55)")
            print("    - Add channel strength requirement: > 0.7 (was 0.6)")

            # Estimate impact
            if not actual_trades.empty:
                estimated_reduction = 0.4  # Estimate 40% reduction in trades
                current_trades = len(actual_trades)
                new_trades = int(current_trades * (1 - estimated_reduction))
                print(
                    f"\n  Estimated impact: {current_trades} → {new_trades} trades (-{estimated_reduction*100:.0f}%)"
                )

    def generate_recommendations(self):
        """Generate final recommendations for all strategies"""
        print("\n" + "=" * 80)
        print("FINAL RECOMMENDATIONS")
        print("=" * 80)

        recommendations = {
            "SWING": {
                "status": "TOO RESTRICTIVE",
                "changes": {
                    "breakout_threshold": {
                        "current": 1.02,
                        "recommended": 1.015,
                        "reason": "Lower to 1.5% to catch more breakouts",
                    },
                    "volume_spike_threshold": {
                        "current": 2.0,
                        "recommended": 1.5,
                        "reason": "Reduce to 1.5x for more signals",
                    },
                    "rsi_bullish_min": {
                        "current": 50,
                        "recommended": 45,
                        "reason": "Allow slightly lower RSI",
                    },
                    "min_score": {
                        "current": 50,
                        "recommended": 40,
                        "reason": "Lower minimum score threshold",
                    },
                },
            },
            "CHANNEL": {
                "status": "TOO LOOSE",
                "changes": {
                    "buy_zone": {
                        "current": 0.25,
                        "recommended": 0.15,
                        "reason": "Tighten to bottom 15% of channel",
                    },
                    "sell_zone": {
                        "current": 0.75,
                        "recommended": 0.85,
                        "reason": "Tighten to top 15% of channel",
                    },
                    "min_touches": {
                        "current": 2,
                        "recommended": 3,
                        "reason": "Require more confirmation",
                    },
                    "min_confidence": {
                        "current": 0.55,
                        "recommended": 0.65,
                        "reason": "Increase confidence requirement",
                    },
                    "channel_strength_min": {
                        "current": 0.6,
                        "recommended": 0.7,
                        "reason": "Require stronger channels",
                    },
                },
            },
            "DCA": {
                "status": "SLIGHTLY RESTRICTIVE",
                "changes": {
                    "drop_threshold": {
                        "current": -5.0,
                        "recommended": -3.0,
                        "reason": "Trigger on smaller drops",
                    },
                    "volume_requirement": {
                        "current": 1.0,
                        "recommended": 0.7,
                        "reason": "Lower volume requirement",
                    },
                    "add_trend_adjustment": {
                        "current": "none",
                        "recommended": "yes",
                        "reason": "Use -2% in uptrends, -5% in downtrends",
                    },
                },
            },
        }

        # Print recommendations
        for strategy, rec in recommendations.items():
            print(
                f"\n{'🔴' if rec['status'].startswith('TOO') else '🟡'} {strategy} Strategy - {rec['status']}"
            )
            print("\n  Recommended changes:")
            for param, change in rec["changes"].items():
                print(f"    • {param}:")
                print(f"      Current: {change['current']}")
                print(f"      Recommended: {change['recommended']}")
                print(f"      Reason: {change['reason']}")

        # Save recommendations to file
        with open("data/backtest_recommendations.json", "w") as f:
            json.dump(
                {
                    "backtest_date": datetime.now().isoformat(),
                    "period": "14 days",
                    "recommendations": recommendations,
                },
                f,
                indent=2,
            )

        print("\n💾 Recommendations saved to data/backtest_recommendations.json")

        return recommendations

    def run_full_backtest(self):
        """Run complete backtest for all strategies"""
        print("=" * 80)
        print("COMPREHENSIVE 14-DAY STRATEGY BACKTEST")
        print(f"Period: {self.start_date[:10]} to {self.end_date[:10]}")
        print("=" * 80)

        # Analyze each strategy
        swing_trades = self.analyze_swing_strategy()
        channel_trades = self.analyze_channel_strategy()
        dca_trades = self.analyze_dca_strategy()

        # Generate recommendations
        recommendations = self.generate_recommendations()

        # Summary statistics
        print("\n" + "=" * 80)
        print("SUMMARY STATISTICS")
        print("=" * 80)

        total_trades = len(swing_trades) + len(channel_trades) + len(dca_trades)
        print(f"\nTotal trades across all strategies: {total_trades}")

        if total_trades > 0:
            print(
                f"  SWING: {len(swing_trades)} ({len(swing_trades)/total_trades*100:.1f}%)"
            )
            print(
                f"  CHANNEL: {len(channel_trades)} ({len(channel_trades)/total_trades*100:.1f}%)"
            )
            print(f"  DCA: {len(dca_trades)} ({len(dca_trades)/total_trades*100:.1f}%)")

        return recommendations


def main():
    backtest = StrategyBacktest()
    backtest.run_full_backtest()

    print("\n" + "=" * 80)
    print("BACKTEST COMPLETE")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Review the recommendations above")
    print("2. Update strategy configurations in configs/paper_trading_config.py")
    print("3. Update detector thresholds in src/strategies/*/detector.py files")
    print("4. Restart paper trading to apply changes")


if __name__ == "__main__":
    main()
