"""
Supabase client for database operations.
Handles all interactions with the PostgreSQL database.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from loguru import logger
from supabase import create_client, Client

from src.config import Settings


class SupabaseClient:
    """Client for Supabase database operations."""
    
    def __init__(self, settings: Settings):
        """Initialize Supabase client."""
        self.settings = settings
        self.client: Optional[Client] = None
        
    async def initialize(self):
        """Initialize database connection."""
        try:
            self.client = create_client(
                self.settings.supabase_url,
                self.settings.supabase_key
            )
            logger.info("Connected to Supabase")
        except Exception as e:
            logger.error(f"Failed to connect to Supabase: {e}")
            raise
    
    async def insert_price_data(self, records: List[Dict]):
        """Insert price data records."""
        try:
            response = self.client.table('price_data').insert(records).execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to insert price data: {e}")
            raise
    
    async def get_recent_prices(self, symbol: str, hours: int = 24) -> List[Dict]:
        """Get recent price data for a symbol."""
        try:
            start_time = datetime.utcnow() - timedelta(hours=hours)
            
            response = self.client.table('price_data') \
                .select('*') \
                .eq('symbol', symbol) \
                .gte('timestamp', start_time.isoformat()) \
                .order('timestamp', desc=True) \
                .execute()
            
            return response.data
        except Exception as e:
            logger.error(f"Failed to get recent prices: {e}")
            return []
    
    async def insert_ml_features(self, features: List[Dict]):
        """Insert ML feature records."""
        try:
            response = self.client.table('ml_features').insert(features).execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to insert ML features: {e}")
            raise
    
    async def get_ml_features(self, symbol: str, limit: int = 1000) -> List[Dict]:
        """Get ML features for training."""
        try:
            response = self.client.table('ml_features') \
                .select('*') \
                .eq('symbol', symbol) \
                .order('timestamp', desc=True) \
                .limit(limit) \
                .execute()
            
            return response.data
        except Exception as e:
            logger.error(f"Failed to get ML features: {e}")
            return []
    
    async def insert_prediction(self, prediction: Dict):
        """Insert ML prediction."""
        try:
            response = self.client.table('ml_predictions').insert(prediction).execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to insert prediction: {e}")
            raise
    
    async def update_prediction_result(self, prediction_id: int, actual_move: float, correct: bool):
        """Update prediction with actual result."""
        try:
            response = self.client.table('ml_predictions') \
                .update({
                    'actual_move': actual_move,
                    'correct': correct
                }) \
                .eq('prediction_id', prediction_id) \
                .execute()
            
            return response.data
        except Exception as e:
            logger.error(f"Failed to update prediction: {e}")
            raise
    
    async def insert_paper_trade(self, trade: Dict):
        """Insert paper trade record."""
        try:
            response = self.client.table('paper_trades').insert(trade).execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to insert paper trade: {e}")
            raise
    
    async def update_paper_trade(self, trade_id: int, updates: Dict):
        """Update paper trade record."""
        try:
            response = self.client.table('paper_trades') \
                .update(updates) \
                .eq('trade_id', trade_id) \
                .execute()
            
            return response.data
        except Exception as e:
            logger.error(f"Failed to update paper trade: {e}")
            raise
    
    async def get_open_trades(self) -> List[Dict]:
        """Get all open paper trades."""
        try:
            response = self.client.table('paper_trades') \
                .select('*') \
                .is_('exit_time', 'null') \
                .execute()
            
            return response.data
        except Exception as e:
            logger.error(f"Failed to get open trades: {e}")
            return []
    
    async def get_daily_performance(self, date: str) -> Optional[Dict]:
        """Get daily performance metrics."""
        try:
            response = self.client.table('daily_performance') \
                .select('*') \
                .eq('date', date) \
                .single() \
                .execute()
            
            return response.data
        except Exception as e:
            logger.debug(f"No daily performance for {date}")
            return None
    
    async def upsert_daily_performance(self, performance: Dict):
        """Insert or update daily performance."""
        try:
            response = self.client.table('daily_performance').upsert(performance).execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to upsert daily performance: {e}")
            raise
    
    async def insert_health_metric(self, metric: Dict):
        """Insert health metric."""
        try:
            response = self.client.table('health_metrics').insert(metric).execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to insert health metric: {e}")
            raise
    
    async def close(self):
        """Close database connection."""
        # Supabase client doesn't need explicit closing
        logger.info("Supabase client closed")
