#!/usr/bin/env python3
"""Analyze crypto market movements in the last 24 hours and their impact on trading performance."""

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

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.settings import get_settings
from supabase import create_client
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def fetch_1min_data(supabase, hours_back: int = 24) -> pd.DataFrame:
    """Fetch OHLC data for all symbols (hourly resolution)."""
    print(f"\n📊 Fetching OHLC data for the last {hours_back} hours...")

    end_time = datetime.now(pytz.UTC)
    start_time = end_time - timedelta(hours=hours_back)

    # Fetch data from ohlc_data table (hourly data)
    query = (
        supabase.table("ohlc_data")
        .select("*")
        .gte("timestamp", start_time.isoformat())
        .lte("timestamp", end_time.isoformat())
    )

    result = query.execute()

    if not result.data:
        print("❌ No OHLC data found for the specified period!")
        return pd.DataFrame()

    df = pd.DataFrame(result.data)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(["symbol", "timestamp"])

    # Determine data frequency
    if len(df) > 1:
        time_diffs = df.groupby("symbol")["timestamp"].diff().dropna()
        avg_minutes = time_diffs.mean().total_seconds() / 60
        if avg_minutes < 10:
            freq = "1-minute"
        elif avg_minutes < 30:
            freq = "15-minute"
        elif avg_minutes < 90:
            freq = "hourly"
        else:
            freq = "daily"
    else:
        freq = "unknown"

    print(f"✅ Fetched {len(df):,} {freq} candles for {df['symbol'].nunique()} symbols")
    return df


def analyze_btc_movement(df: pd.DataFrame) -> Dict:
    """Analyze BTC price movement in detail."""
    btc_data = df[df["symbol"] == "BTC"].copy()

    if btc_data.empty:
        print("❌ No BTC data found!")
        return {}

    btc_data = btc_data.sort_values("timestamp")

    # Calculate key metrics
    start_price = btc_data.iloc[0]["close"]
    end_price = btc_data.iloc[-1]["close"]
    high_price = btc_data["high"].max()
    low_price = btc_data["low"].min()

    # Find major movements
    btc_data["pct_change"] = btc_data["close"].pct_change() * 100
    btc_data["cumulative_return"] = (btc_data["close"] / start_price - 1) * 100

    # Identify largest moves
    largest_drop_idx = btc_data["pct_change"].idxmin()
    largest_gain_idx = btc_data["pct_change"].idxmax()

    # Calculate volatility (for hourly data, use 4-hour rolling window)
    btc_data["rolling_std"] = (
        btc_data["pct_change"].rolling(4).std()
    )  # 4-hour rolling volatility

    # Find the crash/recovery periods
    min_price_idx = btc_data["low"].idxmin()
    min_price_time = btc_data.loc[min_price_idx, "timestamp"]

    # Calculate drawdown
    btc_data["cummax"] = btc_data["close"].cummax()
    btc_data["drawdown"] = (
        (btc_data["close"] - btc_data["cummax"]) / btc_data["cummax"] * 100
    )
    max_drawdown = btc_data["drawdown"].min()
    max_dd_time = btc_data.loc[btc_data["drawdown"].idxmin(), "timestamp"]

    analysis = {
        "start_price": start_price,
        "end_price": end_price,
        "high_price": high_price,
        "low_price": low_price,
        "total_return_pct": ((end_price / start_price - 1) * 100),
        "max_drawdown_pct": max_drawdown,
        "max_drawdown_time": max_dd_time,
        "price_range_pct": ((high_price - low_price) / start_price * 100),
        "largest_hourly_drop": btc_data.loc[largest_drop_idx, "pct_change"],
        "largest_hourly_drop_time": btc_data.loc[largest_drop_idx, "timestamp"],
        "largest_hourly_gain": btc_data.loc[largest_gain_idx, "pct_change"],
        "largest_hourly_gain_time": btc_data.loc[largest_gain_idx, "timestamp"],
        "min_price": low_price,
        "min_price_time": min_price_time,
        "avg_volatility": btc_data["rolling_std"].mean(),
        "max_volatility": btc_data["rolling_std"].max(),
        "data": btc_data,
    }

    return analysis


