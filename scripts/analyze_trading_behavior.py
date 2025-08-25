#!/usr/bin/env python3
"""Deep analysis of trading behavior in relation to market conditions."""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import json
from typing import Dict, List, Tuple
import warnings

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.settings import get_settings
from supabase import create_client


def analyze_trading_patterns(supabase) -> Dict:
    """Analyze detailed trading patterns from the last 24 hours."""
    print("\n" + "=" * 60)
    print("📊 DETAILED TRADING PATTERN ANALYSIS")
    print("=" * 60)

    end_time = datetime.now(pytz.UTC)
    start_time = end_time - timedelta(hours=24)

    # Fetch all paper trades
    query = (
        supabase.table("paper_trades")
        .select("*")
        .gte("created_at", start_time.isoformat())
        .order("created_at")
    )

    result = query.execute()

    if not result.data:
        return {}

    trades_df = pd.DataFrame(result.data)
    trades_df["created_at"] = pd.to_datetime(trades_df["created_at"])
    trades_df["filled_at"] = pd.to_datetime(trades_df["filled_at"])

    # Analyze by symbol
    print("\n📈 Top Traded Symbols:")
    symbol_stats = (
        trades_df.groupby("symbol")
        .agg(
            {
                "trade_id": "count",
                "pnl": ["mean", "sum", "std"],
                "status": lambda x: (x == "CLOSED").sum(),
            }
        )
        .round(2)
    )
    symbol_stats.columns = ["trades", "avg_pnl", "total_pnl", "pnl_std", "closed"]
    symbol_stats["win_rate"] = (
        trades_df[trades_df["status"] == "CLOSED"]
        .groupby("symbol")["pnl"]
        .apply(lambda x: (x > 0).mean() * 100 if len(x) > 0 else 0)
        .round(1)
    )
    symbol_stats = symbol_stats.sort_values("trades", ascending=False)

    for symbol in symbol_stats.head(10).index:
        row = symbol_stats.loc[symbol]
        print(
            f"   {symbol:8} - {row['trades']:3.0f} trades, "
            f"{row['closed']:3.0f} closed, "
            f"Win: {row['win_rate']:.1f}%, "
            f"Avg PnL: ${row['avg_pnl']:.2f}"
        )

    # Analyze entry timing
    print("\n⏰ Entry Timing Analysis:")
    trades_df["hour"] = trades_df["created_at"].dt.hour
    hourly_entries = trades_df.groupby("hour")["trade_id"].count()
    peak_hour = hourly_entries.idxmax()
    print(
        f"   Peak trading hour: {peak_hour}:00 UTC ({hourly_entries[peak_hour]} trades)"
    )
    print(f"   Average trades per hour: {hourly_entries.mean():.1f}")

    # Analyze open positions
    open_trades = trades_df[trades_df["status"] == "FILLED"]
    if not open_trades.empty:
        print(f"\n🔓 Open Positions Analysis:")
        print(f"   Total open: {len(open_trades)}")
        print(f"   Symbols with open positions: {open_trades['symbol'].nunique()}")

        # Calculate unrealized P&L (approximate)
        print("\n   Top Open Positions by Count:")
        open_by_symbol = (
            open_trades.groupby("symbol").size().sort_values(ascending=False)
        )
        for symbol in open_by_symbol.head(5).index:
            count = open_by_symbol[symbol]
            print(f"   {symbol:8} - {count:3} positions")

    # Analyze closed trades performance
    closed_trades = trades_df[trades_df["status"] == "CLOSED"]
    if not closed_trades.empty:
        print(f"\n💰 Closed Trades Performance:")
        winners = closed_trades[closed_trades["pnl"] > 0]
        losers = closed_trades[closed_trades["pnl"] < 0]

        print(f"   Total closed: {len(closed_trades)}")
        print(
            f"   Winners: {len(winners)} ({len(winners)/len(closed_trades)*100:.1f}%)"
        )
        print(f"   Losers: {len(losers)} ({len(losers)/len(closed_trades)*100:.1f}%)")
        print(f"   Total P&L: ${closed_trades['pnl'].sum():.2f}")
        print(f"   Best trade: ${closed_trades['pnl'].max():.2f}")
        print(f"   Worst trade: ${closed_trades['pnl'].min():.2f}")

        # Exit reasons
        if "exit_reason" in closed_trades.columns:
            print("\n   Exit Reasons:")
            exit_reasons = closed_trades["exit_reason"].value_counts()
            for reason, count in exit_reasons.items():
                if reason:
                    print(f"   {reason}: {count} ({count/len(closed_trades)*100:.1f}%)")

    return {
        "trades_df": trades_df,
        "symbol_stats": symbol_stats,
        "open_trades": len(open_trades),
        "closed_trades": len(closed_trades),
    }


