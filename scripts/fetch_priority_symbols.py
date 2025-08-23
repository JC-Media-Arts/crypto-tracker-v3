#!/usr/bin/env python3
"""
Fetch OHLC data for priority symbols (top coins that are still missing).
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


class PriorityOHLCFetcher:
    """Fetch OHLC data for priority symbols"""

    def __init__(self):
        self.client = RESTClient(api_key=settings.polygon_api_key)
        self.supabase = SupabaseClient()
        self.results_file = Path("data/priority_ohlc_results.json")
        self.results = {}

        # Priority symbols - top coins by market cap
        self.priority_symbols = [
            "ETH",
            "SOL",
            "BNB",
            "XRP",
            "ADA",
            "AVAX",
            "DOGE",
            "TRX",
            "DOT",
            "MATIC",
            "LINK",
            "UNI",
            "LTC",
            "BCH",
            "ICP",
            "ATOM",
            "ETC",
        ]

    def check_symbol_data(self, symbol: str, timeframe: str) -> Tuple[bool, int]:
        """Check if symbol has data for timeframe and return count"""
        try:
            result = (
                self.supabase.client.table("ohlc_data")
                .select("timestamp", count="exact")
                .eq("symbol", symbol)
                .eq("timeframe", timeframe)
                .execute()
            )

            count = result.count if hasattr(result, "count") else 0
            has_data = count > 100  # Consider it complete if > 100 bars
            return has_data, count
        except Exception as e:
            logger.error(f"Error checking {symbol} {timeframe}: {e}")
            return False, 0

    def fetch_ohlc_batch(self, symbol: str, timeframe: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Fetch a batch of OHLC data from Polygon"""
        try:
            ticker = f"X:{symbol}USD"

            # Convert timeframe to Polygon format
            multiplier = 1
            if timeframe == "1d":
                timespan = "day"
            elif timeframe == "1h":
                timespan = "hour"
            elif timeframe == "15m":
                multiplier = 15
                timespan = "minute"
            else:  # 1m
                timespan = "minute"

            # Fetch data
            bars = self.client.get_aggs(
                ticker=ticker,
                multiplier=multiplier,
                timespan=timespan,
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
                        "timestamp": pd.Timestamp(bar.timestamp, unit="ms", tz="UTC").isoformat(),
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "open": float(bar.open),
                        "high": float(bar.high),
                        "low": float(bar.low),
                        "close": float(bar.close),
                        "volume": float(bar.volume) if bar.volume else 0,
                        "vwap": (float(bar.vwap) if hasattr(bar, "vwap") and bar.vwap else None),
                        "trades": (int(bar.transactions) if hasattr(bar, "transactions") else None),
                    }
                )

            if not data:
                logger.info(f"No data available for {symbol} {timeframe} from {start_date.date()} to {end_date.date()}")
            else:
                logger.info(f"Fetched {len(data)} bars for {symbol} {timeframe}")

            return data

        except Exception as e:
            logger.error(f"Error fetching {symbol} {timeframe}: {e}")
            return []

    def save_batch(self, data: List[Dict]) -> bool:
        """Save batch to database with retry logic"""
        if not data:
            return True

        max_retries = 3
        batch_size = 1000  # Larger batches since we're doing priority symbols

        for i in range(0, len(data), batch_size):
            batch = data[i : i + batch_size]

            for retry in range(max_retries):
                try:
                    result = self.supabase.client.table("ohlc_data").upsert(batch).execute()
                    logger.success(f"Saved {len(batch)} bars")
                    break
                except Exception as e:
                    logger.error(f"Error saving batch (attempt {retry+1}/{max_retries}): {e}")
                    if retry == max_retries - 1:
                        return False
                    time.sleep(2**retry)  # Exponential backoff

        return True

    def fetch_symbol_timeframe(self, symbol: str, timeframe: str) -> int:
        """Fetch all data for a symbol-timeframe combination"""
        logger.info(f"\n{'='*60}")
        logger.info(f"Fetching {timeframe} data for {symbol}")
        logger.info(f"{'='*60}")

        # Define date ranges based on timeframe
        end_date = datetime.now(tz.utc)
        if timeframe == "1d":
            start_date = end_date - timedelta(days=3650)  # 10 years
            batch_days = 730  # 2 year batches for daily
        else:  # 1h
            start_date = end_date - timedelta(days=1095)  # 3 years
            batch_days = 90  # 3 month batches for hourly

        all_data = []
        current_date = start_date

        while current_date < end_date:
            batch_end = min(current_date + timedelta(days=batch_days), end_date)

            # Fetch batch
            data = self.fetch_ohlc_batch(symbol, timeframe, current_date, batch_end)

            if data:
                all_data.extend(data)
                logger.info(f"Collected {len(data)} bars from {current_date.date()} to {batch_end.date()}")

            current_date = batch_end + timedelta(days=1)

            # Small delay to avoid overwhelming the API
            time.sleep(0.2)

        # Save all data at once for this symbol
        if all_data:
            logger.info(f"Saving {len(all_data)} total bars for {symbol} {timeframe}...")
            if self.save_batch(all_data):
                logger.success(f"✅ Completed {symbol} {timeframe}: {len(all_data)} bars saved")
                return len(all_data)
            else:
                logger.error(f"❌ Failed to save data for {symbol} {timeframe}")
                return 0
        else:
            logger.warning(f"No data found for {symbol} {timeframe}")
            return 0

    def fetch_priority_symbols(self):
        """Main function to fetch priority symbols"""
        logger.info("=" * 80)
        logger.info("PRIORITY SYMBOLS OHLC FETCHER")
        logger.info("=" * 80)

        # Check which priority symbols need data
        missing = {"1d": [], "1h": []}

        logger.info("\nChecking priority symbols...")
        for symbol in self.priority_symbols:
            for tf in ["1d", "1h"]:
                has_data, count = self.check_symbol_data(symbol, tf)
                if not has_data:
                    missing[tf].append(symbol)
                    logger.info(f"  {symbol} {tf}: Missing (only {count} bars)")
                else:
                    logger.success(f"  {symbol} {tf}: ✓ Complete ({count} bars)")

        if not missing["1d"] and not missing["1h"]:
            logger.success("\nAll priority symbols have data!")
            return

        logger.info(f"\nMissing daily data: {', '.join(missing['1d'])}")
        logger.info(f"Missing hourly data: {', '.join(missing['1h'])}")

        # Process each missing symbol
        for timeframe, symbols in missing.items():
            if not symbols:
                continue

            logger.info(f"\n{'#'*80}")
            logger.info(f"Processing {timeframe} timeframe - {len(symbols)} symbols")
            logger.info(f"{'#'*80}")

            for idx, symbol in enumerate(symbols, 1):
                logger.info(f"\n[{idx}/{len(symbols)}] Processing {symbol}")

                try:
                    bars_saved = self.fetch_symbol_timeframe(symbol, timeframe)

                    # Save results
                    if symbol not in self.results:
                        self.results[symbol] = {}
                    self.results[symbol][timeframe] = {
                        "status": "completed" if bars_saved > 0 else "failed",
                        "bars_saved": bars_saved,
                    }

                    # Save results to file
                    with open(self.results_file, "w") as f:
                        json.dump(self.results, f, indent=2)

                except Exception as e:
                    logger.error(f"Failed to process {symbol} {timeframe}: {e}")
                    if symbol not in self.results:
                        self.results[symbol] = {}
                    self.results[symbol][timeframe] = {
                        "status": "failed",
                        "error": str(e),
                    }

                # Delay between symbols
                time.sleep(2)

        # Final summary
        logger.info("\n" + "=" * 80)
        logger.info("PRIORITY SYMBOLS COMPLETE")
        logger.info("=" * 80)

        successful = sum(1 for s in self.results.values() for tf in s.values() if tf.get("status") == "completed")
        failed = sum(1 for s in self.results.values() for tf in s.values() if tf.get("status") == "failed")

        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Results saved to {self.results_file}")


def main():
    fetcher = PriorityOHLCFetcher()
    fetcher.fetch_priority_symbols()


if __name__ == "__main__":
    main()