def analyze_market_correlation(df: pd.DataFrame) -> pd.DataFrame:
    """Analyze how different coins moved relative to BTC."""
    print("\n🔄 Analyzing market correlations...")

    # Create pivot table of prices
    price_pivot = df.pivot_table(
        index="timestamp", columns="symbol", values="close", aggfunc="mean"
    )

    # Calculate returns
    returns = price_pivot.pct_change() * 100

    # Calculate correlations with BTC
    if "BTC" in returns.columns:
        btc_corr = returns.corr()["BTC"].sort_values(ascending=False)

        # Calculate beta (sensitivity to BTC moves)
        betas = {}
        for symbol in returns.columns:
            if symbol != "BTC" and not returns[symbol].isna().all():
                cov = returns[[symbol, "BTC"]].cov().iloc[0, 1]
                var_btc = returns["BTC"].var()
                if var_btc > 0:
                    betas[symbol] = cov / var_btc

        # Calculate performance metrics
        performance = pd.DataFrame(
            {
                "symbol": price_pivot.columns,
                "start_price": price_pivot.iloc[0],
                "end_price": price_pivot.iloc[-1],
                "total_return": (price_pivot.iloc[-1] / price_pivot.iloc[0] - 1) * 100,
                "max_price": price_pivot.max(),
                "min_price": price_pivot.min(),
                "volatility": returns.std(),
                "btc_correlation": btc_corr,
                "beta_to_btc": pd.Series(betas),
            }
        )

        # Calculate drawdowns
        drawdowns = []
        for symbol in price_pivot.columns:
            prices = price_pivot[symbol].dropna()
            cummax = prices.cummax()
            dd = ((prices - cummax) / cummax * 100).min()
            drawdowns.append(dd)
        performance["max_drawdown"] = drawdowns

        performance = performance.sort_values("total_return", ascending=False)

        return performance

    return pd.DataFrame()


def analyze_paper_trades(supabase, start_time: datetime, end_time: datetime) -> Dict:
    """Analyze paper trading performance during the market event."""
    print("\n💼 Analyzing paper trading performance...")

    # Fetch paper trades
    query = (
        supabase.table("paper_trades")
        .select("*")
        .gte("created_at", start_time.isoformat())
        .lte("created_at", end_time.isoformat())
    )

    result = query.execute()

    if not result.data:
        print("No paper trades found in this period")
        return {}

    trades_df = pd.DataFrame(result.data)
    trades_df["created_at"] = pd.to_datetime(trades_df["created_at"])
    if "filled_at" in trades_df.columns:
        trades_df["filled_at"] = pd.to_datetime(trades_df["filled_at"])

    # Analyze by strategy
    if "strategy_name" in trades_df.columns:
        strategy_col = "strategy_name"
    else:
        strategy_col = "strategy"

    if strategy_col in trades_df.columns:
        agg_dict = {"trade_id": "count"}
        if "pnl" in trades_df.columns:
            # Only aggregate pnl for closed trades
            agg_dict["pnl"] = ["mean", "sum", "count"]
        strategy_performance = trades_df.groupby(strategy_col).agg(agg_dict).round(2)
    else:
        strategy_performance = pd.DataFrame()

    # Analyze by status
    status_counts = (
        trades_df["status"].value_counts()
        if "status" in trades_df.columns
        else pd.Series()
    )

    # Analyze timing
    hourly_trades = (
        trades_df.set_index("created_at")
        .resample("1H")
        .agg({"trade_id": "count", "pnl": "mean"})
        if "pnl" in trades_df.columns
        else trades_df.set_index("created_at").resample("1H").size()
    )

    # Find trades during major market moves
    closed_trades = (
        trades_df[trades_df["status"] == "CLOSED"].copy()
        if "status" in trades_df.columns
        else pd.DataFrame()
    )
    if not closed_trades.empty and "pnl" in closed_trades.columns:
        winners = closed_trades[closed_trades["pnl"] > 0]
        losers = closed_trades[closed_trades["pnl"] <= 0]

        win_rate = (
            len(winners) / len(closed_trades) * 100 if len(closed_trades) > 0 else 0
        )
        avg_winner = winners["pnl"].mean() if len(winners) > 0 else 0
        avg_loser = losers["pnl"].mean() if len(losers) > 0 else 0
    else:
        win_rate = avg_winner = avg_loser = 0

    return {
        "total_trades": len(trades_df),
        "strategy_performance": strategy_performance,
        "status_counts": status_counts,
        "hourly_trades": hourly_trades,
        "win_rate": win_rate,
        "avg_winner": avg_winner,
        "avg_loser": avg_loser,
        "trades_df": trades_df,
    }


