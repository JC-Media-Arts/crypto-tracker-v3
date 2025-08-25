#!/usr/bin/env python3
"""Export 48-hour market data for all tracked cryptocurrencies."""

import os
import sys
import pandas as pd
from datetime import datetime, timedelta
import pytz
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.settings import get_settings
from supabase import create_client


def main():
    print("📊 Exporting 48-hour market data...")

    # Initialize Supabase
    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_key)

    # Set time range
    end_time = datetime.now(pytz.UTC)
    start_time = end_time - timedelta(hours=48)

    print(
        f"Time range: {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')} UTC"
    )

    # Fetch OHLC data (paginated to get all data)
    print("Fetching OHLC data...")
    all_data = []
    offset = 0
    limit = 1000

    while True:
        query = (
            supabase.table("ohlc_data")
            .select("*")
            .gte("timestamp", start_time.isoformat())
            .lte("timestamp", end_time.isoformat())
            .order("symbol", desc=False)
            .order("timestamp", desc=False)
            .limit(limit)
            .offset(offset)
        )

        result = query.execute()

        if not result.data:
            break

        all_data.extend(result.data)
        print(f"  Fetched {len(result.data)} records (total: {len(all_data)})")

        if len(result.data) < limit:
            break

        offset += limit

    result.data = all_data

    if not result.data:
        print("❌ No data found!")
        return

    df = pd.DataFrame(result.data)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    print(f"✅ Fetched {len(df):,} data points for {df['symbol'].nunique()} symbols")

    # Save raw data to CSV
    csv_file = f"data/market_data_48hr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(csv_file, index=False)
    print(f"💾 Raw data saved to: {csv_file}")

    # Calculate statistics for each symbol
    stats = []
    for symbol in sorted(df["symbol"].unique()):
        symbol_data = df[df["symbol"] == symbol].sort_values("timestamp")

        if len(symbol_data) < 2:
            continue

        first_price = symbol_data.iloc[0]["close"]
        last_price = symbol_data.iloc[-1]["close"]

        # Find the price 24 hours ago (approximately)
        mid_time = end_time - timedelta(hours=24)
        mid_data = symbol_data[symbol_data["timestamp"] <= mid_time]
        mid_price = mid_data.iloc[-1]["close"] if not mid_data.empty else first_price

        stats_dict = {
            "symbol": symbol,
            "data_points": len(symbol_data),
            "first_timestamp": symbol_data.iloc[0]["timestamp"].strftime(
                "%Y-%m-%d %H:%M"
            ),
            "last_timestamp": symbol_data.iloc[-1]["timestamp"].strftime(
                "%Y-%m-%d %H:%M"
            ),
            "price_48hr_ago": first_price,
            "price_24hr_ago": mid_price,
            "current_price": last_price,
            "change_48hr": (last_price - first_price) / first_price * 100,
            "change_24hr": (last_price - mid_price) / mid_price * 100,
            "high_48hr": symbol_data["high"].max(),
            "low_48hr": symbol_data["low"].min(),
            "avg_volume": symbol_data["volume"].mean()
            if "volume" in symbol_data.columns
            else 0,
            "price_range": (symbol_data["high"].max() - symbol_data["low"].min())
            / first_price
            * 100,
        }
        stats.append(stats_dict)

    stats_df = pd.DataFrame(stats)

    # Save statistics to CSV
    stats_file = (
        f"data/market_stats_48hr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )
    stats_df.to_csv(stats_file, index=False)
    print(f"💾 Statistics saved to: {stats_file}")

    # Fetch paper trades for the same period (paginated)
    print("\nFetching paper trades data...")
    all_trades = []
    offset = 0
    limit = 1000

    while True:
        query = (
            supabase.table("paper_trades")
            .select("*")
            .gte("created_at", start_time.isoformat())
            .lte("created_at", end_time.isoformat())
            .order("created_at", desc=False)
            .limit(limit)
            .offset(offset)
        )

        trades_result = query.execute()

        if not trades_result.data:
            break

        all_trades.extend(trades_result.data)
        print(f"  Fetched {len(trades_result.data)} trades (total: {len(all_trades)})")

        if len(trades_result.data) < limit:
            break

        offset += limit

    trades_result.data = all_trades

    if trades_result.data:
        trades_df = pd.DataFrame(trades_result.data)
        trades_df["created_at"] = pd.to_datetime(trades_df["created_at"])
        if "filled_at" in trades_df.columns:
            trades_df["filled_at"] = pd.to_datetime(trades_df["filled_at"])

        # Save trades to CSV
        trades_file = (
            f"data/paper_trades_48hr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        trades_df.to_csv(trades_file, index=False)
        print(f"💾 Paper trades saved to: {trades_file}")

        # Calculate current portfolio status
        print("\n📊 Portfolio Analysis:")
        open_trades = trades_df[trades_df["status"] == "FILLED"]
        closed_trades = trades_df[trades_df["status"] == "CLOSED"]

        print(f"  Open positions: {len(open_trades)}")
        print(f"  Closed trades: {len(closed_trades)}")

        if not closed_trades.empty and "pnl" in closed_trades.columns:
            realized_pnl = closed_trades["pnl"].sum()
            print(f"  Realized P&L: ${realized_pnl:.2f}")

        # Calculate unrealized P&L for open positions
        if not open_trades.empty:
            unrealized_pnl = 0
            for _, trade in open_trades.iterrows():
                symbol = trade["symbol"]
                entry_price = trade["price"]
                amount = trade["amount"]

                # Get current price
                current_data = df[df["symbol"] == symbol].sort_values("timestamp")
                if not current_data.empty:
                    current_price = current_data.iloc[-1]["close"]
                    position_pnl = (current_price - entry_price) * amount
                    unrealized_pnl += position_pnl

            print(f"  Unrealized P&L: ${unrealized_pnl:.2f}")
            print(
                f"  Total P&L: ${(realized_pnl if 'realized_pnl' in locals() else 0) + unrealized_pnl:.2f}"
            )

    # Create markdown summary
    print("\nCreating markdown summary...")

    markdown_content = f"""# 48-Hour Crypto Market Analysis
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC

## Time Period
- **Start**: {start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC
- **End**: {end_time.strftime('%Y-%m-%d %H:%M:%S')} UTC
- **Duration**: 48 hours
- **Data Points**: {len(df):,}
- **Symbols Tracked**: {df['symbol'].nunique()}

## Market Overview

### Top Gainers (48hr)
"""

    # Add top gainers
    top_gainers = stats_df.nlargest(10, "change_48hr")
    for _, row in top_gainers.iterrows():
        markdown_content += f"- **{row['symbol']}**: {row['change_48hr']:+.2f}% (${row['current_price']:.2f})\n"

    markdown_content += "\n### Top Losers (48hr)\n"

    # Add top losers
    top_losers = stats_df.nsmallest(10, "change_48hr")
    for _, row in top_losers.iterrows():
        markdown_content += f"- **{row['symbol']}**: {row['change_48hr']:+.2f}% (${row['current_price']:.2f})\n"

    # Add BTC specific analysis
    btc_stats = stats_df[stats_df["symbol"] == "BTC"]
    if not btc_stats.empty:
        btc = btc_stats.iloc[0]
        markdown_content += f"""
## Bitcoin Analysis
- **Current Price**: ${btc['current_price']:,.2f}
- **48hr Change**: {btc['change_48hr']:+.2f}%
- **24hr Change**: {btc['change_24hr']:+.2f}%
- **48hr High**: ${btc['high_48hr']:,.2f}
- **48hr Low**: ${btc['low_48hr']:,.2f}
- **Price Range**: {btc['price_range']:.2f}%
"""

    # Add market statistics
    markdown_content += f"""
## Market Statistics
- **Average 48hr Return**: {stats_df['change_48hr'].mean():.2f}%
- **Average 24hr Return**: {stats_df['change_24hr'].mean():.2f}%
- **Symbols Up (48hr)**: {(stats_df['change_48hr'] > 0).sum()} / {len(stats_df)}
- **Symbols Up (24hr)**: {(stats_df['change_24hr'] > 0).sum()} / {len(stats_df)}

## Data Files Generated
1. **Raw OHLC Data**: `{csv_file}`
   - All price data with timestamps
   - Format: CSV with columns: timestamp, symbol, open, high, low, close, volume

2. **Market Statistics**: `{stats_file}`
   - Summary statistics per symbol
   - Format: CSV with price changes, highs, lows

3. **Paper Trades**: `{trades_file if 'trades_file' in locals() else 'No trades found'}`
   - All trading activity during period
   - Format: CSV with trade details

## Notes for Analysis
- Data is hourly resolution (not 1-minute)
- All timestamps are in UTC
- Prices are in USD
- Volume data may be incomplete for some symbols

## Key Events to Investigate
"""

    # Identify potential crash periods
    for symbol in ["BTC", "ETH", "SOL"]:
        symbol_data = df[df["symbol"] == symbol].sort_values("timestamp")
        if not symbol_data.empty:
            # Look for large drops
            symbol_data["pct_change"] = symbol_data["close"].pct_change() * 100
            largest_drop = symbol_data["pct_change"].min()
            if largest_drop < -2:
                drop_time = symbol_data[symbol_data["pct_change"] == largest_drop][
                    "timestamp"
                ].iloc[0]
                markdown_content += f"- **{symbol}** dropped {largest_drop:.2f}% at {drop_time.strftime('%Y-%m-%d %H:%M')} UTC\n"

    markdown_content += """

## Instructions for Further Analysis
1. Load the CSV files into your preferred analysis tool (Excel, Python, R, etc.)
2. The raw OHLC data contains all price movements
3. Cross-reference trade timestamps with price movements to identify impact
4. Look for correlation between BTC movements and portfolio performance
5. Pay special attention to the period around any significant price drops

---
*Generated by crypto-tracker-v3 analysis system*
"""

    # Save markdown file
    markdown_file = (
        f"data/market_analysis_48hr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    )
    with open(markdown_file, "w") as f:
        f.write(markdown_content)

    print(f"📝 Markdown summary saved to: {markdown_file}")

    print("\n" + "=" * 60)
    print("✅ Export complete! Files generated:")
    print(f"  1. {csv_file}")
    print(f"  2. {stats_file}")
    if "trades_file" in locals():
        print(f"  3. {trades_file}")
    print(f"  4. {markdown_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()
