#!/usr/bin/env python3
"""Check current market conditions to see why no signals"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.hybrid_fetcher import HybridDataFetcher
from loguru import logger


async def check_conditions():
    """Check market conditions for signals"""

    fetcher = HybridDataFetcher()

    # Check a few key symbols
    symbols = ["BTC", "ETH", "SOL", "DOGE", "PEPE"]

    for symbol in symbols:
        data = await fetcher.get_recent_data(symbol, hours=4, timeframe="15m")

        if data and len(data) >= 20:
            # Calculate metrics
            closes = [d["close"] for d in data]
            highs = [d["high"] for d in data]
            volumes = [d["volume"] for d in data]

            latest_close = closes[-1]
            recent_high = max(highs[-20:])  # Last 20 bars (5 hours)
            recent_low = min(closes[-20:])
            avg_volume = sum(volumes[-10:]) / 10
            latest_volume = volumes[-1]

            # Check DCA condition (drop from recent high)
            drop_pct = ((latest_close - recent_high) / recent_high) * 100

            # Check Swing condition (recent price change)
            if len(closes) >= 2:
                price_change_pct = ((closes[-1] - closes[-2]) / closes[-2]) * 100
                volume_ratio = latest_volume / avg_volume if avg_volume > 0 else 0
            else:
                price_change_pct = 0
                volume_ratio = 0

            # Check Channel condition
            channel_range = recent_high - recent_low
            if channel_range > 0:
                position_in_channel = (latest_close - recent_low) / channel_range
            else:
                position_in_channel = 0.5

            logger.info(f"\n{symbol}:")
            logger.info(f"  Price: ${latest_close:,.2f}")
            logger.info(f"  Drop from high: {drop_pct:.2f}% (DCA triggers at -3.5%)")
            logger.info(f"  Recent change: {price_change_pct:.2f}% (Swing triggers at +2.1%)")
            logger.info(f"  Volume ratio: {volume_ratio:.2f}x (Swing needs 1.5x)")
            logger.info(f"  Channel position: {position_in_channel:.1%} (signals at <20% or >80%)")

            # Check if close to triggering
            if drop_pct < -2.5:
                logger.warning(f"  → {symbol} approaching DCA trigger!")
            if price_change_pct > 1.5 and volume_ratio > 1.2:
                logger.warning(f"  → {symbol} approaching Swing trigger!")
            if position_in_channel < 0.25 or position_in_channel > 0.75:
                logger.warning(f"  → {symbol} approaching Channel trigger!")


if __name__ == "__main__":
    asyncio.run(check_conditions())
