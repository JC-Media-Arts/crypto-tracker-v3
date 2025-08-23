#!/usr/bin/env python3
"""
Fetch missing 15-minute OHLC data for symbols that don't have it yet.
Specifically targets the 63 symbols missing 15m data.
"""

import sys
import json
import time
from datetime import datetime, timedelta, timezone as tz
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd
from polygon import RESTClient
from loguru import logger

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from src.config.settings import get_settings


class Missing15MinFetcher:
    def __init__(self):
        settings = get_settings()
        self.client = RESTClient(api_key=settings.polygon_api_key)
        self.supabase = SupabaseClient()

        # Symbols that are missing 15m data (from our check)
        self.missing_symbols = [
            "ALT",
            "API3",
            "APT",
            "ARB",
            "AXS",
            "BAL",
            "BEAM",
            "BLUR",
            "BONK",
            "CHZ",
            "CRV",
            "CTSI",
            "DASH",
            "ENS",
            "FET",
            "FIL",
            "FLOKI",
            "FLOW",
            "GALA",
            "GIGA",
            "GOAT",
            "GRT",
            "INJ",
            "JTO",
            "JUP",
            "KAS",
            "KSM",
            "LDO",
            "LRC",
            "MANA",
            "MASK",
            "MEME",
            "MEW",
            "MKR",
            "MOG",
            "NEAR",
            "NEIRO",
            "OCEAN",
            "OP",
            "PENDLE",
            "PEPE",
            "PNUT",
            "POL",
            "PONKE",
            "POPCAT",
            "PYTH",
            "QNT",
            "RENDER",
            "RPL",
            "RUNE",
            "SAND",
            "SEI",
            "SHIB",
            "STRK",
            "STX",
            "SUSHI",
            "TIA",
            "TON",
            "TRUMP",
            "TURBO",
            "WIF",
            "XMR",
            "ZEC",
        ]

        # Results tracking
        self.results = {}

    def check_existing_data(self, symbol: str) -> bool:
        """Check if symbol already has 15m data"""
        try:
            result = (
                self.supabase.client.table("ohlc_data")
                .select("symbol")
                .eq("symbol", symbol)
                .eq("timeframe", "15m")
                .limit(1)
                .execute()
            )

            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error checking existing data for {symbol}: {e}")
            return False

    def fetch_batch(self, symbol: str, from_date: str, to_date: str) -> List[Dict]:
        """Fetch a batch of 15-minute bars"""
        try:
            # Add X: prefix for Polygon API
            polygon_symbol = f"X:{symbol}USD"

            # Fetch 15-minute bars
            bars = self.client.get_aggs(
                ticker=polygon_symbol,
                multiplier=15,
                timespan="minute",
                from_=from_date,
                to=to_date,
                adjusted=True,
                sort="asc",
                limit=50000,
            )

            if bars:
                logger.info(f"Fetched {len(bars)} bars for {symbol}")
                return bars
            else:
                logger.warning(f"No data available for {symbol} from {from_date} to {to_date}")
                return []

        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
            return []

    def save_batch(self, symbol: str, bars: List) -> bool:
        """Save batch of bars to database"""
        if not bars:
            return True

        try:
            # Convert to records for database
            records = []
            for bar in bars:
                records.append(
                    {
                        "timestamp": datetime.fromtimestamp(bar.timestamp / 1000, tz=tz.utc).isoformat(),
                        "symbol": symbol,
                        "timeframe": "15m",
                        "open": float(bar.open),
                        "high": float(bar.high),
                        "low": float(bar.low),
                        "close": float(bar.close),
                        "volume": float(bar.volume) if bar.volume else 0,
                        "vwap": (float(bar.vwap) if hasattr(bar, "vwap") and bar.vwap else None),
                        "trades": (int(bar.transactions) if hasattr(bar, "transactions") else None),
                    }
                )

            # Save in batches of 1000
            batch_size = 1000
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]
                self.supabase.client.table("ohlc_data").upsert(
                    batch, on_conflict="symbol,timeframe,timestamp"
                ).execute()
                logger.success(f"Saved {len(batch)} bars")

            return True

        except Exception as e:
            logger.error(f"Error saving batch: {e}")
            return False

    def fetch_symbol(self, symbol: str) -> Dict:
        """Fetch 2 years of 15-minute data for a symbol"""
        logger.info(f"\n{'=' * 40}")
        logger.info(f"Fetching 15m data for {symbol}")
        logger.info(f"{'=' * 40}")

        # Check if already has data
        if self.check_existing_data(symbol):
            logger.info(f"✓ {symbol} already has 15m data, skipping")
            return {"status": "skipped", "bars_saved": 0}

        # Calculate date range (2 years of data)
        end_date = datetime.now(tz.utc)
        start_date = end_date - timedelta(days=730)  # 2 years

        all_bars = []
        current_start = start_date

        # Fetch in 30-day batches
        while current_start < end_date:
            batch_end = min(current_start + timedelta(days=30), end_date)

            from_str = current_start.strftime("%Y-%m-%d")
            to_str = batch_end.strftime("%Y-%m-%d")

            logger.info(f"Fetching {from_str} to {to_str}...")
            bars = self.fetch_batch(symbol, from_str, to_str)

            if bars:
                all_bars.extend(bars)
                logger.info(f"Progress: {from_str} to {to_str} - {len(bars)} bars")

            current_start = batch_end
            time.sleep(0.5)  # Rate limiting

        # Save all bars
        if all_bars:
            logger.info(f"Saving {len(all_bars)} total bars...")
            if self.save_batch(symbol, all_bars):
                logger.success(f"✅ Completed {symbol}: {len(all_bars)} bars")
                return {"status": "completed", "bars_saved": len(all_bars)}
            else:
                logger.error(f"❌ Failed to save {symbol}")
                return {"status": "failed", "bars_saved": 0}
        else:
            logger.warning(f"No data found for {symbol}")
            return {"status": "no_data", "bars_saved": 0}

    def fetch_all(self):
        """Fetch data for all missing symbols"""
        logger.info("\n" + "=" * 60)
        logger.info("FETCHING MISSING 15-MINUTE DATA")
        logger.info(f"Processing {len(self.missing_symbols)} symbols")
        logger.info("=" * 60)

        successful = []
        failed = []
        skipped = []

        for i, symbol in enumerate(self.missing_symbols, 1):
            logger.info(f"\n[{i}/{len(self.missing_symbols)}] Processing {symbol}")

            try:
                result = self.fetch_symbol(symbol)
                self.results[symbol] = result

                if result["status"] == "completed":
                    successful.append(symbol)
                elif result["status"] == "skipped":
                    skipped.append(symbol)
                else:
                    failed.append(symbol)

            except Exception as e:
                logger.error(f"Unexpected error for {symbol}: {e}")
                failed.append(symbol)
                self.results[symbol] = {"status": "error", "bars_saved": 0}

            # Save progress after each symbol
            self.save_results()

        # Final summary
        logger.info("\n" + "=" * 60)
        logger.info("15-MINUTE DATA FETCH COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Successful: {len(successful)}")
        logger.info(f"Skipped (already had data): {len(skipped)}")
        logger.info(f"Failed: {len(failed)}")

        if failed:
            logger.warning(f"Failed symbols: {', '.join(failed)}")

    def save_results(self):
        """Save results to file"""
        results_file = Path("data/missing_15min_results.json")
        with open(results_file, "w") as f:
            json.dump(self.results, f, indent=2)
        logger.info(f"Results saved to {results_file}")


def main():
    fetcher = Missing15MinFetcher()
    fetcher.fetch_all()


if __name__ == "__main__":
    main()
