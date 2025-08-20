#!/usr/bin/env python3
"""
Fetch 1-minute OHLC data for key symbols.
1-minute data is essential for precise entry/exit points and backtesting.
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta, timezone as tz
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import pandas as pd
from loguru import logger
from polygon import RESTClient

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.supabase_client import SupabaseClient
from src.config.settings import get_settings

settings = get_settings()


class OneMinuteFetcher:
    """Fetch 1-minute OHLC data"""

    def __init__(self):
        self.client = RESTClient(api_key=settings.polygon_api_key)
        self.supabase = SupabaseClient()
        self.results_file = Path("data/1min_ohlc_results.json")
        self.results = {}

        # Top coins only - 1-minute data is voluminous
        # Focusing on most liquid/important coins
        self.symbols = [
            "BTC",
            "ETH",
            "SOL",
            "XRP",
            "ADA",
            "AVAX",
            "DOGE",
            "MATIC",
            "LINK",
            "UNI",
            "LTC",
            "DOT",
            "ATOM",
            "BCH",
        ]

    def check_existing_data(self, symbol: str) -> Tuple[bool, int]:
        """Check if symbol already has 1m data"""
        try:
            result = (
                self.supabase.client.table("ohlc_data")
                .select("timestamp", count="exact")
                .eq("symbol", symbol)
                .eq("timeframe", "1m")
                .execute()
            )

            count = result.count if hasattr(result, "count") else 0
            has_data = count > 10000  # Consider complete if > 10000 bars
            return has_data, count
        except Exception as e:
            logger.error(f"Error checking {symbol}: {e}")
            return False, 0

    def fetch_batch(
        self, symbol: str, start_date: datetime, end_date: datetime
    ) -> List[Dict]:
        """Fetch a batch of 1-minute OHLC data"""
        try:
            ticker = f"X:{symbol}USD"

            # 1-minute bars
            bars = self.client.get_aggs(
                ticker=ticker,
                multiplier=1,
                timespan="minute",
                from_=start_date.strftime("%Y-%m-%d"),
                to=end_date.strftime("%Y-%m-%d"),
                adjusted=True,
                sort="asc",
                limit=50000,
            )

            # Convert to list of dicts
            data = []
            for bar in bars:
                data.append(
                    {
                        "timestamp": pd.Timestamp(
                            bar.timestamp, unit="ms", tz="UTC"
                        ).isoformat(),
                        "symbol": symbol,
                        "timeframe": "1m",
                        "open": float(bar.open),
                        "high": float(bar.high),
                        "low": float(bar.low),
                        "close": float(bar.close),
                        "volume": float(bar.volume) if bar.volume else 0,
                        "vwap": (
                            float(bar.vwap)
                            if hasattr(bar, "vwap") and bar.vwap
                            else None
                        ),
                        "trades": (
                            int(bar.transactions)
                            if hasattr(bar, "transactions")
                            else None
                        ),
                    }
                )

            if data:
                logger.info(f"Fetched {len(data)} bars for {symbol}")

            return data

        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
            return []

    def save_batch(self, data: List[Dict]) -> bool:
        """Save batch to database"""
        if not data:
            return True

        batch_size = 2000  # Larger batches for 1-minute data

        for i in range(0, len(data), batch_size):
            batch = data[i : i + batch_size]

            try:
                result = self.supabase.client.table("ohlc_data").upsert(batch).execute()
                logger.success(f"Saved {len(batch)} bars")
            except Exception as e:
                logger.error(f"Error saving batch: {e}")
                # Try smaller batch on error
                if batch_size > 500:
                    logger.info("Retrying with smaller batch size...")
                    for j in range(0, len(batch), 500):
                        small_batch = batch[j : j + 500]
                        try:
                            result = (
                                self.supabase.client.table("ohlc_data")
                                .upsert(small_batch)
                                .execute()
                            )
                            logger.success(f"Saved {len(small_batch)} bars (retry)")
                        except:
                            return False
                else:
                    return False

        return True

    def fetch_symbol(self, symbol: str) -> int:
        """Fetch 1-minute data for a symbol"""
        # Check if already have data
        has_data, count = self.check_existing_data(symbol)
        if has_data:
            logger.info(f"✓ {symbol} already has {count} bars, skipping")
            return 0

        logger.info(f"\n{'='*60}")
        logger.info(f"Fetching 1m data for {symbol}")
        logger.info(f"{'='*60}")

        # Fetch 1 year of 1-minute data (that's a lot!)
        # We'll do it in smaller chunks
        end_date = datetime.now(tz.utc)
        start_date = end_date - timedelta(days=365)  # 1 year

        all_data = []
        current_date = start_date
        batch_days = 7  # 7-day batches for 1-minute data

        while current_date < end_date:
            batch_end = min(current_date + timedelta(days=batch_days), end_date)

            # Fetch batch
            data = self.fetch_batch(symbol, current_date, batch_end)

            if data:
                # Save immediately for 1-minute data (too much to hold in memory)
                logger.info(
                    f"Saving batch: {current_date.date()} to {batch_end.date()} - {len(data)} bars"
                )
                if not self.save_batch(data):
                    logger.error(f"Failed to save batch for {symbol}")
                    return len(all_data)
                all_data.extend(data)

            current_date = batch_end + timedelta(days=1)
            time.sleep(0.5)  # Rate limiting - be nice to the API

        if all_data:
            logger.success(f"✅ Completed {symbol}: {len(all_data)} total bars")
            return len(all_data)

        return 0

    def fetch_all(self):
        """Main function to fetch all 1-minute data"""
        logger.info("=" * 80)
        logger.info("1-MINUTE OHLC DATA FETCHER")
        logger.info("=" * 80)
        logger.info(f"Fetching 1-minute data for {len(self.symbols)} symbols")
        logger.warning("⚠️  This will fetch a LOT of data - may take a while!")

        for idx, symbol in enumerate(self.symbols, 1):
            logger.info(f"\n[{idx}/{len(self.symbols)}] Processing {symbol}")

            try:
                bars_saved = self.fetch_symbol(symbol)

                self.results[symbol] = {
                    "status": "completed" if bars_saved > 0 else "skipped",
                    "bars_saved": bars_saved,
                }

                # Save progress
                with open(self.results_file, "w") as f:
                    json.dump(self.results, f, indent=2)

            except Exception as e:
                logger.error(f"Failed to process {symbol}: {e}")
                self.results[symbol] = {"status": "failed", "error": str(e)}

            # Longer delay between symbols for 1-minute data
            time.sleep(2)

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("1-MINUTE DATA COMPLETE")
        logger.info("=" * 80)

        successful = sum(
            1 for r in self.results.values() if r.get("status") == "completed"
        )
        skipped = sum(1 for r in self.results.values() if r.get("status") == "skipped")
        failed = sum(1 for r in self.results.values() if r.get("status") == "failed")

        logger.info(f"Successful: {successful}")
        logger.info(f"Skipped (already had data): {skipped}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Results saved to {self.results_file}")


def main():
    fetcher = OneMinuteFetcher()
    fetcher.fetch_all()


if __name__ == "__main__":
    main()