def identify_market_regime(btc_analysis: Dict, market_corr: pd.DataFrame) -> str:
    """Identify the type of market event that occurred."""
    print("\n🎯 Identifying market regime...")

    regime_indicators = []

    # Check for flash crash
    if btc_analysis["max_drawdown_pct"] < -10:
        regime_indicators.append("FLASH CRASH")
    elif btc_analysis["max_drawdown_pct"] < -5:
        regime_indicators.append("SHARP CORRECTION")
    elif btc_analysis["max_drawdown_pct"] < -3:
        regime_indicators.append("MODERATE CORRECTION")

    # Check for recovery
    if btc_analysis["total_return_pct"] > -2 and btc_analysis["max_drawdown_pct"] < -5:
        regime_indicators.append("V-SHAPED RECOVERY")

    # Check volatility regime
    if btc_analysis["max_volatility"] > 2:
        regime_indicators.append("EXTREME VOLATILITY")
    elif btc_analysis["max_volatility"] > 1:
        regime_indicators.append("HIGH VOLATILITY")

    # Check correlation breakdown
    if not market_corr.empty:
        avg_correlation = market_corr["btc_correlation"].mean()
        if avg_correlation < 0.5:
            regime_indicators.append("CORRELATION BREAKDOWN")
        elif avg_correlation > 0.8:
            regime_indicators.append("HIGH CORRELATION")

    return " + ".join(regime_indicators) if regime_indicators else "NORMAL MARKET"


def generate_insights(
    btc_analysis: Dict,
    market_corr: pd.DataFrame,
    paper_trades: Dict,
    market_regime: str,
) -> List[str]:
    """Generate actionable insights from the analysis."""
    insights = []

    # Market structure insights
    if "FLASH CRASH" in market_regime or "SHARP CORRECTION" in market_regime:
        insights.append(
            "🚨 MAJOR FINDING: System experienced a flash crash event with rapid price decline"
        )
        insights.append(
            "   → Need better crash detection and emergency exit mechanisms"
        )
        insights.append("   → Consider implementing circuit breakers for extreme moves")

    if "V-SHAPED RECOVERY" in market_regime:
        insights.append(
            "📈 OPPORTUNITY: V-shaped recovery detected - system should capture these bounces"
        )
        insights.append(
            "   → Implement mean reversion strategies for oversold conditions"
        )
        insights.append("   → Add 'buy the dip' logic with proper risk controls")

    # Volatility insights
    if btc_analysis["max_volatility"] > 1.5:
        insights.append("⚡ VOLATILITY: Extreme volatility detected")
        insights.append("   → Tighten stop losses during high volatility periods")
        insights.append("   → Reduce position sizes when volatility spikes")
        insights.append("   → Consider volatility-adjusted position sizing")

    # Correlation insights
    if not market_corr.empty:
        high_beta_coins = market_corr[market_corr["beta_to_btc"] > 1.5]
        if not high_beta_coins.empty:
            insights.append(
                f"🔗 CORRELATION: {len(high_beta_coins)} coins showed high beta (>1.5) to BTC"
            )
            insights.append(
                "   → These coins amplify BTC moves - adjust position sizes accordingly"
            )
            insights.append(
                "   → Consider reducing exposure to high-beta coins during crashes"
            )

    # Trading performance insights
    if (
        paper_trades
        and "strategy_performance" in paper_trades
        and not paper_trades["strategy_performance"].empty
    ):
        insights.append("\n📊 STRATEGY PERFORMANCE DURING EVENT:")
        for strategy in paper_trades["strategy_performance"].index:
            if ("trade_id", "count") in paper_trades["strategy_performance"].columns:
                count = paper_trades["strategy_performance"].loc[
                    strategy, ("trade_id", "count")
                ]
                if ("pnl", "mean") in paper_trades["strategy_performance"].columns:
                    profit = paper_trades["strategy_performance"].loc[
                        strategy, ("pnl", "mean")
                    ]
                    insights.append(
                        f"   {strategy}: {count} trades, avg PnL: ${profit:.2f}"
                    )
                else:
                    insights.append(
                        f"   {strategy}: {count} trades opened (not yet closed)"
                    )

    # Timing insights
    if btc_analysis["largest_hourly_drop"] < -1:
        drop_time = btc_analysis["largest_hourly_drop_time"].strftime("%H:%M")
        insights.append(
            f"\n⏰ TIMING: Largest hourly drop ({btc_analysis['largest_hourly_drop']:.2f}%) at {drop_time}"
        )
        insights.append(
            "   → Consider time-based filters or reduced trading during volatile hours"
        )

    return insights


