"""
OHLC Data Manager with automatic archive routing.
Handles queries across main and archive tables transparently.
"""

from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
import asyncio
import json
from loguru import logger

from src.config.settings import get_settings
from src.data.supabase_client import SupabaseClient
from src.data.optimized_fetcher import OptimizedDataFetcher


class OHLCDataManager:
    """
    Manages OHLC data access across main and archive tables.
    Automatically routes queries to the appropriate table based on date ranges.
    """

    def __init__(self):
        """Initialize the OHLC data manager."""
        self.settings = get_settings()
        self.db = SupabaseClient()
        self.optimized_fetcher = OptimizedDataFetcher()

        # Threshold for what's considered "recent" data (in main table)
        self.recent_days_threshold = 365  # 1 year in main table
        self.archive_cutoff = datetime.utcnow() - timedelta(
            days=self.recent_days_threshold
        )

        # Cache for frequently accessed data
        self.cache = {}
        self.cache_ttl = {
            "recent": 300,
            "historical": 3600,
        }  # 5 minutes for recent data  # 1 hour for historical data

    async def get_ohlc_data(
        self, symbol: str, timeframe: str, start_date: datetime, end_date: datetime
    ) -> List[Dict]:
        """
        Automatically routes queries to correct table(s).

        Args:
            symbol: Trading symbol
            timeframe: Timeframe (1m, 15m, 1h, 1d)
            start_date: Start of date range
            end_date: End of date range

        Returns:
            Combined list of OHLC records from appropriate tables
        """
        # Determine which table(s) to query
        use_archive = start_date < self.archive_cutoff
        use_main = end_date >= self.archive_cutoff

        results = []

        try:
            if use_archive:
                # Query archive for historical data
                logger.debug(f"Querying archive for {symbol} historical data")
                archive_data = await self.query_archive(
                    symbol, timeframe, start_date, min(end_date, self.archive_cutoff)
                )
                results.extend(archive_data)

            if use_main:
                # Query main table for recent data
                logger.debug(f"Querying main table for {symbol} recent data")
                main_data = await self.query_main(
                    symbol, timeframe, max(start_date, self.archive_cutoff), end_date
                )
                results.extend(main_data)

            # Sort by timestamp
            results.sort(key=lambda x: x["timestamp"])

            logger.info(f"Retrieved {len(results)} records for {symbol} {timeframe}")
            return results

        except Exception as e:
            logger.error(f"Error fetching OHLC data: {e}")
            return []

    async def query_main(
        self, symbol: str, timeframe: str, start_date: datetime, end_date: datetime
    ) -> List[Dict]:
        """
        Query the main OHLC table (recent data).

        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            start_date: Start date
            end_date: End date

        Returns:
            List of OHLC records
        """
        # Check if we can use optimized fetcher for recent data
        days_ago = (datetime.utcnow() - start_date).days

        if days_ago <= 30:
            # Use optimized fetcher for recent data
            return await self.optimized_fetcher.get_price_range(
                symbol, start_date, end_date, timeframe
            )

        # Fallback to standard query for older data
        result = (
            self.db.client.table("ohlc_data")
            .select("*")
            .eq("symbol", symbol)
            .eq("timeframe", timeframe)
            .gte("timestamp", start_date.isoformat())
            .lte("timestamp", end_date.isoformat())
            .order("timestamp")
            .execute()
        )

        return result.data

    async def query_archive(
        self, symbol: str, timeframe: str, start_date: datetime, end_date: datetime
    ) -> List[Dict]:
        """
        Query the archive OHLC table (historical data).

        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            start_date: Start date
            end_date: End date

        Returns:
            List of OHLC records
        """
        try:
            # Check if archive table exists
            result = (
                self.db.client.table("ohlc_data_archive")
                .select("*")
                .eq("symbol", symbol)
                .eq("timeframe", timeframe)
                .gte("timestamp", start_date.isoformat())
                .lte("timestamp", end_date.isoformat())
                .order("timestamp")
                .execute()
            )

            return result.data

        except Exception as e:
            # Archive table might not exist yet
            logger.warning(f"Archive table not accessible: {e}")
            return []

    async def query_with_cache(
        self, symbol: str, timeframe: str, start_date: datetime, end_date: datetime
    ) -> List[Dict]:
        """
        Query with caching for frequently accessed data.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            start_date: Start date
            end_date: End date

        Returns:
            Cached or fresh OHLC data
        """
        # Generate cache key
        cache_key = (
            f"{symbol}:{timeframe}:{start_date.isoformat()}:{end_date.isoformat()}"
        )

        # Check cache
        if cache_key in self.cache:
            cached_time, cached_data = self.cache[cache_key]

            # Determine TTL based on data recency
            is_recent = end_date > datetime.utcnow() - timedelta(days=1)
            ttl = (
                self.cache_ttl["recent"] if is_recent else self.cache_ttl["historical"]
            )

            # Return cached data if still valid
            if (datetime.utcnow() - cached_time).total_seconds() < ttl:
                logger.debug(f"Cache hit for {cache_key}")
                return cached_data

        # Fetch from database
        data = await self.get_ohlc_data(symbol, timeframe, start_date, end_date)

        # Update cache
        self.cache[cache_key] = (datetime.utcnow(), data)

        # Limit cache size (simple LRU)
        if len(self.cache) > 100:
            # Remove oldest entries
            oldest_keys = sorted(self.cache.keys(), key=lambda k: self.cache[k][0])[:20]
            for key in oldest_keys:
                del self.cache[key]

        return data

    async def get_latest_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        Get latest prices for multiple symbols efficiently.

        Args:
            symbols: List of trading symbols

        Returns:
            Dictionary mapping symbols to their latest prices
        """
        prices = {}

        # Use optimized fetcher for recent prices
        tasks = []
        for symbol in symbols:
            task = self.optimized_fetcher.get_latest_price(symbol, "1m")
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to get price for {symbol}: {result}")
                prices[symbol] = None
            elif result:
                prices[symbol] = result.get("close")
            else:
                prices[symbol] = None

        return prices

    async def get_ml_training_data(
        self, symbol: str, days: int = 180
    ) -> Dict[str, List[Dict]]:
        """
        Get comprehensive data for ML training.

        Args:
            symbol: Trading symbol
            days: Number of days of historical data

        Returns:
            Dictionary with data for each timeframe
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        timeframes = ["1d", "1h", "15m"]
        training_data = {}

        # Fetch data for each timeframe in parallel
        tasks = []
        for tf in timeframes:
            task = self.get_ohlc_data(symbol, tf, start_date, end_date)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for tf, result in zip(timeframes, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to get {tf} data for {symbol}: {result}")
                training_data[tf] = []
            else:
                training_data[tf] = result

        return training_data

    async def archive_old_data(self, months_to_keep: int = 12):
        """
        Archive data older than specified months.
        This should be run during maintenance windows.

        Args:
            months_to_keep: Number of months to keep in main table
        """
        cutoff_date = datetime.utcnow() - timedelta(days=months_to_keep * 30)

        logger.info(f"Starting data archival for data before {cutoff_date}")

        # This would typically be done via SQL script
        # Provided here for reference
        archive_sql = f"""
        -- Move old data to archive
        INSERT INTO ohlc_data_archive
        SELECT * FROM ohlc_data
        WHERE timestamp < '{cutoff_date.isoformat()}'
        ON CONFLICT DO NOTHING;

        -- Delete from main table
        DELETE FROM ohlc_data
        WHERE timestamp < '{cutoff_date.isoformat()}';
        """

        logger.info("Archival SQL generated - execute via Supabase dashboard")
        return archive_sql

    def clear_cache(self):
        """Clear all cached data."""
        self.cache.clear()
        self.optimized_fetcher.clear_cache()
        logger.info("All caches cleared")
