#!/usr/bin/env python3
"""
Incremental OHLC Data Updater
Fetches latest OHLC data for all timeframes with smart overlap and error recovery
"""

import os
import sys
import json
import time
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dateutil import tz
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from src.data.supabase_client import SupabaseClient
from loguru import logger
import pandas as pd
import requests

# Configure logging
logger.remove()
logger.add(
    "logs/incremental_updater.log",
    rotation="1 day",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)
logger.add(sys.stdout, level="INFO")


class IncrementalOHLCUpdater:
    """Handles incremental updates for all OHLC timeframes"""

    def __init__(self):
        self.settings = get_settings()
        self.supabase = SupabaseClient()

        # Update configuration
        self.update_config = {
            "1m": {
                "lookback_minutes": 10,  # Fetch last 10 minutes
                "max_days_back": 2,  # Don't go back more than 2 days
                "batch_size": 500,
                "critical": True,
            },
            "15m": {
                "lookback_minutes": 30,  # Fetch last 30 minutes (2 bars)
                "max_days_back": 5,
                "batch_size": 100,
                "critical": True,
            },
            "1h": {
                "lookback_minutes": 120,  # Fetch last 2 hours
                "max_days_back": 7,
                "batch_size": 50,
                "critical": False,
            },
            "1d": {
                "lookback_minutes": 2880,  # Fetch last 2 days
                "max_days_back": 10,
                "batch_size": 10,
                "critical": False,
            },
        }

        # Known symbols that don't have certain timeframe data on Polygon
        self.known_failures = {
            "1m": ["ALGO", "ALT", "ANKR", "API3"],
            "15m": [],
            "1h": ["BNB"],
            "1d": [],
        }

        # Retry configuration
        self.max_retries = 5
        self.retry_delays = [0.1, 0.5, 1.0, 2.0, 4.0]

        # Track update statistics
        self.stats = {
            "symbols_updated": 0,
            "symbols_failed": 0,
            "records_inserted": 0,
            "gaps_detected": 0,
            "start_time": None,
            "end_time": None,
        }

    def get_all_symbols(self) -> List[str]:
        """Get list of all symbols to update"""
        symbols = [
            # Tier 1: Core (20 coins)
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
            # Tier 2: DeFi/Layer 2 (20 coins)
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
            # Tier 3: Trending/Memecoins (20 coins)
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
            # Tier 4: Solid Mid-Caps (40 coins)
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
        return symbols

    def get_latest_timestamp(self, symbol: str, timeframe: str) -> Optional[datetime]:
        """Get the latest timestamp for a symbol/timeframe combination"""
        try:
            response = (
                self.supabase.client.table("ohlc_data")
                .select("timestamp")
                .eq("symbol", symbol)
                .eq("timeframe", timeframe)
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )

            if response.data and len(response.data) > 0:
                timestamp_str = response.data[0]["timestamp"]
                # Parse and ensure timezone aware
                timestamp = pd.to_datetime(timestamp_str)
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=tz.UTC)
                return timestamp
            return None
        except Exception as e:
            logger.error(f"Error getting latest timestamp for {symbol}/{timeframe}: {e}")
            return None

    def fetch_ohlc_from_polygon(
        self, symbol: str, timeframe: str, from_date: datetime, to_date: datetime
    ) -> List[Dict]:
        """Fetch OHLC data from Polygon API"""
        # Map our timeframe to Polygon's multiplier/timespan
        timeframe_map = {
            "1m": (1, "minute"),
            "15m": (15, "minute"),
            "1h": (1, "hour"),
            "1d": (1, "day"),
        }

        multiplier, timespan = timeframe_map[timeframe]

        # Format dates for API
        from_str = from_date.strftime("%Y-%m-%d")
        to_str = to_date.strftime("%Y-%m-%d")

        url = f"https://api.polygon.io/v2/aggs/ticker/X:{symbol}USD/range/{multiplier}/{timespan}/{from_str}/{to_str}"

        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
            "apiKey": self.settings.polygon_api_key,
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            time.sleep(0.1)  # Rate limiting for paid account

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "OK" and "results" in data:
                    return data["results"]
                elif data.get("status") == "ERROR":
                    if "no data" in data.get("message", "").lower():
                        return []  # No data available
            return []
        except Exception as e:
            logger.error(f"Error fetching {symbol}/{timeframe} from Polygon: {e}")
            return []

    def save_ohlc_batch(self, data: List[Dict], symbol: str, timeframe: str) -> int:
        """Save OHLC data batch to database with UPSERT"""
        if not data:
            return 0

        try:
            # Prepare records for insertion
            records = []
            for bar in data:
                record = {
                    "timestamp": datetime.fromtimestamp(bar["t"] / 1000, tz=tz.UTC).isoformat(),
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "open": bar["o"],
                    "high": bar["h"],
                    "low": bar["l"],
                    "close": bar["c"],
                    "volume": bar.get("v", 0),
                    "vwap": bar.get("vw"),
                    "trades": bar.get("n"),
                }
                records.append(record)

            # Use UPSERT to handle duplicates
            response = (
                self.supabase.client.table("ohlc_data")
                .upsert(records, on_conflict="timestamp,symbol,timeframe")
                .execute()
            )

            return len(records)
        except Exception as e:
            logger.error(f"Error saving batch for {symbol}/{timeframe}: {e}")
            return 0

    def update_symbol_timeframe(self, symbol: str, timeframe: str) -> Tuple[bool, int]:
        """Update a single symbol/timeframe combination"""
        # Skip known failures
        if symbol in self.known_failures.get(timeframe, []):
            logger.debug(f"Skipping {symbol}/{timeframe} - known to have no data")
            return True, 0

        config = self.update_config[timeframe]

        # Determine fetch range
        latest_timestamp = self.get_latest_timestamp(symbol, timeframe)

        if latest_timestamp:
            # Start from just before the latest timestamp (overlap)
            from_date = latest_timestamp - timedelta(minutes=config["lookback_minutes"])

            # Don't go back too far
            max_back = datetime.now(tz.UTC) - timedelta(days=config["max_days_back"])
            if from_date < max_back:
                from_date = max_back
        else:
            # No data exists, fetch from max_days_back
            from_date = datetime.now(tz.UTC) - timedelta(days=config["max_days_back"])

        to_date = datetime.now(tz.UTC)

        # Fetch with retries
        for retry in range(self.max_retries):
            data = self.fetch_ohlc_from_polygon(symbol, timeframe, from_date, to_date)

            if data or retry == self.max_retries - 1:
                break

            delay = self.retry_delays[min(retry, len(self.retry_delays) - 1)]
            logger.warning(f"Retry {retry + 1}/{self.max_retries} for {symbol}/{timeframe} after {delay}s")
            time.sleep(delay)

        # Save data
        if data:
            records_saved = self.save_ohlc_batch(data, symbol, timeframe)
            if records_saved > 0:
                logger.info(f"Updated {symbol}/{timeframe}: {records_saved} records")
                return True, records_saved
            else:
                logger.warning(f"No new records for {symbol}/{timeframe}")
                return True, 0
        else:
            if latest_timestamp and (to_date - latest_timestamp).days < 7:
                # If we have recent data, no update needed is OK
                logger.debug(f"No new data for {symbol}/{timeframe} (up to date)")
                return True, 0
            else:
                logger.error(f"Failed to fetch data for {symbol}/{timeframe}")
                return False, 0

    def update_timeframe(self, timeframe: str, symbols: Optional[List[str]] = None) -> Dict:
        """Update all symbols for a specific timeframe"""
        logger.info(f"Starting {timeframe} update")

        if symbols is None:
            symbols = self.get_all_symbols()

        # Filter out known failures
        symbols = [s for s in symbols if s not in self.known_failures.get(timeframe, [])]

        results = {"successful": [], "failed": [], "records_inserted": 0, "duration": 0}

        start_time = time.time()

        # Process symbols in parallel with thread pool
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(self.update_symbol_timeframe, symbol, timeframe): symbol for symbol in symbols}

            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    success, records = future.result(timeout=60)
                    if success:
                        results["successful"].append(symbol)
                        results["records_inserted"] += records
                    else:
                        results["failed"].append(symbol)
                except Exception as e:
                    logger.error(f"Error updating {symbol}/{timeframe}: {e}")
                    results["failed"].append(symbol)

        results["duration"] = time.time() - start_time

        logger.info(
            f"""
        {timeframe} Update Complete:
        - Successful: {len(results['successful'])} symbols
        - Failed: {len(results['failed'])} symbols
        - Records inserted: {results['records_inserted']}
        - Duration: {results['duration']:.1f} seconds
        """
        )

        if results["failed"]:
            logger.warning(f"Failed symbols: {results['failed']}")

        return results

    def update_all_timeframes(self) -> Dict:
        """Update all timeframes in order of priority"""
        self.stats["start_time"] = datetime.now(tz.UTC)

        all_results = {}

        # Update in order of priority
        for timeframe in ["1m", "15m", "1h", "1d"]:
            results = self.update_timeframe(timeframe)
            all_results[timeframe] = results

            self.stats["symbols_updated"] += len(results["successful"])
            self.stats["symbols_failed"] += len(results["failed"])
            self.stats["records_inserted"] += results["records_inserted"]

        self.stats["end_time"] = datetime.now(tz.UTC)

        # Log final statistics
        duration = (self.stats["end_time"] - self.stats["start_time"]).total_seconds()
        logger.info(
            f"""
        ========================================
        INCREMENTAL UPDATE COMPLETE
        ========================================
        Total Duration: {duration:.1f} seconds
        Symbols Updated: {self.stats['symbols_updated']}
        Symbols Failed: {self.stats['symbols_failed']}
        Records Inserted: {self.stats['records_inserted']}
        ========================================
        """
        )

        # Save update record to database
        self.save_update_record(all_results)

        return all_results

    def save_update_record(self, results: Dict):
        """Save update run information to database"""
        try:
            record = {
                "run_type": "incremental",
                "started_at": self.stats["start_time"].isoformat(),
                "completed_at": self.stats["end_time"].isoformat(),
                "symbols_updated": self.stats["symbols_updated"],
                "symbols_failed": self.stats["symbols_failed"],
                "records_inserted": self.stats["records_inserted"],
                "details": json.dumps(results),
            }

            self.supabase.client.table("pipeline_runs").insert(record).execute()
            logger.info("Update record saved to database")
        except Exception as e:
            logger.error(f"Failed to save update record: {e}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Incremental OHLC Data Updater")
    parser.add_argument(
        "--timeframe",
        choices=["1m", "15m", "1h", "1d", "all"],
        default="all",
        help="Timeframe to update",
    )
    parser.add_argument("--symbols", nargs="+", help="Specific symbols to update")

    args = parser.parse_args()

    updater = IncrementalOHLCUpdater()

    if args.timeframe == "all":
        updater.update_all_timeframes()
    else:
        symbols = args.symbols if args.symbols else None
        updater.update_timeframe(args.timeframe, symbols)


if __name__ == "__main__":
    main()
