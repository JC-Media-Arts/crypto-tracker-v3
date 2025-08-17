#!/usr/bin/env python3
"""
Fetch complete historical OHLC data for all timeframes from Polygon.

This is the ONE-TIME historical backfill script that fetches:
- 10 years of daily data
- 3 years of hourly data  
- 2 years of 15-minute data
- 1 year of minute data

Run this ONCE per symbol to populate historical data for backtesting.
"""

import os
import sys
import time
import requests
import pandas as pd
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv
from loguru import logger
import json

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from src.data.supabase_client import SupabaseClient

# Load environment variables
load_dotenv()

# Backfill configuration
BACKFILL_CONFIG = {
    "1m": {
        "days_to_fetch": 365,  # 1 year of minute data
        "batch_days": 1,  # Fetch 1 day at a time
        "multiplier": 1,
        "timespan": "minute",
        "priority": 4,  # Lowest priority (largest dataset)
    },
    "15m": {
        "days_to_fetch": 730,  # 2 years of 15-min data
        "batch_days": 30,  # Fetch 30 days at a time
        "multiplier": 15,
        "timespan": "minute",
        "priority": 3,
    },
    "1h": {
        "days_to_fetch": 1095,  # 3 years of hourly data
        "batch_days": 90,  # Fetch 90 days at a time
        "multiplier": 1,
        "timespan": "hour",
        "priority": 2,
    },
    "1d": {
        "days_to_fetch": 3650,  # 10 years of daily data
        "batch_days": 365,  # Fetch 1 year at a time
        "multiplier": 1,
        "timespan": "day",
        "priority": 1,  # Highest priority (fastest to complete)
    },
}


