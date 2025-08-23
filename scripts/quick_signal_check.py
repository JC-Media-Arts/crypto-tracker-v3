#!/usr/bin/env python3
"""Quick check why no signals"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.hybrid_fetcher import HybridDataFetcher
from loguru import logger


async def check():
    fetcher = HybridDataFetcher()

    # Just check BTC
    data = await fetcher.get_recent_data("BTC", hours=4, timeframe="15m")

    if not data:
        logger.error("No BTC data!")
        return

    logger.info(f"Got {len(data)} BTC data points")

    if len(data) < 20:
        logger.warning(f"Not enough data for analysis (need 20, have {len(data)})")
        return

    # Quick calculations
    closes = [d["close"] for d in data]
    highs = [d["high"] for d in data[-20:]]

    latest = closes[-1]
    recent_high = max(highs)
    drop = ((latest - recent_high) / recent_high) * 100

    logger.info(f"BTC: ${latest:,.0f}")
    logger.info(f"Recent high: ${recent_high:,.0f}")
    logger.info(f"Drop: {drop:.2f}% (need -3.5% for DCA)")

    if abs(drop) < 1:
        logger.info("→ Market is stable, no big moves")

    # Check last few price changes
    recent_changes = []
    for i in range(-5, -1):
        change = ((closes[i] - closes[i - 1]) / closes[i - 1]) * 100
        recent_changes.append(change)

    logger.info(f"Recent 15m changes: {[f'{c:.2f}%' for c in recent_changes]}")
    max_change = max(abs(c) for c in recent_changes)
    logger.info(f"Biggest recent move: {max_change:.2f}% (need 2.1% for Swing)")


asyncio.run(check())
