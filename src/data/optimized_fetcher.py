"""
Optimized data fetcher that leverages partial indexes for performance.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio
import json
from loguru import logger

from src.config.settings import get_settings
from src.data.supabase_client import SupabaseClient


class OptimizedDataFetcher:
    """Optimized data fetcher that uses partial indexes efficiently."""

    def __init__(self):
        """Initialize the optimized fetcher."""
        self.settings = get_settings()
        self.db = SupabaseClient()
        self.cache = {}  # Simple in-memory cache (consider Redis for production)

    async def get_recent_prices(self, symbol: str, hours: int = 24) -> List[Dict]:
        """
        Optimized query for recent data only.
        Uses the partial index for fast retrieval.

        Args:
            symbol: Trading symbol
            hours: Number of hours to look back

        Returns:
            List of OHLC records
        """
        try:
            # Calculate the timestamp cutoff
            cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

            # Use the partial index by querying recent data
            result = (
                self.db.client.table("ohlc_data")
                .select("*")
                .eq("symbol", symbol)
                .gte("timestamp", cutoff)
                .eq("timeframe", "1m")
                .order("timestamp", desc=True)
                .limit(hours * 60)
                .execute()
            )

            logger.debug(f"Fetched {len(result.data)} records for {symbol} (last {hours} hours)")
            return result.data

        except Exception as e:
            logger.error(f"Error fetching recent prices for {symbol}: {e}")
            return []

    async def get_data_for_ml(self, symbols: List[str], days: int = 30) -> Dict[str, List[Dict]]:
        """
        Batch fetch for ML features - optimized for multiple symbols.

        Args:
            symbols: List of trading symbols
            days: Number of days to look back

        Returns:
            Dictionary mapping symbols to their OHLC data
        """
        try:
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
            results = {}

            # Batch fetch with asyncio for parallel processing
            tasks = []
            for symbol in symbols:
                task = self._fetch_symbol_ml_data(symbol, cutoff)
                tasks.append(task)

            # Execute all fetches in parallel
            symbol_data = await asyncio.gather(*tasks, return_exceptions=True)

            # Map results
            for symbol, data in zip(symbols, symbol_data):
                if isinstance(data, Exception):
                    logger.error(f"Failed to fetch ML data for {symbol}: {data}")
                    results[symbol] = []
                else:
                    results[symbol] = data

            return results

        except Exception as e:
            logger.error(f"Error in batch ML data fetch: {e}")
            return {symbol: [] for symbol in symbols}

    async def _fetch_symbol_ml_data(self, symbol: str, cutoff: str) -> List[Dict]:
        """
        Fetch ML data for a single symbol.

        Args:
            symbol: Trading symbol
            cutoff: Timestamp cutoff

        Returns:
            List of OHLC records
        """
        # Get latest prices for each timeframe
        timeframes = ["1d", "1h", "15m"]
        all_data = []

        for tf in timeframes:
            result = (
                self.db.client.table("ohlc_data")
                .select("*")
                .eq("symbol", symbol)
                .eq("timeframe", tf)
                .gte("timestamp", cutoff)
                .order("timestamp", desc=True)
                .execute()
            )

            all_data.extend(result.data)

        return all_data

    async def get_latest_price(self, symbol: str, timeframe: str = "1m") -> Optional[Dict]:
        """
        Get the most recent price for a symbol.
        Optimized for single record retrieval.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe to query

        Returns:
            Latest OHLC record or None
        """
        cache_key = f"latest_{symbol}_{timeframe}"

        # Check cache (5 second TTL for latest prices)
        if cache_key in self.cache:
            cached_time, cached_data = self.cache[cache_key]
            if (datetime.utcnow() - cached_time).total_seconds() < 5:
                return cached_data

        try:
            result = (
                self.db.client.table("ohlc_data")
                .select("*")
                .eq("symbol", symbol)
                .eq("timeframe", timeframe)
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )

            if result.data:
                # Cache the result
                self.cache[cache_key] = (datetime.utcnow(), result.data[0])
                return result.data[0]

            return None

        except Exception as e:
            logger.error(f"Error fetching latest price for {symbol}: {e}")
            return None

    async def get_price_range(
        self, symbol: str, start_time: datetime, end_time: datetime, timeframe: str = "1h"
    ) -> List[Dict]:
        """
        Get prices within a specific time range.
        Optimized to use partial indexes when querying recent data.

        Args:
            symbol: Trading symbol
            start_time: Start of time range
            end_time: End of time range
            timeframe: Timeframe to query

        Returns:
            List of OHLC records
        """
        try:
            # Check if we're querying recent data (can use partial index)
            days_ago = (datetime.utcnow() - start_time).days

            if days_ago <= 7:
                logger.debug(f"Using 7-day partial index for {symbol}")
            elif days_ago <= 30:
                logger.debug(f"Using 30-day partial index for {symbol}")
            else:
                logger.warning(f"Querying historical data beyond partial indexes for {symbol}")

            result = (
                self.db.client.table("ohlc_data")
                .select("*")
                .eq("symbol", symbol)
                .eq("timeframe", timeframe)
                .gte("timestamp", start_time.isoformat())
                .lte("timestamp", end_time.isoformat())
                .order("timestamp", desc=False)
                .execute()
            )

            return result.data

        except Exception as e:
            logger.error(f"Error fetching price range for {symbol}: {e}")
            return []

    async def get_trading_signals_data(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Optimized fetch for trading signal generation.
        Gets just enough recent data for signal calculation.

        Args:
            symbols: List of trading symbols

        Returns:
            Dictionary with signal-ready data for each symbol
        """
        signal_data = {}

        for symbol in symbols:
            try:
                # Get last 100 15-minute candles (25 hours of data)
                recent_15m = (
                    self.db.client.table("ohlc_data")
                    .select("timestamp,close,high,low,volume")
                    .eq("symbol", symbol)
                    .eq("timeframe", "15m")
                    .order("timestamp", desc=True)
                    .limit(100)
                    .execute()
                )

                # Get last 24 hourly candles
                recent_1h = (
                    self.db.client.table("ohlc_data")
                    .select("timestamp,close,high,low,volume")
                    .eq("symbol", symbol)
                    .eq("timeframe", "1h")
                    .order("timestamp", desc=True)
                    .limit(24)
                    .execute()
                )

                signal_data[symbol] = {
                    "15m": recent_15m.data,
                    "1h": recent_1h.data,
                    "latest_price": recent_15m.data[0]["close"] if recent_15m.data else None,
                }

            except Exception as e:
                logger.error(f"Error fetching signal data for {symbol}: {e}")
                signal_data[symbol] = {"15m": [], "1h": [], "latest_price": None}

        return signal_data

    def clear_cache(self):
        """Clear the in-memory cache."""
        self.cache.clear()
        logger.info("Cache cleared")
