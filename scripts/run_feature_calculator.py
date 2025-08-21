#!/usr/bin/env python3
"""
Production Feature Calculator Runner

Runs the ML feature calculator continuously for all symbols.
Designed for production deployment on Railway or other cloud platforms.
"""

import asyncio
import time
from datetime import datetime, timezone, timedelta
import sys
import os
import signal

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from src.ml.feature_calculator import FeatureCalculator
from src.data.supabase_client import SupabaseClient
from src.config.settings import get_settings

# Configure logger
logger.remove()
logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
)
logger.add("logs/feature_calculator.log", rotation="100 MB", retention="7 days")

# Get settings
settings = get_settings()

# Define symbols to track (same as in polygon_client.py)
SYMBOLS = [
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

# Global flag for graceful shutdown
shutdown_flag = False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_flag
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_flag = True


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main function to run feature calculator"""
    logger.info("Starting ML Feature Calculator (Production)")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Update interval: {settings.feature_update_interval} seconds")

    calculator = FeatureCalculator()
    supabase = SupabaseClient()
    iteration = 0

    while not shutdown_flag:
        try:
            iteration += 1
            logger.info(f"Starting feature calculation iteration {iteration}")

            start_time = time.time()

            # Check which symbols have enough data
            ready_symbols = []
            for symbol in SYMBOLS:
                end_time = datetime.now(timezone.utc)
                start_time_check = end_time - timedelta(
                    hours=48
                )  # Need 48 hours of data
                price_data = supabase.get_price_data(symbol, start_time_check, end_time)
                if price_data and len(price_data) >= calculator.min_periods:
                    ready_symbols.append(symbol)

            if ready_symbols:
                logger.info(f"Symbols ready for feature calculation: {ready_symbols}")

                # Update features for ready symbols
                results = await calculator.update_all_symbols(ready_symbols)

                # Count successes and failures
                successful = sum(1 for success in results.values() if success)
                failed = len(results) - successful

                elapsed = time.time() - start_time
                logger.info(
                    f"Feature calculation complete in {elapsed:.1f}s - Success: {successful}, Failed: {failed}"
                )
            else:
                logger.warning("No symbols have enough data yet. Waiting...")

            # Wait before next update
            if not shutdown_flag:
                logger.info(
                    f"Waiting {settings.feature_update_interval} seconds before next update..."
                )
                await asyncio.sleep(settings.feature_update_interval)

        except Exception as e:
            logger.error(f"Error in feature calculation loop: {e}")
            if not shutdown_flag:
                logger.info("Waiting 60 seconds before retry...")
                await asyncio.sleep(60)

    logger.info("Feature calculator shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Feature calculator stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
# Force Railway redeploy at Wed Aug 20 20:44:45 PDT 2025
