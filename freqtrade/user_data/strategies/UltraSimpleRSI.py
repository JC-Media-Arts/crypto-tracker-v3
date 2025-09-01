"""
Ultra Simple RSI Strategy - Guaranteed to trigger trades
This is the absolute simplest strategy to ensure trades execute
"""

from datetime import datetime
from typing import Optional
import logging
from pandas import DataFrame

from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade

logger = logging.getLogger(__name__)


class UltraSimpleRSI(IStrategy):
    """
    Ultra simple RSI strategy - buy on RSI < 40, sell on RSI > 60
    This WILL trigger trades!
    """
    
    INTERFACE_VERSION = 3
    can_short = False
    
    # Wide stoploss
    stoploss = -0.20  # 20% stop loss
    
    # Simple trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True
    
    # Take profits
    minimal_roi = {
        "0": 0.15,   # 15% after any time
        "10": 0.08,  # 8% after 10 min
        "30": 0.04,  # 4% after 30 min
        "60": 0.02   # 2% after 60 min
    }
    
    timeframe = '1m'
    startup_candle_count = 20
    
    def __init__(self, config: dict) -> None:
        super().__init__(config)
        logger.info("🎯 UltraSimpleRSI initialized - This WILL trade!")
        logger.info("  Buy when RSI < 40")
        logger.info("  Sell when RSI > 60")
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Just RSI, nothing else"""
        
        # Calculate RSI
        dataframe['rsi'] = self.calculate_rsi(dataframe['close'], 14)
        
        # Log for major pairs
        if len(dataframe) > 0 and metadata.get('pair') in ['BTC/USD', 'ETH/USD', 'SOL/USD']:
            latest = dataframe.iloc[-1]
            logger.info(f"📊 {metadata.get('pair')} - RSI: {latest['rsi']:.1f}, Close: {latest['close']:.4f}")
        
        return dataframe
    
    def calculate_rsi(self, series, period=14):
        """Calculate RSI"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Buy when RSI < 40 - very simple!"""
        
        dataframe.loc[
            (dataframe['rsi'] < 40) &  # Simple RSI oversold
            (dataframe['close'] > 0),   # Valid price
            'enter_long'
        ] = 1
        
        # Log entry signals
        if len(dataframe) > 0:
            latest = dataframe.iloc[-1]
            if latest.get('enter_long', 0) == 1:
                logger.info(f"🟢 BUY SIGNAL: {metadata.get('pair')} - RSI: {latest['rsi']:.1f}")
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Sell when RSI > 60"""
        
        dataframe.loc[
            (dataframe['rsi'] > 60),  # RSI overbought
            'exit_long'
        ] = 1
        
        return dataframe
    
    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, 
                   current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        """Quick exits for testing"""
        
        # Take quick profits
        if current_profit > 0.01:  # 1% profit
            return "quick_profit_1pct"
        
        # Time-based exit (max 2 hours)
        if (current_time - trade.open_date_utc).total_seconds() > 7200:
            return "time_limit_2h"
        
        return None
