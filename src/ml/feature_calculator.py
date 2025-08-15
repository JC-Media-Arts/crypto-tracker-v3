"""
Feature calculator for ML predictions.
Calculates technical indicators and features from price data.
"""

from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from loguru import logger
import ta

from src.data.supabase_client import SupabaseClient


class FeatureCalculator:
    """Calculates features for ML predictions."""
    
    def __init__(self, db_client: SupabaseClient):
        """Initialize feature calculator."""
        self.db_client = db_client
        
    async def calculate_features(self, symbol: str) -> Optional[Dict]:
        """Calculate all features for a symbol."""
        try:
            # Get recent price data
            price_data = await self.db_client.get_recent_prices(symbol, hours=24)
            
            if len(price_data) < 20:  # Need minimum data for indicators
                logger.warning(f"Insufficient data for {symbol}: {len(price_data)} records")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(price_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            df['price'] = df['price'].astype(float)
            df['volume'] = df['volume'].astype(float)
            
            # Calculate features
            features = {}
            
            # Price returns
            features['returns_5m'] = self._calculate_returns(df, minutes=5)
            features['returns_1h'] = self._calculate_returns(df, minutes=60)
            
            # RSI
            features['rsi_14'] = self._calculate_rsi(df, period=14)
            
            # Distance from SMA
            features['distance_from_sma20'] = self._calculate_sma_distance(df, period=20)
            
            # Volume ratio
            features['volume_ratio'] = self._calculate_volume_ratio(df)
            
            # Support/Resistance distance
            features['support_distance'] = self._calculate_support_distance(df)
            
            return features
            
        except Exception as e:
            logger.error(f"Failed to calculate features for {symbol}: {e}")
            return None
    
    def _calculate_returns(self, df: pd.DataFrame, minutes: int) -> float:
        """Calculate price returns over specified minutes."""
        try:
            current_price = df.iloc[-1]['price']
            
            # Find price from X minutes ago
            target_time = df.iloc[-1]['timestamp'] - timedelta(minutes=minutes)
            past_data = df[df['timestamp'] <= target_time]
            
            if past_data.empty:
                return 0.0
            
            past_price = past_data.iloc[-1]['price']
            
            # Calculate return
            if past_price > 0:
                return (current_price - past_price) / past_price * 100
            return 0.0
            
        except Exception:
            return 0.0
    
    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate RSI (Relative Strength Index)."""
        try:
            rsi = ta.momentum.RSIIndicator(close=df['price'], window=period)
            rsi_values = rsi.rsi()
            
            if not rsi_values.empty:
                return float(rsi_values.iloc[-1])
            return 50.0  # Neutral RSI
            
        except Exception:
            return 50.0
    
    def _calculate_sma_distance(self, df: pd.DataFrame, period: int = 20) -> float:
        """Calculate distance from Simple Moving Average."""
        try:
            if len(df) < period:
                return 0.0
            
            sma = df['price'].rolling(window=period).mean()
            current_price = df.iloc[-1]['price']
            current_sma = sma.iloc[-1]
            
            if current_sma > 0:
                return (current_price - current_sma) / current_sma * 100
            return 0.0
            
        except Exception:
            return 0.0
    
    def _calculate_volume_ratio(self, df: pd.DataFrame) -> float:
        """Calculate current volume vs average volume ratio."""
        try:
            if len(df) < 20:
                return 1.0
            
            current_volume = df.iloc[-1]['volume']
            avg_volume = df['volume'].rolling(window=20).mean().iloc[-1]
            
            if avg_volume > 0:
                return current_volume / avg_volume
            return 1.0
            
        except Exception:
            return 1.0
    
    def _calculate_support_distance(self, df: pd.DataFrame) -> float:
        """Calculate distance from nearest support level."""
        try:
            current_price = df.iloc[-1]['price']
            
            # Find recent lows as support levels
            recent_lows = df['price'].rolling(window=5).min()
            support_levels = recent_lows[recent_lows < current_price * 0.98]  # At least 2% below
            
            if not support_levels.empty:
                nearest_support = support_levels.iloc[-1]
                return (current_price - nearest_support) / nearest_support * 100
            
            # If no support found, use 5% below current price
            return 5.0
            
        except Exception:
            return 5.0
    
    async def calculate_and_store_features(self, symbols: List[str]):
        """Calculate and store features for multiple symbols."""
        for symbol in symbols:
            try:
                features = await self.calculate_features(symbol)
                if features:
                    # Add metadata
                    features['symbol'] = symbol
                    features['timestamp'] = datetime.utcnow().isoformat()
                    
                    # Store in database
                    await self.db_client.insert_ml_features([features])
                    logger.debug(f"Stored features for {symbol}")
                    
            except Exception as e:
                logger.error(f"Failed to store features for {symbol}: {e}")
