#!/usr/bin/env python3
"""Test if data fetching is working"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.hybrid_fetcher import HybridDataFetcher
from loguru import logger


async def test_fetch():
    """Test data fetching"""

    fetcher = HybridDataFetcher()

    symbols = ["BTC", "ETH", "SOL"]

    for symbol in symbols:
        logger.info(f"\nTesting {symbol}:")

        # Test get_recent_data
        data = await fetcher.get_recent_data(symbol=symbol, hours=4, timeframe="15m")

        if data:
            logger.info(f"✅ Got {len(data)} records for {symbol}")
            logger.info(
                f"   Latest: {data[-1]['timestamp']} - Close: ${data[-1]['close']:,.2f}"
            )
        else:
            logger.warning(f"❌ No data for {symbol}")


if __name__ == "__main__":
    asyncio.run(test_fetch())