class HistoricalOHLCFetcher:
    """Fetch complete historical OHLC data from Polygon REST API."""

    def __init__(self):
        """Initialize the OHLC fetcher."""
        self.settings = get_settings()
        self.api_key = self.settings.polygon_api_key
        self.base_url = "https://api.polygon.io"
        self.supabase = SupabaseClient()
        self.stats = {
            "total_bars_fetched": 0,
            "total_bars_saved": 0,
            "symbols_completed": 0,
            "errors": 0,
        }

    def get_all_symbols(self) -> List[str]:
        """Get list of all symbols to fetch."""
        # Tier 1: Core coins
        tier1 = [
            "BTC",
            "ETH",
            "SOL",
            "BNB",
            "XRP",
            "ADA",
            "AVAX",
            "DOGE",
            "DOT",
            "POL",
            "LINK",
            "TON",
            "SHIB",
            "TRX",
            "UNI",
            "ATOM",
            "BCH",
            "APT",
            "NEAR",
            "ICP",
        ]

        # Tier 2: DeFi/Layer 2
        tier2 = [
            "ARB",
            "OP",
            "AAVE",
            "CRV",
            "MKR",
            "LDO",
            "SUSHI",
            "COMP",
            "SNX",
            "BAL",
            "INJ",
            "SEI",
            "PENDLE",
            "BLUR",
            "ENS",
            "GRT",
            "RENDER",
            "FET",
            "RPL",
            "SAND",
        ]

        # Tier 3: Trending/Memecoins
        tier3 = [
            "PEPE",
            "WIF",
            "BONK",
            "FLOKI",
            "MEME",
            "POPCAT",
            "MEW",
            "TURBO",
            "NEIRO",
            "PNUT",
            "GOAT",
            "ACT",
            "TRUMP",
            "FARTCOIN",
            "MOG",
            "PONKE",
            "TREMP",
            "BRETT",
            "GIGA",
            "HIPPO",
        ]

        # Tier 4: Solid Mid-Caps
        tier4 = [
            "FIL",
            "RUNE",
            "IMX",
            "FLOW",
            "MANA",
            "AXS",
            "CHZ",
            "GALA",
            "LRC",
            "OCEAN",
            "QNT",
            "ALGO",
            "XLM",
            "XMR",
            "ZEC",
            "DASH",
            "HBAR",
            "VET",
            "THETA",
            "EOS",
            "KSM",
            "STX",
            "KAS",
            "TIA",
            "JTO",
            "JUP",
            "PYTH",
            "DYM",
            "STRK",
            "ALT",
            "PORTAL",
            "BEAM",
            "BLUR",
            "MASK",
            "API3",
            "ANKR",
            "CTSI",
            "YFI",
            "AUDIO",
            "ENJ",
        ]

        return tier1 + tier2 + tier3 + tier4

    def check_existing_data(
        self, symbol: str, timeframe: str
    ) -> Tuple[Optional[datetime], int]:
        """
        Check what data already exists for a symbol/timeframe.
        Returns: (latest_timestamp, total_bars)
        """
        try:
            result = (
                self.supabase.client.table("ohlc_data")
                .select("timestamp")
                .eq("symbol", symbol)
                .eq("timeframe", timeframe)
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )

            if result.data and len(result.data) > 0:
                latest = pd.to_datetime(result.data[0]["timestamp"])

                # Get count
                count_result = (
                    self.supabase.client.table("ohlc_data")
                    .select("timestamp", count="exact")
                    .eq("symbol", symbol)
                    .eq("timeframe", timeframe)
                    .execute()
                )

                total_bars = (
                    count_result.count
                    if hasattr(count_result, "count")
                    else len(count_result.data)
                )

                logger.info(
                    f"Found existing data for {symbol} {timeframe}: {total_bars} bars, latest: {latest}"
                )
                return latest, total_bars

        except Exception as e:
            logger.error(f"Error checking existing data: {e}")

        return None, 0

    def fetch_ohlc_batch(
        self, symbol: str, timeframe: str, from_date: str, to_date: str
    ) -> Optional[pd.DataFrame]:
        """
        Fetch a batch of OHLC bars from Polygon.
        """
        config = BACKFILL_CONFIG[timeframe]
        ticker = f"X:{symbol}USD"

        url = f"{self.base_url}/v2/aggs/ticker/{ticker}/range/{config['multiplier']}/{config['timespan']}/{from_date}/{to_date}"

        params = {
            "apiKey": self.api_key,
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,  # Max allowed
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if data.get("status") != "OK":
                logger.warning(
                    f"API returned status {data.get('status')} for {symbol} {timeframe}"
                )
                return None

            if "results" not in data or not data["results"]:
                logger.info(
                    f"No data available for {symbol} {timeframe} from {from_date} to {to_date}"
                )
                return None

            # Convert to DataFrame
            df = pd.DataFrame(data["results"])

            # Rename columns
            df = df.rename(
                columns={
                    "t": "timestamp",
                    "o": "open",
                    "h": "high",
                    "l": "low",
                    "c": "close",
                    "v": "volume",
                    "vw": "vwap",
                    "n": "trades",
                }
            )

            # Convert timestamp from milliseconds to datetime
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)

            # Add symbol and timeframe
            df["symbol"] = symbol
            df["timeframe"] = timeframe

            # Ensure we have all required columns
            if "vwap" not in df.columns:
                df["vwap"] = df["close"]  # Use close as fallback
            if "trades" not in df.columns:
                df["trades"] = 0

            logger.info(
                f"Fetched {len(df)} bars for {symbol} {timeframe} from {from_date} to {to_date}"
            )
            self.stats["total_bars_fetched"] += len(df)

            return df

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for {symbol} {timeframe}: {e}")
            self.stats["errors"] += 1
            return None
        except Exception as e:
            logger.error(f"Unexpected error for {symbol} {timeframe}: {e}")
            self.stats["errors"] += 1
            return None

    def save_ohlc_batch(self, df: pd.DataFrame) -> int:
        """Save OHLC data to database."""
        if df.empty:
            return 0

        # Prepare records for insertion
        records = []
        for _, row in df.iterrows():
            record = {
                "timestamp": row["timestamp"].isoformat(),
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row.get("volume", 0)),
                "vwap": float(row.get("vwap", row["close"])),
                "trades": int(row.get("trades", 0)),
            }
            records.append(record)

        # Insert in batches with upsert
        batch_size = 1000
        saved_count = 0

        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            try:
                result = (
                    self.supabase.client.table("ohlc_data")
                    .upsert(batch, on_conflict="symbol,timeframe,timestamp")
                    .execute()
                )

                if result.data:
                    saved_count += len(result.data)
            except Exception as e:
                logger.error(f"Error saving batch: {e}")
                self.stats["errors"] += 1

        self.stats["total_bars_saved"] += saved_count
        return saved_count

    def fetch_timeframe_for_symbol(
        self, symbol: str, timeframe: str, force_refetch: bool = False
    ) -> Dict:
        """
        Fetch all historical data for a symbol/timeframe combination.
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Fetching {timeframe} data for {symbol}")
        logger.info(f"{'='*60}")

        config = BACKFILL_CONFIG[timeframe]

        # Check existing data
        latest_timestamp, existing_bars = self.check_existing_data(symbol, timeframe)

        # Calculate date range (use UTC for consistency)
        from datetime import timezone as tz

        end_date = datetime.now(tz.utc)

        if force_refetch or latest_timestamp is None:
            # Fetch full history
            start_date = end_date - timedelta(days=config["days_to_fetch"])
            logger.info(f"Fetching full history: {config['days_to_fetch']} days")
        else:
            # Only fetch new data since latest
            # Ensure latest_timestamp is timezone-aware
            if latest_timestamp.tzinfo is None:
                latest_timestamp = latest_timestamp.replace(tzinfo=tz.utc)
            start_date = latest_timestamp + timedelta(minutes=1)
            if start_date >= end_date:
                logger.info(f"Data is up to date for {symbol} {timeframe}")
                return {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "new_bars": 0,
                    "total_bars": existing_bars,
                }

        # Fetch in batches
        total_fetched = 0
        current_start = start_date

        while current_start < end_date:
            # Calculate batch end
            batch_end = min(
                current_start + timedelta(days=config["batch_days"]), end_date
            )

            # Format dates for API
            from_str = current_start.strftime("%Y-%m-%d")
            to_str = batch_end.strftime("%Y-%m-%d")

            # Fetch batch
            df = self.fetch_ohlc_batch(symbol, timeframe, from_str, to_str)

            if df is not None and not df.empty:
                # Save to database
                saved = self.save_ohlc_batch(df)
                total_fetched += saved
                logger.info(f"Saved {saved} bars for batch {from_str} to {to_str}")

            # Move to next batch
            current_start = batch_end + timedelta(days=1)

            # Small delay to be respectful
            time.sleep(0.1)

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "new_bars": total_fetched,
            "total_bars": existing_bars + total_fetched,
        }

    def fetch_all_timeframes_for_symbol(
        self, symbol: str, timeframes: List[str] = None
    ) -> Dict:
        """
        Fetch all timeframes for a single symbol.
        Processes in priority order (daily first, then hourly, etc.)
        """
        if timeframes is None:
            # Sort by priority (daily first)
            timeframes = sorted(
                BACKFILL_CONFIG.keys(), key=lambda x: BACKFILL_CONFIG[x]["priority"]
            )

        results = {}

        for tf in timeframes:
            result = self.fetch_timeframe_for_symbol(symbol, tf)
            results[tf] = result

            # Log progress
            logger.info(
                f"Progress for {symbol}: {tf} complete with {result['new_bars']} new bars"
            )

        self.stats["symbols_completed"] += 1
        return results

    def fetch_all_symbols(
        self, symbols: List[str] = None, timeframes: List[str] = None
    ) -> Dict:
        """
        Fetch data for all symbols and timeframes.
        """
        if symbols is None:
            symbols = self.get_all_symbols()

        all_results = {}

        for idx, symbol in enumerate(symbols, 1):
            logger.info(f"\n{'#'*80}")
            logger.info(f"Processing symbol {idx}/{len(symbols)}: {symbol}")
            logger.info(f"{'#'*80}")

            results = self.fetch_all_timeframes_for_symbol(symbol, timeframes)
            all_results[symbol] = results

            # Print summary for this symbol
            total_new = sum(r["new_bars"] for r in results.values())
            logger.info(
                f"Completed {symbol}: {total_new} new bars across all timeframes"
            )

        return all_results

    def print_final_summary(self):
        """Print final summary statistics."""
        print("\n" + "=" * 80)
        print("HISTORICAL BACKFILL COMPLETE")
        print("=" * 80)
        print(f"Total bars fetched: {self.stats['total_bars_fetched']:,}")
        print(f"Total bars saved: {self.stats['total_bars_saved']:,}")
        print(f"Symbols completed: {self.stats['symbols_completed']}")
        print(f"Errors encountered: {self.stats['errors']}")
        print("=" * 80)


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Fetch historical OHLC data from Polygon"
    )
    parser.add_argument(
        "--timeframe", type=str, help="Specific timeframe (1m, 15m, 1h, 1d)"
    )
    parser.add_argument("--symbol", type=str, help="Specific symbol to fetch")
    parser.add_argument("--all-symbols", action="store_true", help="Fetch all symbols")
    parser.add_argument(
        "--test", action="store_true", help="Test mode - only fetch BTC"
    )

    args = parser.parse_args()

    print("=" * 80)
    print("POLYGON HISTORICAL OHLC FETCHER")
    print("=" * 80)

    fetcher = HistoricalOHLCFetcher()

    # Determine what to fetch
    if args.test:
        symbols = ["BTC"]
        timeframes = ["1d", "1h"]  # Just daily and hourly for testing
        print("TEST MODE: Fetching only BTC daily and hourly data")
    elif args.symbol:
        symbols = [args.symbol]
        timeframes = [args.timeframe] if args.timeframe else None
        print(f"Fetching {args.symbol} for {timeframes or 'all timeframes'}")
    elif args.all_symbols:
        symbols = None  # Will use all
        timeframes = [args.timeframe] if args.timeframe else None
        print(f"Fetching all symbols for {timeframes or 'all timeframes'}")
    else:
        print("Please specify --symbol, --all-symbols, or --test")
        return

    # Start fetching
    start_time = time.time()
    results = fetcher.fetch_all_symbols(symbols, timeframes)

    # Print summary
    fetcher.print_final_summary()

    elapsed = time.time() - start_time
    print(f"\nTotal time: {elapsed/60:.1f} minutes")

    # Save results to file for reference
    with open("data/backfill_results.json", "w") as f:
        # Convert to serializable format
        serializable_results = {}
        for symbol, tfs in results.items():
            serializable_results[symbol] = {
                tf: {k: v for k, v in data.items()} for tf, data in tfs.items()
            }
        json.dump(serializable_results, f, indent=2)
        print(f"\nResults saved to data/backfill_results.json")


if __name__ == "__main__":
    main()
