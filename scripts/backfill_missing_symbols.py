#!/usr/bin/env python3
"""
Simple backfill script for missing symbols
Fetches historical OHLC data for symbols that don't have data yet
"""

import os
import sys
import time
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict
import logging

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from supabase import create_client, Client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class SimpleBackfiller:
    """Simple backfiller for missing OHLC data"""

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.polygon_api_key
        self.supabase = create_client(settings.supabase_url, settings.supabase_key)
        self.base_url = "https://api.polygon.io"

    def get_missing_symbols(self) -> List[str]:
        """Get list of symbols that need backfilling"""

        # All configured symbols (90 total)
        all_symbols = [
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
            # Tier 4: Solid Mid-Caps (30 coins)
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
        ]

        # Get symbols that already have data
        try:
            result = self.supabase.table("ohlc_data").select("symbol").execute()
            existing = (
                set(row["symbol"] for row in result.data) if result.data else set()
            )

            # Return symbols that need backfilling
            missing = [s for s in all_symbols if s not in existing]
            logger.info(
                f"Found {len(missing)} symbols to backfill out of {len(all_symbols)}"
            )
            return missing

        except Exception as e:
            logger.error(f"Error checking existing symbols: {e}")
            return all_symbols

    def fetch_ohlc_for_symbol(
        self, symbol: str, timeframe: str = "1d", days_back: int = 30
    ) -> List[Dict]:
        """Fetch OHLC data for a single symbol"""

        ticker = f"X:{symbol}USD"
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        # Map timeframe to Polygon parameters
        timeframe_map = {
            "1m": (1, "minute"),
            "15m": (15, "minute"),
            "1h": (1, "hour"),
            "1d": (1, "day"),
        }

        multiplier, timespan = timeframe_map.get(timeframe, (1, "day"))

        url = f"{self.base_url}/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"

        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
            "apiKey": self.api_key,
        }

        try:
            response = requests.get(url, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()

                if data.get("results"):
                    bars = []
                    for bar in data["results"]:
                        bars.append(
                            {
                                "symbol": symbol,
                                "timeframe": timeframe,
                                "timestamp": datetime.fromtimestamp(
                                    bar["t"] / 1000
                                ).isoformat(),
                                "open": bar["o"],
                                "high": bar["h"],
                                "low": bar["l"],
                                "close": bar["c"],
                                "volume": bar.get("v", 0),
                                "vwap": bar.get("vw", bar["c"]),
                                "trades": bar.get("n", 0),
                            }
                        )

                    logger.info(f"✅ {symbol} {timeframe}: Fetched {len(bars)} bars")
                    return bars
                else:
                    logger.warning(f"⚠️  {symbol} {timeframe}: No data available")
                    return []

            elif response.status_code == 429:
                logger.error(f"❌ Rate limited! Waiting 60 seconds...")
                time.sleep(60)
                return []
            else:
                logger.error(f"❌ {symbol}: HTTP {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"❌ {symbol}: Error fetching - {e}")
            return []

    def save_to_database(self, bars: List[Dict]) -> int:
        """Save OHLC bars to database"""

        if not bars:
            return 0

        try:
            # Use upsert to handle duplicates
            result = self.supabase.table("ohlc_data").upsert(bars).execute()

            if result.data:
                return len(result.data)
            else:
                return 0

        except Exception as e:
            if "duplicate" not in str(e).lower():
                logger.error(f"Error saving to database: {e}")
            return 0

    def backfill_symbol(
        self, symbol: str, timeframes: List[str] = None, days_back: int = 30
    ):
        """Backfill a single symbol with multiple timeframes"""

        if timeframes is None:
            timeframes = ["1d", "1h", "15m"]  # Skip 1m for now (too much data)

        logger.info(f"\n{'='*60}")
        logger.info(f"Backfilling {symbol}")
        logger.info(f"{'='*60}")

        total_saved = 0

        for timeframe in timeframes:
            # Adjust days back based on timeframe
            if timeframe == "1m":
                days = min(days_back, 7)  # Max 7 days for minute data
            elif timeframe == "15m":
                days = min(days_back, 90)  # Max 90 days for 15m
            else:
                days = days_back

            bars = self.fetch_ohlc_for_symbol(symbol, timeframe, days)

            if bars:
                saved = self.save_to_database(bars)
                total_saved += saved
                logger.info(f"   Saved {saved} {timeframe} bars to database")

            # Small delay to avoid rate limiting
            time.sleep(0.5)

        logger.info(f"✅ {symbol}: Total {total_saved} bars saved")
        return total_saved

    def run_backfill(self, max_symbols: int = 10):
        """Run backfill for missing symbols"""

        logger.info("\n" + "=" * 80)
        logger.info("STARTING BACKFILL PROCESS")
        logger.info("=" * 80)

        missing_symbols = self.get_missing_symbols()

        if not missing_symbols:
            logger.info("✅ All symbols already have data!")
            return

        # Limit number of symbols to avoid rate limiting
        symbols_to_process = missing_symbols[:max_symbols]

        logger.info(
            f"Will backfill {len(symbols_to_process)} symbols: {', '.join(symbols_to_process)}"
        )

        total_bars = 0
        successful = 0

        for i, symbol in enumerate(symbols_to_process, 1):
            logger.info(f"\nProgress: {i}/{len(symbols_to_process)}")

            saved = self.backfill_symbol(symbol, days_back=90)  # 90 days of history

            if saved > 0:
                successful += 1
                total_bars += saved

            # Longer delay between symbols to avoid rate limiting
            if i < len(symbols_to_process):
                logger.info("Waiting 2 seconds before next symbol...")
                time.sleep(2)

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("BACKFILL COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Symbols processed: {len(symbols_to_process)}")
        logger.info(f"Successful: {successful}")
        logger.info(f"Total bars saved: {total_bars:,}")

        if len(missing_symbols) > max_symbols:
            logger.info(
                f"\n⚠️  {len(missing_symbols) - max_symbols} symbols still need backfilling"
            )
            logger.info("Run this script again to continue")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Backfill missing OHLC data")
    parser.add_argument(
        "--symbols",
        type=int,
        default=5,
        help="Number of symbols to backfill (default: 5)",
    )
    parser.add_argument(
        "--days", type=int, default=90, help="Days of history to fetch (default: 90)"
    )

    args = parser.parse_args()

    backfiller = SimpleBackfiller()
    backfiller.run_backfill(max_symbols=args.symbols)


if __name__ == "__main__":
    main()
