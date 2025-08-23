#!/usr/bin/env python3
"""
Historical Data Backfill Script

Fetches historical price data from Polygon.io REST API and populates the database.
This script is designed to be run once to backfill historical data for ML training.
"""

import sys
import os
import time
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
import requests
from loguru import logger

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.settings import get_settings
from src.data.supabase_client import SupabaseClient
from src.data.polygon_client import PolygonWebSocketClient

# Configure logger
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")
logger.add("logs/backfill.log", rotation="100 MB", retention="7 days")


class HistoricalDataBackfill:
    """Handles historical data backfill from Polygon REST API."""

    def __init__(self):
        self.settings = get_settings()
        self.supabase = SupabaseClient()
        self.polygon_client = PolygonWebSocketClient()
        self.api_key = self.settings.polygon_api_key
        self.base_url = "https://api.polygon.io/v2"
        self.rate_limit_delay = 0.1  # Paid tier: Unlimited API calls, just a small delay to be nice

    def get_symbols(self) -> List[str]:
        """Get list of symbols to backfill from PolygonClient."""
        return self.polygon_client._get_supported_symbols()

    def fetch_aggregates(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime,
        timespan: str = "minute",
        multiplier: int = 1,
    ) -> Optional[List[Dict]]:
        """
        Fetch aggregate bars from Polygon REST API.

        Args:
            symbol: Crypto symbol (e.g., 'BTC')
            from_date: Start date for data
            to_date: End date for data
            timespan: Bar size (minute, hour, day)
            multiplier: Size multiplier

        Returns:
            List of price bars or None if error
        """
        # Convert symbol to Polygon format
        ticker = f"X:{symbol}USD"

        # Format dates
        from_str = from_date.strftime("%Y-%m-%d")
        to_str = to_date.strftime("%Y-%m-%d")

        # Build URL
        url = f"{self.base_url}/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_str}/{to_str}"

        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": "50000",  # Max allowed
            "apiKey": self.api_key,
        }

        try:
            logger.debug(f"Fetching {symbol} from {from_str} to {to_str}")
            response = requests.get(url, params=params, timeout=30)

            if response.status_code == 429:
                logger.warning("Rate limit hit, waiting 60 seconds...")
                time.sleep(60)
                return self.fetch_aggregates(symbol, from_date, to_date, timespan, multiplier)

            response.raise_for_status()
            data = response.json()

            if data.get("status") == "OK" and "results" in data:
                logger.info(f"Fetched {len(data['results'])} bars for {symbol}")
                return data["results"]
            else:
                logger.warning(f"No data returned for {symbol}: {data.get('status')}")
                return []

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None

    def process_bars(self, symbol: str, bars: List[Dict]) -> List[Dict]:
        """
        Process Polygon bars into price_data records.

        Args:
            symbol: Crypto symbol
            bars: List of Polygon aggregate bars

        Returns:
            List of price_data records
        """
        records = []

        for bar in bars:
            # Convert timestamp from milliseconds to datetime
            timestamp = datetime.fromtimestamp(bar["t"] / 1000, tz=timezone.utc)

            # Use close price as the price point
            record = {
                "symbol": symbol,
                "timestamp": timestamp.isoformat(),
                "price": bar["c"],  # Close price
                "volume": bar.get("v", 0),  # Volume
            }
            records.append(record)

        return records

    async def backfill_symbol(self, symbol: str, months_back: int = 6, timespan: str = "minute") -> Tuple[int, int]:
        """
        Backfill historical data for a single symbol.

        Args:
            symbol: Crypto symbol to backfill
            months_back: Number of months of historical data
            timespan: Granularity of data

        Returns:
            Tuple of (records_fetched, records_saved)
        """
        logger.info(f"Starting backfill for {symbol} ({months_back} months)")

        # Calculate date range
        to_date = datetime.now(timezone.utc)
        from_date = to_date - timedelta(days=months_back * 30)

        # With paid tier, we can fetch larger chunks - let's do 30-day chunks for efficiency
        # This reduces the number of API calls while keeping response sizes manageable
        chunk_days = 30
        total_fetched = 0
        total_saved = 0

        current_from = from_date
        while current_from < to_date:
            current_to = min(current_from + timedelta(days=chunk_days), to_date)

            # Fetch data for this chunk
            bars = self.fetch_aggregates(
                symbol=symbol,
                from_date=current_from,
                to_date=current_to,
                timespan=timespan,
                multiplier=1 if timespan == "minute" else 5,  # 5-min bars if not minute
            )

            if bars:
                # Process bars into records
                records = self.process_bars(symbol, bars)
                total_fetched += len(records)

                # Save to database
                if records:
                    try:
                        # Insert in batches to handle duplicates gracefully
                        saved = self.supabase.insert_price_data(records)
                        total_saved += saved
                        logger.info(
                            f"Saved {saved}/{len(records)} records for {symbol} "
                            f"({current_from.date()} to {current_to.date()})"
                        )
                    except Exception as e:
                        logger.error(f"Error saving data for {symbol}: {e}")

            # Move to next chunk
            current_from = current_to

            # Rate limiting (5 requests per minute for free tier)
            logger.debug(f"Rate limit delay: {self.rate_limit_delay}s")
            time.sleep(self.rate_limit_delay)

        logger.info(f"Completed {symbol}: Fetched {total_fetched}, Saved {total_saved}")
        return total_fetched, total_saved

    async def backfill_all(
        self,
        symbols: Optional[List[str]] = None,
        months_back: int = 6,
        timespan: str = "minute",
    ):
        """
        Backfill historical data for all symbols.

        Args:
            symbols: List of symbols to backfill (None for all)
            months_back: Number of months of historical data
            timespan: Granularity of data
        """
        if symbols is None:
            symbols = self.get_symbols()

        logger.info(f"Starting backfill for {len(symbols)} symbols, {months_back} months back")
        # With 30-day chunks and 0.1s delay, estimate is much faster
        chunks_per_symbol = (months_back * 30) // 30  # Number of 30-day chunks
        logger.info(
            f"Estimated time: {len(symbols) * chunks_per_symbol * self.rate_limit_delay / 60:.1f} minutes (paid tier - fast!)"
        )

        total_fetched = 0
        total_saved = 0
        failed_symbols = []

        for i, symbol in enumerate(symbols, 1):
            logger.info(f"\n[{i}/{len(symbols)}] Processing {symbol}")

            try:
                fetched, saved = await self.backfill_symbol(symbol=symbol, months_back=months_back, timespan=timespan)
                total_fetched += fetched
                total_saved += saved

            except Exception as e:
                logger.error(f"Failed to backfill {symbol}: {e}")
                failed_symbols.append(symbol)
                continue

        # Summary
        logger.info("\n" + "=" * 50)
        logger.info("BACKFILL COMPLETE")
        logger.info(f"Symbols processed: {len(symbols) - len(failed_symbols)}/{len(symbols)}")
        logger.info(f"Total records fetched: {total_fetched:,}")
        logger.info(f"Total records saved: {total_saved:,}")
        if failed_symbols:
            logger.warning(f"Failed symbols: {failed_symbols}")
        logger.info("=" * 50)


async def main():
    """Main function to run backfill."""
    import argparse

    parser = argparse.ArgumentParser(description="Backfill historical crypto data")
    parser.add_argument("--symbols", nargs="+", help="Specific symbols to backfill (e.g., BTC ETH SOL)")
    parser.add_argument(
        "--months",
        type=int,
        default=6,
        help="Number of months to backfill (default: 6)",
    )
    parser.add_argument(
        "--timespan",
        choices=["minute", "hour", "day"],
        default="minute",
        help="Data granularity (default: minute)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode: backfill only 1 week for first symbol",
    )

    args = parser.parse_args()

    backfiller = HistoricalDataBackfill()

    if args.test:
        # Test mode: just backfill 1 week of BTC data
        logger.info("TEST MODE: Backfilling 1 week of BTC data")
        symbols = ["BTC"]
        months = 0.25  # ~1 week
    else:
        symbols = args.symbols
        months = args.months

    await backfiller.backfill_all(symbols=symbols, months_back=months, timespan=args.timespan)


if __name__ == "__main__":
    asyncio.run(main())
