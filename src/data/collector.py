"""
Data collector module for real-time crypto price data from Polygon.io.
Handles WebSocket connections and data persistence to Supabase.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from decimal import Decimal
from loguru import logger
from polygon import WebSocketClient
from polygon.websocket.models import EquityAgg

from src.config import Settings
from src.data.supabase_client import SupabaseClient


class DataCollector:
    """Collects real-time crypto data from Polygon.io WebSocket."""
    
    # Supported crypto symbols (100 coins as defined in master plan)
    TIER_1_COINS = [
        'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'AVAX', 'DOGE', 'DOT', 'POL',
        'LINK', 'TON', 'SHIB', 'TRX', 'UNI', 'ATOM', 'BCH', 'APT', 'NEAR', 'ICP'
    ]
    
    TIER_2_COINS = [
        'ARB', 'OP', 'AAVE', 'CRV', 'MKR', 'LDO', 'SUSHI', 'COMP', 'SNX', 'BAL',
        'INJ', 'SEI', 'PENDLE', 'BLUR', 'ENS', 'GRT', 'RENDER', 'FET', 'RPL', 'SAND'
    ]
    
    TIER_3_COINS = [
        'PEPE', 'WIF', 'BONK', 'FLOKI', 'MEME', 'POPCAT', 'MEW', 'TURBO', 'NEIRO', 'PNUT',
        'GOAT', 'ACT', 'TRUMP', 'FARTCOIN', 'MOG', 'PONKE', 'TREMP', 'BRETT', 'GIGA', 'HIPPO'
    ]
    
    TIER_4_COINS = [
        'FIL', 'RUNE', 'IMX', 'FLOW', 'MANA', 'AXS', 'CHZ', 'GALA', 'LRC', 'OCEAN',
        'QNT', 'ALGO', 'XLM', 'XMR', 'ZEC', 'DASH', 'HBAR', 'VET', 'THETA', 'EOS',
        'KSM', 'STX', 'KAS', 'TIA', 'JTO', 'JUP', 'PYTH', 'DYM', 'STRK', 'ALT',
        'PORTAL', 'BEAM', 'BLUR', 'MASK', 'API3', 'ANKR', 'CTSI', 'YFI', 'AUDIO', 'ENJ'
    ]
    
    def __init__(self, settings: Settings):
        """Initialize the data collector."""
        self.settings = settings
        self.ws_client: Optional[WebSocketClient] = None
        self.db_client: Optional[SupabaseClient] = None
        self.running = False
        self.price_buffer: List[Dict] = []
        self.buffer_size = 100  # Batch insert size
        self.last_prices: Dict[str, float] = {}
        
        # Get all supported coins
        self.supported_coins = (
            self.TIER_1_COINS + self.TIER_2_COINS + 
            self.TIER_3_COINS + self.TIER_4_COINS
        )
        
    async def initialize(self):
        """Initialize the data collector."""
        logger.info("Initializing data collector...")
        
        try:
            # Initialize Supabase client
            self.db_client = SupabaseClient(self.settings)
            await self.db_client.initialize()
            
            # Initialize Polygon WebSocket client
            self.ws_client = WebSocketClient(
                api_key=self.settings.polygon_api_key,
                feed='delayed',  # Use delayed feed for free tier
                market='crypto'
            )
            
            # Subscribe to crypto pairs
            await self._subscribe_to_symbols()
            
            logger.success("Data collector initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize data collector: {e}")
            raise
    
    async def _subscribe_to_symbols(self):
        """Subscribe to WebSocket feeds for all supported symbols."""
        # Convert crypto symbols to Polygon format (e.g., BTC -> X:BTCUSD)
        subscriptions = []
        for symbol in self.supported_coins:
            # Subscribe to USD pairs
            subscriptions.append(f"XA.{symbol}-USD")  # Aggregate bars
            subscriptions.append(f"XT.{symbol}-USD")  # Trades
        
        logger.info(f"Subscribing to {len(subscriptions)} crypto pairs")
        
        # Note: Actual subscription will happen when WebSocket connects
        self.subscriptions = subscriptions
    
    async def start(self):
        """Start collecting data."""
        logger.info("Starting data collection...")
        self.running = True
        
        # Start WebSocket connection
        asyncio.create_task(self._run_websocket())
        
        # Start buffer flush task
        asyncio.create_task(self._flush_buffer_periodically())
        
        # Start data health check
        asyncio.create_task(self._check_data_health())
        
        logger.success("Data collection started")
    
    async def _run_websocket(self):
        """Run the WebSocket connection."""
        while self.running:
            try:
                logger.info("Connecting to Polygon WebSocket...")
                
                # Define message handler
                async def handle_msg(messages):
                    for message in messages:
                        await self._process_message(message)
                
                # Connect and subscribe
                self.ws_client.subscribe(*self.subscriptions)
                await self.ws_client.connect(handle_msg)
                
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await asyncio.sleep(5)  # Reconnect after 5 seconds
    
    async def _process_message(self, message: Any):
        """Process incoming WebSocket message."""
        try:
            # Parse message based on type
            if hasattr(message, 'event_type'):
                if message.event_type == 'XA':  # Aggregate bar
                    await self._process_aggregate(message)
                elif message.event_type == 'XT':  # Trade
                    await self._process_trade(message)
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    async def _process_aggregate(self, agg: Any):
        """Process aggregate bar data."""
        try:
            # Extract symbol from pair (e.g., X:BTCUSD -> BTC)
            symbol = agg.pair.replace('X:', '').replace('USD', '')
            
            # Create price record
            price_record = {
                'timestamp': datetime.fromtimestamp(agg.start_timestamp / 1000, tz=timezone.utc).isoformat(),
                'symbol': symbol,
                'price': float(agg.close),
                'volume': float(agg.volume) if hasattr(agg, 'volume') else 0
            }
            
            # Update last price
            self.last_prices[symbol] = float(agg.close)
            
            # Add to buffer
            self.price_buffer.append(price_record)
            
            # Flush if buffer is full
            if len(self.price_buffer) >= self.buffer_size:
                await self._flush_buffer()
            
        except Exception as e:
            logger.error(f"Error processing aggregate: {e}")
    
    async def _process_trade(self, trade: Any):
        """Process trade data."""
        # For now, we'll focus on aggregates
        # Trades can be used for more granular analysis in Phase 2
        pass
    
    async def _flush_buffer(self):
        """Flush price buffer to database."""
        if not self.price_buffer:
            return
        
        try:
            # Batch insert to Supabase
            await self.db_client.insert_price_data(self.price_buffer)
            
            logger.debug(f"Flushed {len(self.price_buffer)} price records to database")
            self.price_buffer.clear()
            
        except Exception as e:
            logger.error(f"Failed to flush buffer: {e}")
    
    async def _flush_buffer_periodically(self):
        """Periodically flush the buffer."""
        while self.running:
            await asyncio.sleep(10)  # Flush every 10 seconds
            await self._flush_buffer()
    
    async def _check_data_health(self):
        """Check data flow health."""
        while self.running:
            await asyncio.sleep(60)  # Check every minute
            
            # Check if we're receiving data
            if not self.last_prices:
                logger.warning("No data received in the last minute")
            else:
                active_symbols = len(self.last_prices)
                logger.info(f"Receiving data for {active_symbols} symbols")
    
    async def stop(self):
        """Stop data collection."""
        logger.info("Stopping data collection...")
        self.running = False
        
        # Flush remaining buffer
        await self._flush_buffer()
        
        # Close WebSocket connection
        if self.ws_client:
            await self.ws_client.close()
        
        # Close database connection
        if self.db_client:
            await self.db_client.close()
        
        logger.info("Data collection stopped")
    
    def get_last_price(self, symbol: str) -> Optional[float]:
        """Get the last known price for a symbol."""
        return self.last_prices.get(symbol)
    
    def get_active_symbols(self) -> List[str]:
        """Get list of symbols with recent data."""
        return list(self.last_prices.keys())
