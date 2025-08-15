#!/usr/bin/env python3
"""
Run ML Feature Calculator (Development Mode)
Runs with reduced data requirements for testing
"""
import asyncio
import time
from datetime import datetime, timezone, timedelta
from loguru import logger
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ml.feature_calculator import FeatureCalculator
from src.data.supabase_client import SupabaseClient


async def main():
    """Main function to run feature calculator"""
    logger.info("Starting ML Feature Calculator (Dev Mode - Reduced Requirements)")

    calculator = FeatureCalculator()
    supabase = SupabaseClient()

    # Reduce minimum periods for development
    calculator.min_periods = 30
    logger.info(f"Running with reduced minimum periods: {calculator.min_periods}")

    # Get list of symbols that have data
    symbols = ["BTC", "ETH", "SOL", "XRP", "ADA", "AVAX", "DOGE", "DOT", "LINK", "ATOM"]

    iteration = 0
    while True:
        try:
            iteration += 1
            logger.info(f"Starting feature calculation iteration {iteration}")
            start_time = time.time()

            # Check which symbols have enough data
            ready_symbols = []
            for symbol in symbols:
                end_time = datetime.now(timezone.utc)
                start_time_check = end_time - timedelta(hours=24)
                price_data = supabase.get_price_data(symbol, start_time_check, end_time)
                if price_data and len(price_data) >= calculator.min_periods:
                    ready_symbols.append(symbol)

            logger.info(f"Symbols ready for feature calculation: {ready_symbols}")

            # Update features for ready symbols
            if ready_symbols:
                results = calculator.update_all_symbols(ready_symbols)

                # Log results
                successful = sum(1 for success in results.values() if success)
                failed = len(results) - successful

                elapsed = time.time() - start_time
                logger.info(
                    f"Feature calculation complete in {elapsed:.1f}s - Success: {successful}, Failed: {failed}"
                )
            else:
                logger.warning("No symbols have enough data yet. Waiting...")

            # Wait before next update (2 minutes in dev mode)
            logger.info("Waiting 2 minutes before next update...")
            await asyncio.sleep(120)

        except KeyboardInterrupt:
            logger.info("Shutting down feature calculator...")
            break
        except Exception as e:
            logger.error(f"Error in feature calculator: {e}")
            import traceback

            traceback.print_exc()
            await asyncio.sleep(60)  # Wait 1 minute on error


if __name__ == "__main__":
    asyncio.run(main())