def analyze_market_conditions(supabase) -> Dict:
    """Analyze market conditions and identify opportunities."""
    print("\n" + "=" * 60)
    print("🌍 MARKET CONDITIONS ANALYSIS")
    print("=" * 60)

    end_time = datetime.now(pytz.UTC)
    start_time = end_time - timedelta(hours=24)

    # Fetch OHLC data
    query = (
        supabase.table("ohlc_data")
        .select("*")
        .gte("timestamp", start_time.isoformat())
        .lte("timestamp", end_time.isoformat())
    )

    result = query.execute()

    if not result.data:
        return {}

    df = pd.DataFrame(result.data)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Calculate returns and volatility for each symbol
    market_stats = []
    for symbol in df["symbol"].unique():
        symbol_data = df[df["symbol"] == symbol].sort_values("timestamp")
        if len(symbol_data) < 2:
            continue

        returns = symbol_data["close"].pct_change() * 100

        stats = {
            "symbol": symbol,
            "return_24h": (
                symbol_data["close"].iloc[-1] / symbol_data["close"].iloc[0] - 1
            )
            * 100,
            "volatility": returns.std(),
            "max_gain": returns.max(),
            "max_drop": returns.min(),
            "price_range": (
                (symbol_data["high"].max() - symbol_data["low"].min())
                / symbol_data["close"].iloc[0]
                * 100
            ),
            "num_candles": len(symbol_data),
        }
        market_stats.append(stats)

    market_df = pd.DataFrame(market_stats)

    print("\n📊 Market Characteristics:")
    print(f"   Average 24h Return: {market_df['return_24h'].mean():.2f}%")
    print(f"   Average Volatility: {market_df['volatility'].mean():.3f}%")
    print(f"   Symbols Up: {(market_df['return_24h'] > 0).sum()}")
    print(f"   Symbols Down: {(market_df['return_24h'] < 0).sum()}")

    # Identify market regimes
    high_vol = market_df[
        market_df["volatility"] > market_df["volatility"].quantile(0.75)
    ]
    low_vol = market_df[
        market_df["volatility"] < market_df["volatility"].quantile(0.25)
    ]

    print(f"\n⚡ Volatility Analysis:")
    print(f"   High volatility coins (top 25%): {len(high_vol)}")
    if not high_vol.empty:
        print("   Examples:", ", ".join(high_vol.head(5)["symbol"].tolist()))
    print(f"   Low volatility coins (bottom 25%): {len(low_vol)}")
    if not low_vol.empty:
        print("   Examples:", ", ".join(low_vol.head(5)["symbol"].tolist()))

    # Identify opportunities
    print("\n🎯 Potential Opportunities:")

    # Strong trending coins
    strong_up = market_df[market_df["return_24h"] > 2]
    if not strong_up.empty:
        print(
            f"   Strong uptrends (>2% gain): {', '.join(strong_up['symbol'].tolist())}"
        )

    strong_down = market_df[market_df["return_24h"] < -2]
    if not strong_down.empty:
        print(
            f"   Strong downtrends (<-2% loss): {', '.join(strong_down['symbol'].tolist())}"
        )

    # Mean reversion candidates
    oversold = market_df[market_df["max_drop"] < -1]
    if not oversold.empty:
        print(f"   Oversold (>1% intraday drop): {len(oversold)} symbols")

    return {"market_df": market_df, "high_vol": high_vol, "low_vol": low_vol}


def correlate_performance(trading_data: Dict, market_data: Dict) -> List[str]:
    """Correlate trading performance with market conditions."""
    print("\n" + "=" * 60)
    print("🔗 PERFORMANCE CORRELATION ANALYSIS")
    print("=" * 60)

    insights = []

    if "symbol_stats" in trading_data and "market_df" in market_data:
        # Merge trading and market data
        symbol_stats = trading_data["symbol_stats"]
        market_df = market_data["market_df"]

        # Join on symbol
        merged = symbol_stats.merge(
            market_df[["symbol", "return_24h", "volatility", "price_range"]],
            left_index=True,
            right_on="symbol",
            how="inner",
        )

        if not merged.empty:
            # Analyze correlations
            print("\n📈 Trading Success vs Market Conditions:")

            # Win rate vs volatility
            if "win_rate" in merged.columns:
                corr = merged["win_rate"].corr(merged["volatility"])
                print(f"   Win rate vs Volatility correlation: {corr:.3f}")
                if abs(corr) > 0.3:
                    if corr > 0:
                        insights.append(
                            "✅ Higher volatility correlates with better win rates"
                        )
                    else:
                        insights.append(
                            "⚠️ Higher volatility correlates with lower win rates"
                        )

            # Trading frequency vs price movement
            corr = merged["trades"].corr(merged["price_range"])
            print(f"   Trade frequency vs Price range correlation: {corr:.3f}")
            if corr > 0.3:
                insights.append(
                    "📊 System correctly identifies and trades more volatile symbols"
                )

            # Best performing conditions
            if "win_rate" in merged.columns:
                best_performers = merged[merged["win_rate"] > 60].sort_values(
                    "win_rate", ascending=False
                )
                if not best_performers.empty:
                    print("\n🏆 Best Performing Symbols:")
                    for _, row in best_performers.head(5).iterrows():
                        print(
                            f"   {row['symbol']:8} - Win: {row['win_rate']:.1f}%, "
                            f"Vol: {row['volatility']:.3f}%, "
                            f"24h: {row['return_24h']:+.2f}%"
                        )

    # Analyze strategy behavior
    trades_df = trading_data.get("trades_df", pd.DataFrame())
    if not trades_df.empty:
        print("\n🎯 Strategy Behavior Analysis:")

        # Channel strategy specific
        channel_trades = trades_df[trades_df["strategy_name"] == "CHANNEL"]
        if not channel_trades.empty:
            print(f"\n   CHANNEL Strategy:")
            print(f"   Total signals: {len(channel_trades)}")
            print(f"   Unique symbols: {channel_trades['symbol'].nunique()}")

            # Entry distribution
            if (
                "stop_loss" in channel_trades.columns
                and "take_profit" in channel_trades.columns
            ):
                channel_trades["risk_reward"] = (
                    channel_trades["take_profit"] - channel_trades["price"]
                ) / (channel_trades["price"] - channel_trades["stop_loss"])
                avg_rr = channel_trades["risk_reward"].mean()
                print(f"   Average Risk/Reward: {avg_rr:.2f}")

                if avg_rr < 1.5:
                    insights.append(
                        "⚠️ Risk/Reward ratio is low - consider wider take profits"
                    )
                elif avg_rr > 3:
                    insights.append("✅ Good Risk/Reward ratio maintained")

    return insights


