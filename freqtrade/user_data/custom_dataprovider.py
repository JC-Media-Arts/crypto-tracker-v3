"""
Custom DataProvider for Freqtrade that uses Supabase as the data source
This replaces the need to download data from exchanges
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
import pandas as pd
from freqtrade.data.dataprovider import DataProvider
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))
from data.supabase_dataprovider import SupabaseDataProvider

logger = logging.getLogger(__name__)


class CustomDataProvider(DataProvider):
    """
    Custom DataProvider that fetches data from Supabase instead of exchange
    """

    def __init__(self, config: dict, exchange=None, pairlists=None, rpc=None):
        """
        Initialize the custom data provider
        """
        super().__init__(config, exchange, pairlists, rpc)
        
        # Initialize Supabase data provider
        try:
            self.supabase_provider = SupabaseDataProvider()
            logger.info("✅ Supabase data provider initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Supabase provider: {e}")
            self.supabase_provider = None
            
        # Cache for dataframes
        self._klines: Dict[str, pd.DataFrame] = {}
        self._last_refresh: Dict[str, datetime] = {}
        
    def ohlcv(
        self,
        pair: str,
        timeframe: str = None,
        copy: bool = True,
        candle_type: str = ''
    ) -> pd.DataFrame:
        """
        Get OHLC data for a pair
        
        Args:
            pair: Pair to get data for
            timeframe: Timeframe to get data for
            copy: Return a copy of the dataframe
            candle_type: Candle type (ignored, we only use spot)
            
        Returns:
            DataFrame with OHLC data
        """
        if not self.supabase_provider:
            logger.warning(f"Supabase provider not available, returning empty dataframe for {pair}")
            return pd.DataFrame()
            
        # Use configured timeframe if not specified
        if timeframe is None:
            timeframe = self._config.get('timeframe', '1h')
            
        # Create cache key
        cache_key = f"{pair}_{timeframe}"
        
        # Check if we need to refresh (every 5 minutes)
        now = datetime.now(timezone.utc)
        last_refresh = self._last_refresh.get(cache_key)
        
        if last_refresh is None or (now - last_refresh).seconds > 300:
            # Fetch fresh data from Supabase
            logger.debug(f"Fetching fresh data for {pair} {timeframe}")
            
            # Map timeframe to hours for calculation
            timeframe_hours = {
                '1m': 1/60,
                '5m': 5/60,
                '15m': 15/60,
                '30m': 30/60,
                '1h': 1,
                '4h': 4,
                '1d': 24
            }
            
            hours_per_candle = timeframe_hours.get(timeframe, 1)
            
            # Calculate candle count (get 500 candles by default)
            candle_count = int(500 / hours_per_candle) if timeframe == '1h' else 500
            
            # Fetch data from Supabase
            df = self.supabase_provider.get_pair_dataframe(
                pair=pair,
                timeframe=timeframe,
                candle_count=candle_count
            )
            
            if not df.empty:
                # Ensure the dataframe has the required columns for Freqtrade
                required_columns = ['open', 'high', 'low', 'close', 'volume']
                if all(col in df.columns for col in required_columns):
                    # Store in cache
                    self._klines[cache_key] = df
                    self._last_refresh[cache_key] = now
                    logger.info(f"✅ Loaded {len(df)} candles for {pair} {timeframe}")
                else:
                    logger.error(f"❌ Missing required columns for {pair}: {df.columns.tolist()}")
                    return pd.DataFrame()
            else:
                logger.warning(f"⚠️ No data available for {pair} {timeframe}")
                return pd.DataFrame()
        
        # Return cached data
        df = self._klines.get(cache_key, pd.DataFrame())
        
        if copy and not df.empty:
            return df.copy()
        return df
        
    def historic_ohlcv(
        self,
        pair: str,
        timeframe: str = None,
        candle_type: str = ''
    ) -> pd.DataFrame:
        """
        Get historic OHLC data (just returns the same as ohlcv for our case)
        """
        return self.ohlcv(pair, timeframe, copy=True, candle_type=candle_type)
        
    def get_pair_dataframe(
        self,
        pair: str,
        timeframe: str = None,
        candle_type: str = ''
    ) -> pd.DataFrame:
        """
        Get dataframe for a pair (alias for ohlcv)
        """
        return self.ohlcv(pair, timeframe, copy=True, candle_type=candle_type)
        
    def refresh(self,
                pairlist: List[str],
                helping_pairs: List[str] = None) -> None:
        """
        Refresh data for all pairs
        """
        if not self.supabase_provider:
            logger.warning("Supabase provider not available, cannot refresh data")
            return
            
        all_pairs = pairlist + (helping_pairs if helping_pairs else [])
        
        for pair in all_pairs:
            # Force refresh by clearing cache timestamp
            for timeframe in ['1m', '5m', '15m', '30m', '1h', '4h', '1d']:
                cache_key = f"{pair}_{timeframe}"
                if cache_key in self._last_refresh:
                    del self._last_refresh[cache_key]
                    
        logger.info(f"🔄 Marked {len(all_pairs)} pairs for refresh")
        
    def available_pairs(self) -> List[str]:
        """
        Get list of available pairs from Supabase
        """
        if not self.supabase_provider:
            return []
            
        return self.supabase_provider.get_available_pairs()
