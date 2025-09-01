"""
Supabase Data Provider for Freqtrade
Connects Freqtrade to existing Polygon data stored in Supabase
"""

import os
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from supabase import create_client, Client
import logging

logger = logging.getLogger(__name__)


class SupabaseDataProvider:
    """
    Custom data provider that fetches OHLC data from Supabase
    instead of downloading from exchange
    """

    def __init__(self):
        """Initialize Supabase client"""
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")

        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment")

        self.client: Client = create_client(self.supabase_url, self.supabase_key)

        # Cache for market cap data
        self._market_cap_cache: Dict[str, float] = {}
        self._cache_timestamp = None
        self._cache_ttl = 3600  # 1 hour cache

    def get_pair_dataframe(
        self, pair: str, timeframe: str = "1h", candle_count: int = 500
    ) -> pd.DataFrame:
        """
        Fetch OHLC data for a pair from Supabase

        Args:
            pair: Trading pair (e.g., "BTC/USDT")
            timeframe: Timeframe (e.g., '5m', '15m', '1h')
            candle_count: Number of candles to fetch

        Returns:
            DataFrame with OHLC data in Freqtrade format
        """

        # Convert pair format (BTC/USDT -> BTC)
        symbol = pair.split("/")[0]

        # Map timeframe to minutes
        timeframe_minutes = {
            '1m': 1,
            '5m': 5,
            '15m': 15,
            '30m': 30,
            '1h': 60,
            '4h': 240,
            '1d': 1440
        }
        
        minutes = timeframe_minutes.get(timeframe, 60)
        
        # Calculate date range
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=candle_count * minutes)

        try:
            # Determine which table to query based on timeframe
            # Assuming you have 1m data in ohlc_data table
            # We'll aggregate it for larger timeframes
            
            # For now, we'll use the 1h data from ohlc_data table
            # In production, you might want to create separate tables for different timeframes
            # or aggregate 1m data on the fly
            
            # Query OHLC data from Supabase
            response = (
                self.client.table("ohlc_data")
                .select("timestamp, open, high, low, close, volume")
                .eq("symbol", symbol)
                .gte("timestamp", start_time.isoformat())
                .lte("timestamp", end_time.isoformat())
                .order("timestamp")
                .execute()
            )

            if not response.data:
                logger.warning(f"No data found for {symbol}")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(response.data)

            # Convert timestamp to datetime
            df["date"] = pd.to_datetime(df["timestamp"])
            df.set_index("date", inplace=True)

            # Ensure numeric types
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            # Drop the original timestamp column
            df.drop("timestamp", axis=1, inplace=True)

            # Sort by date
            df.sort_index(inplace=True)

            # Add market cap data
            market_cap = self.get_market_cap(symbol)
            df["market_cap"] = market_cap

            logger.info(f"Fetched {len(df)} candles for {symbol}")

            return df

        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()

    def get_market_cap(self, symbol: str) -> float:
        """
        Get market cap for a symbol from cache or database

        Args:
            symbol: Cryptocurrency symbol (e.g., "BTC")

        Returns:
            Market cap in millions USD
        """

        # Check cache
        if (
            self._cache_timestamp
            and (datetime.now(timezone.utc) - self._cache_timestamp).seconds
            < self._cache_ttl
        ):
            if symbol in self._market_cap_cache:
                return self._market_cap_cache[symbol]

        try:
            # Fetch latest price data (market_data table doesn't exist, use price_data)
            # For now, we'll use default values since market cap isn't in price_data
            # In production, you might want to add market cap to your data pipeline
            response = None  # Temporarily disabled until we have market cap data

            if response.data:
                market_cap = (
                    response.data[0]["market_cap"] / 1_000_000
                )  # Convert to millions
                self._market_cap_cache[symbol] = market_cap
                self._cache_timestamp = datetime.now(timezone.utc)
                return market_cap

        except Exception as e:
            logger.error(f"Error fetching market cap for {symbol}: {e}")

        # Default market caps based on known tiers
        defaults = {
            "BTC": 1000000,
            "ETH": 400000,
            "SOL": 50000,
            "BNB": 80000,
            "XRP": 40000,
            "ADA": 15000,
            "AVAX": 10000,
            "DOGE": 12000,
            "DOT": 8000,
            "MATIC": 7000,
        }

        return defaults.get(symbol, 1000)  # Default to medium tier

    def get_available_pairs(self) -> list:
        """
        Get list of available trading pairs from database

        Returns:
            List of pairs in Freqtrade format (e.g., ["BTC/USDT", "ETH/USDT"])
        """

        try:
            # Get unique symbols from OHLC data
            response = self.client.table("ohlc_data").select("symbol").execute()

            if response.data:
                symbols = list(set(row["symbol"] for row in response.data))
                # Convert to Freqtrade pair format
                pairs = [f"{symbol}/USDT" for symbol in symbols]
                return sorted(pairs)

        except Exception as e:
            logger.error(f"Error fetching available pairs: {e}")

        return []

    def refresh_data(self, pair: str, timeframe: str = "1h") -> bool:
        """
        Check if new data is available for a pair

        Args:
            pair: Trading pair
            timeframe: Timeframe

        Returns:
            True if new data is available
        """

        symbol = pair.split("/")[0]

        try:
            # Check latest timestamp in database
            response = (
                self.client.table("ohlc_data")
                .select("timestamp")
                .eq("symbol", symbol)
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )

            if response.data:
                latest = pd.to_datetime(response.data[0]["timestamp"])
                now = datetime.now(timezone.utc)

                # New data if latest is within last hour
                return (now - latest).seconds < 3600

        except Exception as e:
            logger.error(f"Error checking data freshness for {symbol}: {e}")

        return False
