"""
Hybrid data fetcher that uses materialized views for recent data.
This provides massive performance improvements by avoiding the unindexed main table.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from loguru import logger

from src.config.settings import get_settings
from src.data.supabase_client import SupabaseClient


class HybridDataFetcher:
    """
    Intelligently routes queries between:
    - ohlc_today: Last 24 hours (fastest)
    - ohlc_recent: Last 7 days (fast)
    - ohlc_data: Historical data (slow, use sparingly)
    """

    def __init__(self):
        """Initialize the hybrid fetcher."""
        self.settings = get_settings()
        self.db = SupabaseClient()

        # Thresholds for table selection
        self.today_hours = 24
        self.recent_days = 7

        # Cache for latest prices
        self.price_cache = {}
        self.cache_ttl = 5  # seconds

    def _select_table(self, start_date: datetime) -> str:
        """
        Select the optimal table based on date range.

        Returns:
            Table name to query
        """
        # TEMPORARY FIX: Always use ohlc_data until we fix the materialized views
        # The ohlc_today and ohlc_recent views are stale/broken
        return "ohlc_data"

        # Original logic (disabled for now):
        # now = datetime.utcnow()
        # time_diff = now - start_date
        # if time_diff.total_seconds() <= (self.today_hours * 3600):
        #     return "ohlc_today"
        # elif time_diff.days <= self.recent_days:
        #     return "ohlc_recent"
        # else:
        #     return "ohlc_data"

    async def get_latest_price(self, symbol: str, timeframe: str = "1m") -> Optional[Dict]:
        """
        Get the most recent price - uses ohlc_today for maximum speed.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe to query

        Returns:
            Latest OHLC record or None
        """
        cache_key = f"{symbol}_{timeframe}_latest"

        # Check cache
        if cache_key in self.price_cache:
            cached_time, cached_data = self.price_cache[cache_key]
            if (datetime.utcnow() - cached_time).total_seconds() < self.cache_ttl:
                return cached_data

        try:
            # Always use ohlc_today for latest prices
            result = (
                self.db.client.table("ohlc_today")
                .select("*")
                .eq("symbol", symbol)
                .eq("timeframe", timeframe)
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )

            if result.data:
                # Update cache
                self.price_cache[cache_key] = (datetime.utcnow(), result.data[0])
                return result.data[0]

            # Fallback to ohlc_recent if not in today
            result = (
                self.db.client.table("ohlc_recent")
                .select("*")
                .eq("symbol", symbol)
                .eq("timeframe", timeframe)
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )

            if result.data:
                self.price_cache[cache_key] = (datetime.utcnow(), result.data[0])
                return result.data[0]

            return None

        except Exception as e:
            logger.error(f"Error fetching latest price for {symbol}: {e}")
            return None

    async def get_recent_data(self, symbol: str, hours: int = 24, timeframe: str = "15m") -> List[Dict]:
        """
        Get recent data optimized for trading signals.

        Args:
            symbol: Trading symbol
            hours: Number of hours to look back
            timeframe: Timeframe to query

        Returns:
            List of OHLC records
        """
        try:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            table = self._select_table(cutoff)

            logger.debug(f"Fetching {symbol} from {table} (last {hours} hours)")

            result = (
                self.db.client.table(table)
                .select("*")
                .eq("symbol", symbol)
                .eq("timeframe", timeframe)
                .gte("timestamp", cutoff.isoformat())
                .order("timestamp", desc=False)
                .execute()
            )

            return result.data

        except Exception as e:
            logger.error(f"Error fetching recent data for {symbol}: {e}")
            return []

    async def get_ml_features_data(self, symbol: str) -> Dict[str, List]:
        """
        Get data for ML feature calculation - uses ohlc_recent.

        Args:
            symbol: Trading symbol

        Returns:
            Dictionary with arrays for each feature
        """
        try:
            # Get last 7 days of hourly data from ohlc_recent
            result_1h = (
                self.db.client.table("ohlc_recent")
                .select("timestamp, open, high, low, close, volume")
                .eq("symbol", symbol)
                .eq("timeframe", "1h")
                .order("timestamp", desc=True)
                .limit(168)
                .execute()
            )

            # Get last 24 hours of 15m data from ohlc_today
            result_15m = (
                self.db.client.table("ohlc_today")
                .select("timestamp, open, high, low, close, volume")
                .eq("symbol", symbol)
                .eq("timeframe", "15m")
                .order("timestamp", desc=True)
                .limit(96)
                .execute()
            )

            return {
                "1h": result_1h.data,
                "15m": result_15m.data,
                "has_data": bool(result_1h.data or result_15m.data),
            }

        except Exception as e:
            logger.error(f"Error fetching ML data for {symbol}: {e}")
            return {"1h": [], "15m": [], "has_data": False}

    async def get_trading_signals_batch(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Get trading signal data for multiple symbols efficiently.

        Args:
            symbols: List of trading symbols

        Returns:
            Dictionary with signal data for each symbol
        """
        signals = {}

        for symbol in symbols:
            try:
                # Get last 4 hours from ohlc_today (most efficient)
                result = (
                    self.db.client.table("ohlc_today")
                    .select("timestamp, close, high, low, volume")
                    .eq("symbol", symbol)
                    .eq("timeframe", "15m")
                    .order("timestamp", desc=True)
                    .limit(16)
                    .execute()
                )

                if result.data and len(result.data) >= 2:
                    current = result.data[0]
                    previous = result.data[1]

                    # Calculate basic signals
                    price_change = ((current["close"] - previous["close"]) / previous["close"]) * 100

                    # Find 24h high/low
                    high_24h = max(r["high"] for r in result.data)
                    low_24h = min(r["low"] for r in result.data)

                    signals[symbol] = {
                        "price": current["close"],
                        "change_pct": round(price_change, 2),
                        "volume": current["volume"],
                        "high_24h": high_24h,
                        "low_24h": low_24h,
                        "timestamp": current["timestamp"],
                        "has_data": True,
                    }
                else:
                    signals[symbol] = {"has_data": False}

            except Exception as e:
                logger.error(f"Error getting signals for {symbol}: {e}")
                signals[symbol] = {"has_data": False, "error": str(e)}

        return signals

    async def get_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str = "1d",
    ) -> List[Dict]:
        """
        Get historical data - may be slow for old dates.

        Args:
            symbol: Trading symbol
            start_date: Start of date range
            end_date: End of date range
            timeframe: Timeframe to query

        Returns:
            List of OHLC records
        """
        # Determine which tables we need to query
        tables_to_query = []

        now = datetime.utcnow()

        # Check if we need ohlc_today
        if end_date > now - timedelta(hours=self.today_hours):
            tables_to_query.append("ohlc_today")

        # Check if we need ohlc_recent
        if end_date > now - timedelta(days=self.recent_days) and start_date < now - timedelta(hours=self.today_hours):
            tables_to_query.append("ohlc_recent")

        # Check if we need historical data
        if start_date < now - timedelta(days=self.recent_days):
            tables_to_query.append("ohlc_data")
            logger.warning(f"Querying historical data for {symbol} - may be slow")

        all_data = []

        for table in tables_to_query:
            try:
                result = (
                    self.db.client.table(table)
                    .select("*")
                    .eq("symbol", symbol)
                    .eq("timeframe", timeframe)
                    .gte("timestamp", start_date.isoformat())
                    .lte("timestamp", end_date.isoformat())
                    .order("timestamp")
                    .execute()
                )

                all_data.extend(result.data)

            except Exception as e:
                logger.error(f"Error querying {table} for {symbol}: {e}")

        # Remove duplicates and sort
        seen = set()
        unique_data = []
        for record in all_data:
            key = (record["symbol"], record["timestamp"], record["timeframe"])
            if key not in seen:
                seen.add(key)
                unique_data.append(record)

        unique_data.sort(key=lambda x: x["timestamp"])

        return unique_data

    def clear_cache(self):
        """Clear the price cache."""
        self.price_cache.clear()
        logger.info("Cache cleared")
