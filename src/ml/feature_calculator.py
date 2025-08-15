"""
ML Feature Calculator
Calculates technical indicators and features for ML model
"""

import pandas as pd

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import ta
from loguru import logger
from src.data.supabase_client import SupabaseClient
from src.config import get_settings

settings = get_settings()


class FeatureCalculator:
    """Calculate ML features from price data"""

    def __init__(self):
        self.supabase = SupabaseClient()
        self.min_periods = 100  # Minimum data points needed for indicators

    def calculate_features_for_symbol(
        self, symbol: str, lookback_hours: int = 48
    ) -> Optional[pd.DataFrame]:
        """Calculate features for a single symbol"""
        try:
            # Get recent price data
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=lookback_hours)

            price_data = self.supabase.get_price_data(
                symbol=symbol, start_time=start_time, end_time=end_time
            )

            if not price_data or len(price_data) < self.min_periods:
                logger.warning(
                    f"Insufficient data for {symbol}: {len(price_data) if price_data else 0} records"
                )
                return None

            # Convert to DataFrame
            df = pd.DataFrame(price_data)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp")
            df.set_index("timestamp", inplace=True)

            # Calculate features
            features_df = self._calculate_technical_indicators(df)
            features_df["symbol"] = symbol

            return features_df

        except Exception as e:
            logger.error(f"Error calculating features for {symbol}: {e}")
            return None

    def _calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators"""
        features = pd.DataFrame(index=df.index)

        # Price changes
        features["price_change_5m"] = df["price"].pct_change(5).fillna(0) * 100
        features["price_change_15m"] = df["price"].pct_change(15).fillna(0) * 100
        features["price_change_1h"] = df["price"].pct_change(60).fillna(0) * 100
        features["price_change_4h"] = df["price"].pct_change(240).fillna(0) * 100

        # Volume ratio (current vs average)
        features["volume_ratio"] = df["volume"] / df["volume"].rolling(60).mean()

        # RSI
        features["rsi_14"] = ta.momentum.RSIIndicator(df["price"], window=14).rsi()
        features["rsi_30"] = ta.momentum.RSIIndicator(df["price"], window=30).rsi()

        # MACD
        macd = ta.trend.MACD(df["price"])
        features["macd"] = macd.macd()
        features["macd_signal"] = macd.macd_signal()
        features["macd_diff"] = macd.macd_diff()

        # Bollinger Bands
        bb = ta.volatility.BollingerBands(df["price"], window=20, window_dev=2)
        features["bb_high_band"] = bb.bollinger_hband()
        features["bb_low_band"] = bb.bollinger_lband()
        features["bb_middle_band"] = bb.bollinger_mavg()
        features["bb_width"] = (
            features["bb_high_band"] - features["bb_low_band"]
        ) / features["bb_middle_band"]
        features["bb_position"] = (df["price"] - features["bb_low_band"]) / (
            features["bb_high_band"] - features["bb_low_band"]
        )

        # Moving Averages
        features["sma_20"] = ta.trend.sma_indicator(df["price"], window=20)
        features["sma_50"] = ta.trend.sma_indicator(df["price"], window=50)
        features["ema_12"] = ta.trend.ema_indicator(df["price"], window=12)
        features["ema_26"] = ta.trend.ema_indicator(df["price"], window=26)

        # Distance from moving averages
        features["distance_from_sma20"] = (
            (df["price"] - features["sma_20"]) / features["sma_20"]
        ) * 100
        features["distance_from_sma50"] = (
            (df["price"] - features["sma_50"]) / features["sma_50"]
        ) * 100

        # Support/Resistance
        features["distance_from_support"] = self._calculate_support_resistance(
            df["price"], "support"
        )
        features["distance_from_resistance"] = self._calculate_support_resistance(
            df["price"], "resistance"
        )

        # Volatility
        features["volatility_1h"] = df["price"].pct_change().rolling(60).std() * 100
        features["volatility_4h"] = df["price"].pct_change().rolling(240).std() * 100

        # Volume indicators
        features["obv"] = ta.volume.OnBalanceVolumeIndicator(
            df["price"], df["volume"]
        ).on_balance_volume()
        features["volume_sma_ratio"] = df["volume"] / ta.trend.sma_indicator(
            df["volume"], window=20
        )

        # Momentum indicators
        features["roc_12"] = ta.momentum.ROCIndicator(df["price"], window=12).roc()
        features["stoch_k"] = ta.momentum.StochasticOscillator(
            df["price"], df["price"], df["price"]
        ).stoch()

        # Fill NaN values
        features = features.ffill().fillna(0)

        return features

    def _calculate_support_resistance(
        self, prices: pd.Series, level_type: str
    ) -> pd.Series:
        """Calculate distance from support/resistance levels"""
        window = 20

        if level_type == "support":
            levels = prices.rolling(window).min()
        else:  # resistance
            levels = prices.rolling(window).max()

        distance = ((prices - levels) / levels) * 100
        return distance.fillna(0)

    def save_features(self, features_df: pd.DataFrame) -> bool:
        """Save calculated features to database"""
        try:
            # Prepare data for insertion
            records = []
            for timestamp, row in features_df.iterrows():
                record = {
                    "timestamp": timestamp.isoformat(),
                    "symbol": row["symbol"],
                    "price_change_5m": float(row["price_change_5m"]),
                    "price_change_1h": float(row["price_change_1h"]),
                    "volume_ratio": float(row["volume_ratio"]),
                    "rsi_14": float(row["rsi_14"]),
                    "distance_from_support": float(row["distance_from_support"]),
                }
                records.append(record)

            # Insert into database
            if records:
                self.supabase.insert_ml_features(records)
                logger.debug(f"Processed {len(records)} feature records")
                return True

        except Exception as e:
            # Don't treat duplicate key errors as failures
            if "duplicate key value" not in str(e):
                logger.error(f"Error saving features: {e}")
                return False
            else:
                # Duplicates are handled in supabase client
                return True

    def update_all_symbols(self, symbols: List[str]) -> Dict[str, bool]:
        """Update features for all symbols"""
        results = {}

        for symbol in symbols:
            logger.info(f"Calculating features for {symbol}")
            features_df = self.calculate_features_for_symbol(symbol)

            if features_df is not None and not features_df.empty:
                # Only save the most recent features
                recent_features = features_df.tail(10)  # Last 10 time periods
                success = self.save_features(recent_features)
                results[symbol] = success
            else:
                results[symbol] = False

        return results
