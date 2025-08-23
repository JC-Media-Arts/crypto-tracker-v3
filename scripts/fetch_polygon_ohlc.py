#!/usr/bin/env python3
"""
Fetch historical OHLC (candlestick) data from Polygon REST API.

This fetches aggregated bars instead of individual trades, giving us:
- Open: First trade price in the period
- High: Highest price in the period
- Low: Lowest price in the period
- Close: Last trade price in the period
- Volume: Total volume in the period
"""

import os
import sys
import time
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dotenv import load_dotenv
from loguru import logger

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from src.data.supabase_client import SupabaseClient

# Load environment variables
load_dotenv()


class PolygonOHLCFetcher:
    """Fetch historical OHLC data from Polygon REST API."""

    def __init__(self):
        """Initialize the OHLC fetcher."""
        self.settings = get_settings()
        self.api_key = self.settings.polygon_api_key
        self.base_url = "https://api.polygon.io"
        self.supabase = SupabaseClient()

    def fetch_ohlc_bars(
        self,
        symbol: str,
        timespan: str = "hour",
        multiplier: int = 1,
        from_date: str = None,
        to_date: str = None,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLC bars from Polygon.

        Args:
            symbol: Crypto symbol (e.g., 'BTC')
            timespan: Size of bars (minute, hour, day, week, month)
            multiplier: Size multiplier (1 = 1 hour, 4 = 4 hours)
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with OHLC data or None if error
        """
        # Build the URL for crypto aggregates
        # Format: X:BTCUSD for crypto pairs
        ticker = f"X:{symbol}USD"

        url = f"{self.base_url}/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_date}/{to_date}"

        params = {
            "apiKey": self.api_key,
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,  # Max allowed
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            if data.get("status") != "OK":
                logger.error(f"API error for {symbol}: {data.get('status')}")
                return None

            if "results" not in data or not data["results"]:
                logger.warning(f"No data returned for {symbol}")
                return None

            # Convert to DataFrame
            df = pd.DataFrame(data["results"])

            # Rename columns to match our needs
            df = df.rename(
                columns={
                    "t": "timestamp",  # Unix timestamp in milliseconds
                    "o": "open",
                    "h": "high",
                    "l": "low",
                    "c": "close",
                    "v": "volume",
                    "n": "num_trades",  # Number of trades
                }
            )

            # Convert timestamp from milliseconds to datetime
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)

            # Add symbol column
            df["symbol"] = symbol

            logger.info(f"Fetched {len(df)} bars for {symbol}")
            return df

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error for {symbol}: {e}")
            return None

    def save_ohlc_to_db(self, df: pd.DataFrame) -> int:
        """
        Save OHLC data to database.

        Args:
            df: DataFrame with OHLC data

        Returns:
            Number of records saved
        """
        if df.empty:
            return 0

        # Prepare data for insertion
        records = []
        for _, row in df.iterrows():
            record = {
                "timestamp": row["timestamp"].isoformat(),
                "symbol": row["symbol"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
                "num_trades": int(row.get("num_trades", 0)),
            }
            records.append(record)

        # Insert in batches
        batch_size = 1000
        saved_count = 0

        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            try:
                result = self.supabase.client.table("ohlc_data").upsert(batch, on_conflict="timestamp,symbol").execute()

                if result.data:
                    saved_count += len(result.data)
            except Exception as e:
                logger.error(f"Error saving batch: {e}")

        return saved_count

    def fetch_all_symbols(self, symbols: List[str], days_back: int = 180) -> Dict[str, int]:
        """
        Fetch OHLC data for multiple symbols.

        Args:
            symbols: List of symbols to fetch
            days_back: Number of days of history to fetch

        Returns:
            Dictionary mapping symbols to number of bars fetched
        """
        results = {}
        to_date = datetime.now().strftime("%Y-%m-%d")
        from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

        for symbol in symbols:
            logger.info(f"Fetching {symbol}...")

            # Fetch hourly bars
            df = self.fetch_ohlc_bars(
                symbol=symbol,
                timespan="hour",
                multiplier=1,
                from_date=from_date,
                to_date=to_date,
            )

            if df is not None and not df.empty:
                saved = self.save_ohlc_to_db(df)
                results[symbol] = saved
                logger.info(f"Saved {saved} bars for {symbol}")
            else:
                results[symbol] = 0
                logger.warning(f"No data fetched for {symbol}")

            # Small delay to be respectful of API
            time.sleep(0.1)  # 100ms delay between requests (paid account)

        return results


def main():
    """Fetch OHLC data for all symbols."""
    print("=" * 80)
    print("POLYGON OHLC DATA FETCHER")
    print("=" * 80)

    fetcher = PolygonOHLCFetcher()

    # Test with a few symbols first
    test_symbols = ["BTC", "ETH", "SOL"]

    print(f"\nFetching OHLC data for {len(test_symbols)} symbols")
    print(f"Time period: Last 180 days")
    print(f"Timeframe: 1-hour bars")
    print("-" * 40)

    results = fetcher.fetch_all_symbols(test_symbols, days_back=180)

    # Print summary
    print("\n" + "=" * 60)
    print("FETCH SUMMARY")
    print("=" * 60)

    total_bars = 0
    for symbol, count in results.items():
        print(f"{symbol:10} {count:,} bars")
        total_bars += count

    print("-" * 60)
    print(f"Total:     {total_bars:,} bars")

    print("\n" + "=" * 80)
    print("OHLC FETCH COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