def generate_recommendations(
    trading_data: Dict, market_data: Dict, insights: List[str]
) -> List[str]:
    """Generate specific recommendations based on analysis."""
    recommendations = []

    # Based on market conditions
    if "market_df" in market_data:
        market_df = market_data["market_df"]
        avg_vol = market_df["volatility"].mean()

        if avg_vol < 0.1:  # Low volatility
            recommendations.append("📉 LOW VOLATILITY ENVIRONMENT:")
            recommendations.append(
                "   • Consider tightening stop losses to preserve capital"
            )
            recommendations.append("   • Reduce position sizes as moves are smaller")
            recommendations.append("   • Focus on range-bound strategies like CHANNEL")
        elif avg_vol > 0.5:  # High volatility
            recommendations.append("⚡ HIGH VOLATILITY ENVIRONMENT:")
            recommendations.append("   • Widen stops to avoid premature exits")
            recommendations.append(
                "   • Consider trailing stops to capture larger moves"
            )
            recommendations.append("   • Increase focus on trend-following strategies")

    # Based on trading performance
    if trading_data:
        open_trades = trading_data.get("open_trades", 0)
        closed_trades = trading_data.get("closed_trades", 0)

        if open_trades > closed_trades * 2:
            recommendations.append("\n⚠️ POSITION MANAGEMENT:")
            recommendations.append("   • High number of open positions vs closed")
            recommendations.append("   • Consider implementing time-based exits")
            recommendations.append(
                "   • Review exit criteria - may be too conservative"
            )

        if "symbol_stats" in trading_data:
            symbol_stats = trading_data["symbol_stats"]
            concentrated = symbol_stats[
                symbol_stats["trades"] > symbol_stats["trades"].mean() * 2
            ]
            if not concentrated.empty:
                recommendations.append("\n🎯 CONCENTRATION RISK:")
                recommendations.append(
                    f"   • Heavy concentration in {', '.join(concentrated.index.tolist())}"
                )
                recommendations.append("   • Consider position limits per symbol")
                recommendations.append("   • Implement portfolio diversification rules")

    # Specific strategy adjustments
    recommendations.append("\n🔧 IMMEDIATE ACTIONS:")
    recommendations.append(
        "   1. Review and adjust CHANNEL thresholds for current volatility"
    )
    recommendations.append("   2. Implement portfolio-wide risk limits")
    recommendations.append("   3. Add time-based exits for stale positions")
    recommendations.append(
        "   4. Consider adding mean-reversion logic for oversold conditions"
    )

    return recommendations


def main():
    """Main analysis function."""
    print("=" * 80)
    print("🔬 DEEP TRADING BEHAVIOR ANALYSIS")
    print("=" * 80)

    # Initialize Supabase
    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_key)

    # Analyze trading patterns
    trading_data = analyze_trading_patterns(supabase)

    # Analyze market conditions
    market_data = analyze_market_conditions(supabase)

    # Correlate performance
    insights = correlate_performance(trading_data, market_data)

    # Generate recommendations
    recommendations = generate_recommendations(trading_data, market_data, insights)

    # Print final insights and recommendations
    print("\n" + "=" * 60)
    print("💡 KEY INSIGHTS")
    print("=" * 60)

    if insights:
        for insight in insights:
            print(f"   {insight}")
    else:
        print("   No significant correlations found")

    print("\n" + "=" * 60)
    print("📋 RECOMMENDATIONS")
    print("=" * 60)

    for rec in recommendations:
        print(rec)

    # Save analysis
    report = {
        "timestamp": datetime.now().isoformat(),
        "open_trades": trading_data.get("open_trades", 0),
        "closed_trades": trading_data.get("closed_trades", 0),
        "insights": insights,
        "recommendations": recommendations,
    }

    report_file = (
        f"data/trading_behavior_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n💾 Analysis saved to: {report_file}")
    print("\n" + "=" * 80)
    print("✅ Analysis Complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