def main():
    """Main analysis function."""
    print("=" * 80)
    print("🔍 24-HOUR CRYPTO MARKET EVENT ANALYSIS")
    print("=" * 80)

    # Initialize Supabase
    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_key)

    # Set time range
    end_time = datetime.now(pytz.UTC)
    start_time = end_time - timedelta(hours=24)

    print(f"\n📅 Analysis Period:")
    print(f"   From: {start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"   To:   {end_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # Fetch and analyze 1-minute data
    df = fetch_1min_data(supabase, hours_back=24)

    if df.empty:
        print("❌ No data available for analysis")
        return

    # Analyze BTC movement
    print("\n" + "=" * 60)
    print("📊 BTC DETAILED ANALYSIS")
    print("=" * 60)

    btc_analysis = analyze_btc_movement(df)

    if btc_analysis:
        print(f"\n💰 Price Movement:")
        print(f"   Start Price:  ${btc_analysis['start_price']:,.2f}")
        print(f"   End Price:    ${btc_analysis['end_price']:,.2f}")
        print(f"   High:         ${btc_analysis['high_price']:,.2f}")
        print(f"   Low:          ${btc_analysis['low_price']:,.2f}")
        print(f"   Total Return: {btc_analysis['total_return_pct']:+.2f}%")

        print(f"\n📉 Drawdown Analysis:")
        print(f"   Max Drawdown: {btc_analysis['max_drawdown_pct']:.2f}%")
        print(
            f"   Occurred at:  {btc_analysis['max_drawdown_time'].strftime('%H:%M:%S')}"
        )
        print(
            f"   Lowest Price: ${btc_analysis['min_price']:,.2f} at {btc_analysis['min_price_time'].strftime('%H:%M:%S')}"
        )

        print(f"\n⚡ Volatility Metrics:")
        print(
            f"   Price Range:     {btc_analysis['price_range_pct']:.2f}% of starting price"
        )
        print(f"   Avg Volatility:  {btc_analysis['avg_volatility']:.3f}%")
        print(f"   Max Volatility:  {btc_analysis['max_volatility']:.3f}%")

        print(f"\n🎢 Extreme Moves:")
        print(
            f"   Largest Hourly Drop: {btc_analysis['largest_hourly_drop']:.2f}% at {btc_analysis['largest_hourly_drop_time'].strftime('%H:%M:%S')}"
        )
        print(
            f"   Largest Hourly Gain: {btc_analysis['largest_hourly_gain']:.2f}% at {btc_analysis['largest_hourly_gain_time'].strftime('%H:%M:%S')}"
        )

    # Analyze market correlations
    print("\n" + "=" * 60)
    print("🔄 MARKET-WIDE ANALYSIS")
    print("=" * 60)

    market_corr = analyze_market_correlation(df)

    if not market_corr.empty:
        print("\n📊 Top Performers:")
        top_5 = market_corr.head(5)
        for _, row in top_5.iterrows():
            print(
                f"   {row['symbol']:12} Return: {row['total_return']:+6.2f}%  "
                f"Drawdown: {row['max_drawdown']:6.2f}%  "
                f"Beta: {row['beta_to_btc']:5.2f}"
            )

        print("\n📉 Worst Performers:")
        bottom_5 = market_corr.tail(5)
        for _, row in bottom_5.iterrows():
            print(
                f"   {row['symbol']:12} Return: {row['total_return']:+6.2f}%  "
                f"Drawdown: {row['max_drawdown']:6.2f}%  "
                f"Beta: {row['beta_to_btc']:5.2f}"
            )

        # Statistics
        print("\n📈 Market Statistics:")
        print(f"   Average Return:      {market_corr['total_return'].mean():+.2f}%")
        print(f"   Median Return:       {market_corr['total_return'].median():+.2f}%")
        print(
            f"   Winners/Losers:      {(market_corr['total_return'] > 0).sum()}/{(market_corr['total_return'] <= 0).sum()}"
        )
        print(f"   Avg BTC Correlation: {market_corr['btc_correlation'].mean():.3f}")
        print(f"   Avg Drawdown:        {market_corr['max_drawdown'].mean():.2f}%")

    # Analyze paper trading performance
    paper_trades = analyze_paper_trades(supabase, start_time, end_time)

    if paper_trades:
        print("\n" + "=" * 60)
        print("💼 PAPER TRADING PERFORMANCE")
        print("=" * 60)

        print(f"\n📊 Overall Stats:")
        print(f"   Total Trades:  {paper_trades['total_trades']}")
        print(f"   Win Rate:      {paper_trades['win_rate']:.1f}%")
        print(f"   Avg Winner:    {paper_trades['avg_winner']:+.2f}%")
        print(f"   Avg Loser:     {paper_trades['avg_loser']:+.2f}%")

        if not paper_trades["status_counts"].empty:
            print(f"\n📈 Trade Status:")
            for status, count in paper_trades["status_counts"].items():
                print(f"   {status:10}: {count}")

    # Identify market regime
    market_regime = identify_market_regime(btc_analysis, market_corr)

    print("\n" + "=" * 60)
    print("🎯 MARKET REGIME IDENTIFICATION")
    print("=" * 60)
    print(f"\n🏷️  Regime: {market_regime}")

    # Generate insights
    print("\n" + "=" * 60)
    print("💡 KEY INSIGHTS & RECOMMENDATIONS")
    print("=" * 60)

    insights = generate_insights(btc_analysis, market_corr, paper_trades, market_regime)

    for insight in insights:
        print(insight)

    # Save detailed report
    report = {
        "timestamp": datetime.now().isoformat(),
        "period": {"start": start_time.isoformat(), "end": end_time.isoformat()},
        "market_regime": market_regime,
        "btc_metrics": {
            "total_return_pct": float(btc_analysis["total_return_pct"]),
            "max_drawdown_pct": float(btc_analysis["max_drawdown_pct"]),
            "price_range_pct": float(btc_analysis["price_range_pct"]),
            "max_volatility": float(btc_analysis["max_volatility"]),
        },
        "market_stats": {
            "symbols_analyzed": int(df["symbol"].nunique()),
            "total_candles": int(len(df)),
            "avg_market_return": float(market_corr["total_return"].mean())
            if not market_corr.empty
            else 0,
            "avg_btc_correlation": float(market_corr["btc_correlation"].mean())
            if not market_corr.empty
            else 0,
        },
        "paper_trading": {
            "total_trades": paper_trades.get("total_trades", 0),
            "win_rate": paper_trades.get("win_rate", 0),
        },
        "insights": insights,
    }

    report_file = (
        f"data/market_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n💾 Detailed report saved to: {report_file}")

    # Create visualization
    if btc_analysis and "data" in btc_analysis:
        create_visualization(btc_analysis["data"], market_corr, paper_trades)

    print("\n" + "=" * 80)
    print("✅ Analysis Complete!")
    print("=" * 80)


def create_visualization(
    btc_data: pd.DataFrame, market_corr: pd.DataFrame, paper_trades: Dict
):
    """Create interactive visualization of the market event."""
    print("\n📊 Creating visualization...")

    # Create subplots
    fig = make_subplots(
        rows=3,
        cols=2,
        subplot_titles=(
            "BTC Price Movement",
            "BTC Returns Distribution",
            "Market Drawdowns",
            "Correlation with BTC",
            "Hourly Volatility",
            "Paper Trading Activity",
        ),
        specs=[[{"secondary_y": True}, {}], [{}, {}], [{}, {}]],
    )

    # 1. BTC Price with volume
    fig.add_trace(
        go.Scatter(
            x=btc_data["timestamp"],
            y=btc_data["close"],
            name="BTC Price",
            line=dict(color="gold", width=2),
        ),
        row=1,
        col=1,
    )

    # Add volume bars
    fig.add_trace(
        go.Bar(
            x=btc_data["timestamp"],
            y=btc_data["volume"],
            name="Volume",
            marker_color="lightblue",
            opacity=0.3,
        ),
        row=1,
        col=1,
        secondary_y=True,
    )

    # 2. Returns distribution
    fig.add_trace(
        go.Histogram(
            x=btc_data["pct_change"],
            name="Hourly Returns",
            nbinsx=30,
            marker_color="purple",
        ),
        row=1,
        col=2,
    )

    # 3. Market drawdowns
    if not market_corr.empty:
        top_coins = market_corr.head(10)
        fig.add_trace(
            go.Bar(
                x=top_coins["symbol"],
                y=top_coins["max_drawdown"],
                name="Max Drawdown",
                marker_color="red",
            ),
            row=2,
            col=1,
        )

    # 4. Correlation with BTC
    if not market_corr.empty:
        fig.add_trace(
            go.Scatter(
                x=market_corr["btc_correlation"],
                y=market_corr["total_return"],
                mode="markers",
                name="Coins",
                text=market_corr["symbol"],
                marker=dict(
                    size=10,
                    color=market_corr["beta_to_btc"],
                    colorscale="Viridis",
                    showscale=True,
                    colorbar=dict(title="Beta to BTC"),
                ),
            ),
            row=2,
            col=2,
        )

    # 5. Rolling volatility
    fig.add_trace(
        go.Scatter(
            x=btc_data["timestamp"],
            y=btc_data["rolling_std"],
            name="4-hour Volatility",
            line=dict(color="orange", width=1),
            fill="tozeroy",
        ),
        row=3,
        col=1,
    )

    # 6. Paper trading activity
    if paper_trades and "hourly_trades" in paper_trades:
        hourly = paper_trades["hourly_trades"]
        fig.add_trace(
            go.Bar(
                x=hourly.index,
                y=hourly["trade_id"],
                name="Trades per Hour",
                marker_color="green",
            ),
            row=3,
            col=2,
        )

    # Update layout
    fig.update_layout(
        title="24-Hour Crypto Market Event Analysis",
        height=1200,
        showlegend=True,
        hovermode="x unified",
    )

    # Update axes
    fig.update_xaxes(title_text="Time", row=1, col=1)
    fig.update_xaxes(title_text="Returns (%)", row=1, col=2)
    fig.update_xaxes(title_text="Symbol", row=2, col=1)
    fig.update_xaxes(title_text="BTC Correlation", row=2, col=2)
    fig.update_xaxes(title_text="Time", row=3, col=1)
    fig.update_xaxes(title_text="Time", row=3, col=2)

    fig.update_yaxes(title_text="Price ($)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="Frequency", row=1, col=2)
    fig.update_yaxes(title_text="Drawdown (%)", row=2, col=1)
    fig.update_yaxes(title_text="Total Return (%)", row=2, col=2)
    fig.update_yaxes(title_text="Volatility (%)", row=3, col=1)
    fig.update_yaxes(title_text="Trade Count", row=3, col=2)

    # Save HTML
    html_file = f"data/market_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    fig.write_html(html_file)
    print(f"✅ Visualization saved to: {html_file}")


if __name__ == "__main__":
    main()
