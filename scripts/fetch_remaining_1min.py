#!/usr/bin/env python3
"""
Fetch remaining 1-minute OHLC data for failed symbols
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
import requests
from loguru import logger
from dateutil import tz

from src.data.supabase_client import SupabaseClient
from src.config.settings import get_settings

# Configuration
TIMEFRAME = "1m"
LOOKBACK_DAYS = 365  # 1 year of 1-minute data
BATCH_SIZE = 500  # Smaller batch size to avoid conflicts
DELAY_BETWEEN_REQUESTS = 0.1  # For paid Polygon account


def load_failed_symbols() -> List[str]:
    """Load list of failed symbols from previous run"""
    results_file = Path("data/1min_all_symbols_results.json")
    if not results_file.exists():
        logger.error("No results file found")
        return []

    with open(results_file, "r") as f:
        results = json.load(f)

    failed = [sym for sym, data in results.items() if data["status"] == "failed"]
    logger.info(f"Found {len(failed)} failed symbols to retry")
    return failed


def fetch_ohlc_batch(symbol: str, from_date: datetime, to_date: datetime, api_key: str) -> List[Dict[str, Any]]:
    """Fetch OHLC data for a specific date range"""

    url = "https://api.polygon.io/v2/aggs/ticker"
    url += f"/X:{symbol}USD/range/1/minute"
    url += f"/{int(from_date.timestamp() * 1000)}"
    url += f"/{int(to_date.timestamp() * 1000)}"

    params = {"apiKey": api_key, "limit": 50000, "sort": "asc"}

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "OK" and "results" in data:
            bars = data["results"]
            logger.info(f"Fetched {len(bars)} bars for {symbol}")
            return bars
        else:
            logger.info(f"No data available for {symbol} {TIMEFRAME} from {from_date.date()} to {to_date.date()}")
            return []

    except Exception as e:
        logger.error(f"Error fetching {symbol}: {e}")
        return []


def save_batch(client: SupabaseClient, symbol: str, bars: List[Dict]) -> bool:
    """Save a batch of OHLC bars to database"""
    if not bars:
        return True

    try:
        # Process bars in smaller chunks to avoid duplicates
        for i in range(0, len(bars), BATCH_SIZE):
            chunk = bars[i : i + BATCH_SIZE]

            # Remove any duplicate timestamps within this chunk
            seen_timestamps = set()
            unique_bars = []

            for bar in chunk:
                timestamp = datetime.fromtimestamp(bar["t"] / 1000, tz=tz.UTC).isoformat()
                if timestamp not in seen_timestamps:
                    seen_timestamps.add(timestamp)
                    unique_bars.append(
                        {
                            "timestamp": timestamp,
                            "symbol": symbol,
                            "timeframe": TIMEFRAME,
                            "open": bar["o"],
                            "high": bar["h"],
                            "low": bar["l"],
                            "close": bar["c"],
                            "volume": bar["v"],
                            "vwap": bar.get("vw", 0),
                            "trades": bar.get("n", 0),
                        }
                    )

            if unique_bars:
                client.client.table("ohlc_data").upsert(unique_bars).execute()
                logger.success(f"Saved {len(unique_bars)} bars")

        return True

    except Exception as e:
        logger.error(f"Error saving batch: {e}")
        return False


def fetch_symbol(symbol: str, client: SupabaseClient, api_key: str) -> Dict[str, Any]:
    """Fetch all 1-minute data for a symbol"""

    logger.info(f"\n{'='*40}")
    logger.info(f"Fetching {TIMEFRAME} data for {symbol}")
    logger.info(f"{'='*40}")

    end_date = datetime.now(tz.UTC)
    start_date = end_date - timedelta(days=LOOKBACK_DAYS)

    # Check if we already have data
    try:
        result = (
            client.client.table("ohlc_data")
            .select("timestamp")
            .eq("symbol", symbol)
            .eq("timeframe", TIMEFRAME)
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            latest = datetime.fromisoformat(result.data[0]["timestamp"].replace("Z", "+00:00"))
            if latest >= end_date - timedelta(days=1):
                logger.info(f"✅ {symbol} already has recent data, skipping")
                return {"status": "skipped", "bars_saved": 0}
    except:
        pass

    all_bars = []
    current_date = start_date

    # Fetch in 30-day chunks
    while current_date < end_date:
        chunk_end = min(current_date + timedelta(days=30), end_date)

        logger.info(f"Fetching {current_date.date()} to {chunk_end.date()}...")
        bars = fetch_ohlc_batch(symbol, current_date, chunk_end, api_key)

        if bars:
            all_bars.extend(bars)
            logger.info(f"Progress: {current_date.date()} to {chunk_end.date()} - {len(bars)} bars")

        current_date = chunk_end
        time.sleep(DELAY_BETWEEN_REQUESTS)

    # Save all data
    if all_bars:
        logger.info(f"Saving {len(all_bars)} total bars...")
        if save_batch(client, symbol, all_bars):
            logger.success(f"✅ Completed {symbol}: {len(all_bars)} bars")
            return {"status": "completed", "bars_saved": len(all_bars)}
        else:
            logger.error(f"❌ Failed to save {symbol}")
            return {"status": "failed", "bars_saved": 0}
    else:
        logger.warning(f"No data found for {symbol}")
        return {"status": "no_data", "bars_saved": 0}


def main():
    """Main execution"""
    logger.info("=" * 80)
    logger.info("FETCHING REMAINING 1-MINUTE DATA")
    logger.info("=" * 80)

    # Initialize
    settings = get_settings()
    client = SupabaseClient()

    # Load failed symbols
    symbols = load_failed_symbols()

    if not symbols:
        logger.info("No failed symbols to process")
        return

    logger.info(f"Processing {len(symbols)} failed symbols")

    # Process each symbol
    results = {}
    successful = 0
    failed = 0

    for idx, symbol in enumerate(symbols, 1):
        logger.info(f"\n[{idx}/{len(symbols)}] Processing {symbol}")

        result = fetch_symbol(symbol, client, settings.polygon_api_key)
        results[symbol] = result

        if result["status"] == "completed":
            successful += 1
        elif result["status"] == "failed":
            failed += 1

        # Save intermediate results
        if idx % 5 == 0:
            save_results(results)

        # Small delay between symbols
        time.sleep(1)

    # Save final results
    save_results(results)

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("FETCH COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Skipped/No data: {len(symbols) - successful - failed}")


def save_results(results: Dict):
    """Save results to file"""
    # Load existing results
    results_file = Path("data/1min_all_symbols_results.json")
    existing = {}

    if results_file.exists():
        with open(results_file, "r") as f:
            existing = json.load(f)

    # Merge with new results
    existing.update(results)

    # Save
    with open(results_file, "w") as f:
        json.dump(existing, f, indent=2)

    logger.info(f"Results saved to {results_file}")


if __name__ == "__main__":
    main()
