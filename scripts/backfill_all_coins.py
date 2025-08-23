#!/usr/bin/env python3
"""
Backfill ALL coins with 12 months of historical data.
Optimized for paid Polygon tier with unlimited API calls.
"""

import sys
import os
import subprocess
from datetime import datetime, timezone

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.polygon_client import PolygonWebSocketClient
from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")


def main():
    """Run backfill for all tracked symbols."""

    # Get all symbols we're tracking
    polygon_client = PolygonWebSocketClient()
    all_symbols = polygon_client._get_supported_symbols()

    # Convert to space-separated string for command
    symbols_str = " ".join(all_symbols)

    logger.info("=" * 80)
    logger.info("COMPREHENSIVE HISTORICAL DATA BACKFILL")
    logger.info("=" * 80)
    logger.info(f"Symbols to backfill: {len(all_symbols)} coins")
    logger.info("Time period: 12 months")
    logger.info("Data granularity: 1-minute bars")
    logger.info("API tier: Paid (unlimited calls)")
    logger.info("-" * 80)

    # Estimate time (with paid tier: ~0.1s per request, 12 requests per symbol)
    estimated_minutes = (len(all_symbols) * 12 * 0.1) / 60
    logger.info(f"Estimated completion time: {estimated_minutes:.1f} minutes")
    logger.info("=" * 80)

    # Build the command
    cmd = ["python", "scripts/backfill_historical_data.py", "--symbols"] + all_symbols + ["--months", "12"]

    logger.info("Starting backfill process...")
    logger.info(f"Command: {' '.join(cmd[:5])}... [99 symbols] ... --months 12")

    # Run the backfill
    try:
        result = subprocess.run(cmd, capture_output=False, text=True)
        if result.returncode == 0:
            logger.info("✅ Backfill completed successfully!")
        else:
            logger.error(f"❌ Backfill failed with exit code: {result.returncode}")
    except KeyboardInterrupt:
        logger.warning("Backfill interrupted by user")
    except Exception as e:
        logger.error(f"Error running backfill: {e}")


if __name__ == "__main__":
    main()
