"""
Supabase client for database operations.
Handles all database interactions for the crypto trading system.
"""

import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from loguru import logger
from supabase import create_client, Client

from src.config import get_settings


class SupabaseClient:
    """Handles all Supabase database operations."""
    
    def __init__(self):
        """Initialize Supabase client."""
        self.settings = get_settings()
        self.client: Client = create_client(
            self.settings.supabase_url,
            self.settings.supabase_key
        )
        logger.info("Supabase client initialized")
    
    def insert_price_data(self, data: List[Dict[str, Any]]) -> None:
        """Insert price data into the database, skipping duplicates."""
        if not data:
            return
            
        try:
            # Try batch insert first
            response = self.client.table('price_data').insert(data).execute()
            logger.debug(f"Inserted {len(data)} price records")
        except Exception as e:
            # If batch fails due to duplicates, insert one by one
            if 'duplicate key value' in str(e):
                successful = 0
                failed = 0
                
                for record in data:
                    try:
                        # Try to insert individual record
                        self.client.table('price_data').insert(record).execute()
                        successful += 1
                    except Exception as single_error:
                        if 'duplicate key value' in str(single_error):
                            # This is expected for duplicates, just skip
                            failed += 1
                        else:
                            # Log unexpected errors
                            logger.warning(f"Unexpected error inserting {record['symbol']}: {single_error}")
                            failed += 1
                
                if successful > 0:
                    logger.debug(f"Inserted {successful} new records, skipped {failed} duplicates")
                
                # Don't raise error for duplicates - this is normal operation
                if successful == 0 and failed == len(data):
                    logger.debug(f"All {failed} records were duplicates (this is normal)")
            else:
                # Re-raise if it's not a duplicate key error
                logger.error(f"Failed to insert price data: {e}")
                raise
    
    async def save_health_metric(
        self, 
        metric_name: str, 
        status: str, 
        value: float,
        details: Optional[Dict] = None
    ) -> None:
        """Save a health metric to the database."""
        try:
            data = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'metric_name': metric_name,
                'status': status,
                'value': value,
                'details': details or {},
                'alert_sent': False
            }
            
            response = self.client.table('health_metrics').insert(data).execute()
            
            # If critical, we might want to send an alert
            if status == 'critical':
                logger.warning(f"Critical health metric: {metric_name} = {value}")
                
        except Exception as e:
            logger.error(f"Failed to save health metric: {e}")
    
    def get_latest_prices(self, symbols: List[str], limit: int = 1) -> Dict[str, float]:
        """Get latest prices for given symbols."""
        try:
            prices = {}
            
            for symbol in symbols:
                response = (
                    self.client.table('price_data')
                    .select('price')
                    .eq('symbol', symbol)
                    .order('timestamp', desc=True)
                    .limit(limit)
                    .execute()
                )
                
                if response.data:
                    prices[symbol] = float(response.data[0]['price'])
            
            return prices
            
        except Exception as e:
            logger.error(f"Failed to get latest prices: {e}")
            return {}
    
    def get_price_history(
        self, 
        symbol: str, 
        start_time: datetime, 
        end_time: Optional[datetime] = None
    ) -> List[Dict]:
        """Get price history for a symbol within a time range."""
        try:
            query = (
                self.client.table('price_data')
                .select('timestamp, price, volume')
                .eq('symbol', symbol)
                .gte('timestamp', start_time.isoformat())
            )
            
            if end_time:
                query = query.lte('timestamp', end_time.isoformat())
            
            response = query.order('timestamp', desc=False).execute()
            return response.data
            
        except Exception as e:
            logger.error(f"Failed to get price history: {e}")
            return []
    
    def save_ml_features(self, features: List[Dict[str, Any]]) -> None:
        """Save calculated ML features to the database."""
        try:
            response = self.client.table('ml_features').insert(features).execute()
            logger.debug(f"Saved {len(features)} ML feature records")
        except Exception as e:
            # Handle duplicates like we do for price data
            if 'duplicate key value' in str(e):
                successful = 0
                failed = 0
                
                for record in features:
                    try:
                        self.client.table('ml_features').insert(record).execute()
                        successful += 1
                    except Exception as single_error:
                        if 'duplicate key value' in str(single_error):
                            failed += 1
                        else:
                            logger.warning(f"Unexpected error inserting feature for {record['symbol']}: {single_error}")
                            failed += 1
                
                if successful > 0:
                    logger.debug(f"Inserted {successful} new ML feature records, skipped {failed} duplicates")
                elif failed == len(features):
                    logger.debug(f"All {failed} ML feature records were duplicates (this is normal)")
            else:
                logger.error(f"Failed to save ML features: {e}")
                raise
            
    def insert_ml_features(self, data: list):
        """Insert ML features into database (alias for save_ml_features)"""
        self.save_ml_features(data)
        
    def get_price_data(self, symbol: str, start_time, end_time):
        """Get price data for a symbol within time range (alias for get_price_history)"""
        return self.get_price_history(symbol, start_time, end_time)
    
    def save_ml_prediction(
        self, 
        symbol: str, 
        prediction: str, 
        confidence: float,
        model_version: str = "1.0.0"
    ) -> int:
        """Save an ML prediction and return the prediction ID."""
        try:
            data = {
                'symbol': symbol,
                'prediction': prediction,
                'confidence': confidence,
                'model_version': model_version
            }
            
            response = self.client.table('ml_predictions').insert(data).execute()
            
            if response.data:
                prediction_id = response.data[0]['prediction_id']
                logger.info(
                    f"Saved prediction for {symbol}: {prediction} "
                    f"(confidence: {confidence:.2%}, id: {prediction_id})"
                )
                return prediction_id
            
            return -1
            
        except Exception as e:
            logger.error(f"Failed to save ML prediction: {e}")
            raise
    
    def get_recent_predictions(self, hours: int = 24) -> List[Dict]:
        """Get recent ML predictions."""
        try:
            cutoff_time = datetime.now(timezone.utc)
            cutoff_time = cutoff_time.replace(
                hour=cutoff_time.hour - hours
            )
            
            response = (
                self.client.table('ml_predictions')
                .select('*')
                .gte('timestamp', cutoff_time.isoformat())
                .order('timestamp', desc=True)
                .execute()
            )
            
            return response.data
            
        except Exception as e:
            logger.error(f"Failed to get recent predictions: {e}")
            return []
    
    def update_prediction_result(
        self, 
        prediction_id: int, 
        actual_move: float, 
        correct: bool
    ) -> None:
        """Update a prediction with its actual result."""
        try:
            data = {
                'actual_move': actual_move,
                'correct': correct
            }
            
            response = (
                self.client.table('ml_predictions')
                .update(data)
                .eq('prediction_id', prediction_id)
                .execute()
            )
            
            logger.debug(f"Updated prediction {prediction_id} with result")
            
        except Exception as e:
            logger.error(f"Failed to update prediction result: {e}")
    
    def get_system_config(self, key: str) -> Optional[Any]:
        """Get a system configuration value."""
        try:
            response = (
                self.client.table('system_config')
                .select('config_value')
                .eq('config_key', key)
                .execute()
            )
            
            if response.data:
                return response.data[0]['config_value']
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get system config: {e}")
            return None
    
    def update_system_config(self, key: str, value: Any) -> None:
        """Update a system configuration value."""
        try:
            data = {
                'config_value': value,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            response = (
                self.client.table('system_config')
                .update(data)
                .eq('config_key', key)
                .execute()
            )
            
            logger.info(f"Updated system config: {key}")
            
        except Exception as e:
            logger.error(f"Failed to update system config: {e}")
            raise
    
    def save_hummingbot_trade(self, trade_data: Dict) -> None:
        """Save a Hummingbot paper trade record."""
        try:
            response = self.client.table('hummingbot_trades').insert(trade_data).execute()
            logger.info(f"Saved Hummingbot trade: {trade_data['hummingbot_order_id']}")
        except Exception as e:
            logger.error(f"Failed to save Hummingbot trade: {e}")
            raise
    
    def get_ml_features(self, symbol: str, hours: int = 24) -> List[Dict]:
        """Get recent ML features for a symbol."""
        try:
            cutoff_time = datetime.now(timezone.utc)
            cutoff_time = cutoff_time.replace(
                hour=cutoff_time.hour - hours
            )
            
            response = (
                self.client.table('ml_features')
                .select('*')
                .eq('symbol', symbol)
                .gte('timestamp', cutoff_time.isoformat())
                .order('timestamp', desc=True)
                .execute()
            )
            
            return response.data
            
        except Exception as e:
            logger.error(f"Failed to get ML features: {e}")
            return []