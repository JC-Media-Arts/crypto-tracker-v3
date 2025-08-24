#!/usr/bin/env python3
"""
Fetch 15-minute OHLC data for all symbols.
15-minute data is crucial for strategy detection and ML features.
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


class FifteenMinuteFetcher:
    """Fetch 15-minute OHLC data"""

    def __init__(self):
        self.client = RESTClient(api_key=settings.polygon_api_key)
        self.supabase = SupabaseClient()
        self.results_file = Path("data/15min_ohlc_results.json")
        self.results = {}

        # Top coins to fetch (prioritizing most important)
        self.symbols = [
            "BTC",
            "ETH",
            "SOL",
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
            "XLM",
            "IMX",
            "HBAR",
            "VET",
            "THETA",
            "EOS",
            "FTM",
            "ALGO",
            "AAVE",
            "SAND",
            "MANA",
            "AXS",
            "CRV",
            "GALA",
            "CHZ",
            "ZEC",
            "MKR",
            "ENJ",
            "COMP",
            "SNX",
            "BAT",
            "ANKR",
            "YFI",
            "AUDIO",
        ]

    def check_existing_data(self, symbol: str) -> Tuple[bool, int]:
        """Check if symbol already has 15m data"""
        try:
            result = (
                self.supabase.client.table("ohlc_data")
                .select("timestamp", count="exact")
                .eq("symbol", symbol)
                .eq("timeframe", "15m")
                .execute()
            )

            count = result.count if hasattr(result, "count") else 0
            has_data = count > 1000  # Consider complete if > 1000 bars
            return has_data, count
        except Exception as e:
            logger.error(f"Error checking {symbol}: {e}")
            return False, 0

    def fetch_batch(
        self, symbol: str, start_date: datetime, end_date: datetime
    ) -> List[Dict]:
        """Fetch a batch of 15-minute OHLC data"""
        try:
            ticker = f"X:{symbol}USD"

            # 15-minute bars
            bars = self.client.get_aggs(
                ticker=ticker,
                multiplier=15,
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
                        "timeframe": "15m",
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

        batch_size = 1000

        for i in range(0, len(data), batch_size):
            batch = data[i : i + batch_size]

            try:
                result = self.supabase.client.table("ohlc_data").upsert(batch).execute()
                logger.success(f"Saved {len(batch)} bars")
            except Exception as e:
                logger.error(f"Error saving batch: {e}")
                return False

        return True

    def fetch_symbol(self, symbol: str) -> int:
        """Fetch 15-minute data for a symbol"""
        # Check if already have data
        has_data, count = self.check_existing_data(symbol)
        if has_data:
            logger.info(f"✓ {symbol} already has {count} bars, skipping")
            return 0

        logger.info(f"\n{'='*60}")
        logger.info(f"Fetching 15m data for {symbol}")
        logger.info(f"{'='*60}")

        # Fetch 2 years of 15-minute data
        end_date = datetime.now(tz.utc)
        start_date = end_date - timedelta(days=730)  # 2 years

        all_data = []
        current_date = start_date
        batch_days = 30  # 30-day batches

        while current_date < end_date:
            batch_end = min(current_date + timedelta(days=batch_days), end_date)

            # Fetch batch
            data = self.fetch_batch(symbol, current_date, batch_end)

            if data:
                all_data.extend(data)
                logger.info(
                    f"Progress: {current_date.date()} to {batch_end.date()} - {len(data)} bars"
                )

            current_date = batch_end + timedelta(days=1)
            time.sleep(0.2)  # Rate limiting

        # Save all data
        if all_data:
            logger.info(f"Saving {len(all_data)} total bars...")
            if self.save_batch(all_data):
                logger.success(f"✅ Completed {symbol}: {len(all_data)} bars")
                return len(all_data)

        return 0

    def fetch_all(self):
        """Main function to fetch all 15-minute data"""
        logger.info("=" * 80)
        logger.info("15-MINUTE OHLC DATA FETCHER")
        logger.info("=" * 80)
        logger.info(f"Fetching 15-minute data for {len(self.symbols)} symbols")

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

            # Delay between symbols
            time.sleep(1)

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("15-MINUTE DATA COMPLETE")
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
    fetcher = FifteenMinuteFetcher()
    fetcher.fetch_all()


if __name__ == "__main__":
    main()
