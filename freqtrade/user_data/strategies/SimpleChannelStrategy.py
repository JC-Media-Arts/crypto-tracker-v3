"""
Simple Channel Strategy - Minimal viable trading system
Designed to actually trigger trades with loosened thresholds
"""

from datetime import datetime, timezone
from typing import Dict, Optional, Any
import logging
from pandas import DataFrame
import pandas as pd
import numpy as np

from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade

logger = logging.getLogger(__name__)


class SimpleChannelStrategy(IStrategy):
    """
    Simplified Channel Strategy with loosened thresholds
    Goal: Get trades executing, then tighten later
    """
    
    # Strategy configuration
    INTERFACE_VERSION = 3
    can_short = False
    
    # Minimal stoploss to prevent huge losses
    stoploss = -0.15  # 15% stop loss
    
    # Simple trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True
    
    # ROI table - take profits at various levels
    minimal_roi = {
        "0": 0.10,   # 10% after any time
        "30": 0.05,  # 5% after 30 min
        "60": 0.03,  # 3% after 60 min
        "120": 0.02  # 2% after 120 min
    }
    
    # Timeframe
    timeframe = '1m'
    
    # Run populate_indicators for all pairs
    process_only_new_candles = False
    startup_candle_count = 30
    
    # Simple thresholds - VERY loose to ensure trades happen
    # Channel position thresholds
    channel_entry_threshold = 0.70  # Buy when price is in lower 70% of channel (was 0.35)
    channel_exit_threshold = 0.30   # Sell when price is in upper 30% of channel (was 0.65+)
    
    # RSI thresholds - very wide range
    rsi_min = 20  # Avoid extreme oversold
    rsi_max = 80  # Avoid extreme overbought
    
    # No volume requirements for now
    use_volume_filter = False
    
    def __init__(self, config: dict) -> None:
        super().__init__(config)
        logger.info("🚀 SimpleChannelStrategy initialized with loosened thresholds")
        logger.info(f"  Entry threshold: {self.channel_entry_threshold} (lower {self.channel_entry_threshold*100}% of channel)")
        logger.info(f"  Exit threshold: {self.channel_exit_threshold} (upper {(1-self.channel_exit_threshold)*100}% of channel)")
        
        # Initialize scan logger if available
        try:
            from scan_logger import ScanLogger
            self.scan_logger = ScanLogger()
            self.has_scan_logger = True
            logger.info("✅ Scan logger initialized")
        except Exception as e:
            logger.warning(f"Scan logger not available: {e}")
            self.scan_logger = None
            self.has_scan_logger = False
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Add minimal technical indicators
        """
        
        # Bollinger Bands (20 period, 2 std)
        dataframe['bb_upper'] = dataframe['close'].rolling(window=20).mean() + (dataframe['close'].rolling(window=20).std() * 2)
        dataframe['bb_lower'] = dataframe['close'].rolling(window=20).mean() - (dataframe['close'].rolling(window=20).std() * 2)
        dataframe['bb_middle'] = dataframe['close'].rolling(window=20).mean()
        
        # Channel position (0 = at lower band, 1 = at upper band)
        bb_width = dataframe['bb_upper'] - dataframe['bb_lower']
        dataframe['channel_position'] = (dataframe['close'] - dataframe['bb_lower']) / bb_width
        # Handle division by zero
        dataframe['channel_position'] = dataframe['channel_position'].fillna(0.5)
        dataframe['channel_position'] = dataframe['channel_position'].clip(0, 1)
        
        # Simple RSI
        dataframe['rsi'] = self.calculate_rsi(dataframe['close'], 14)
        
        # Log current indicators for debugging
        if len(dataframe) > 0:
            latest = dataframe.iloc[-1]
            if metadata.get('pair') and self._should_log(metadata.get('pair')):
                logger.info(f"📊 {metadata.get('pair')} - Channel: {latest['channel_position']:.3f}, RSI: {latest['rsi']:.1f}, Close: {latest['close']:.4f}")
        
        return dataframe
    
    def calculate_rsi(self, series, period=14):
        """Calculate RSI"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _should_log(self, pair: str) -> bool:
        """Only log every 10th pair to reduce noise"""
        common_pairs = ['BTC/USD', 'ETH/USD', 'SOL/USD', 'DOGE/USD', 'PEPE/USD']
        return pair in common_pairs
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Simple entry conditions - VERY loose to ensure trades happen
        """
        
        # Calculate entry conditions
        entry_conditions = (
            # Price in lower portion of channel (loosened from 0.35 to 0.70)
            (dataframe['channel_position'] <= self.channel_entry_threshold) &
            
            # RSI not extremely oversold (avoid catching falling knives)
            (dataframe['rsi'] > self.rsi_min) &
            
            # RSI not extremely overbought
            (dataframe['rsi'] < self.rsi_max) &
            
            # Ensure we have valid Bollinger Bands
            (dataframe['bb_upper'] > dataframe['bb_lower']) &
            
            # Ensure we have a valid close price
            (dataframe['close'] > 0)
            
            # NO VOLUME REQUIREMENT - removed to ensure trades happen
        )
        
        # Set entry signal
        dataframe.loc[entry_conditions, 'enter_long'] = 1
        
        # Log scan decision (FIXED: check conditions, not the result)
        if self.has_scan_logger and len(dataframe) > 0:
            latest_idx = -1
            latest_row = dataframe.iloc[latest_idx]
            
            # Check if THIS specific row meets entry conditions
            row_meets_conditions = (
                latest_row['channel_position'] <= self.channel_entry_threshold and
                latest_row['rsi'] > self.rsi_min and
                latest_row['rsi'] < self.rsi_max and
                latest_row['bb_upper'] > latest_row['bb_lower'] and
                latest_row['close'] > 0
            )
            
            try:
                self.scan_logger.log_entry_analysis(
                    pair=metadata.get('pair', 'UNKNOWN'),
                    dataframe_row=latest_row.to_dict(),
                    entry_signal=row_meets_conditions,  # Use actual condition check
                    strategy='SIMPLE_CHANNEL'
                )
                
                # Log details for debugging
                if metadata.get('pair') and self._should_log(metadata.get('pair')):
                    logger.info(f"🎯 {metadata.get('pair')} - Entry signal: {row_meets_conditions}, Channel: {latest_row['channel_position']:.3f}, RSI: {latest_row['rsi']:.1f}")
                    if not row_meets_conditions:
                        reasons = []
                        if latest_row['channel_position'] > self.channel_entry_threshold:
                            reasons.append(f"Channel too high: {latest_row['channel_position']:.3f} > {self.channel_entry_threshold}")
                        if latest_row['rsi'] <= self.rsi_min:
                            reasons.append(f"RSI too low: {latest_row['rsi']:.1f} <= {self.rsi_min}")
                        if latest_row['rsi'] >= self.rsi_max:
                            reasons.append(f"RSI too high: {latest_row['rsi']:.1f} >= {self.rsi_max}")
                        if reasons:
                            logger.info(f"  ❌ Reasons: {', '.join(reasons)}")
                            
            except Exception as e:
                logger.error(f"Failed to log scan: {e}")
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Simple exit conditions
        """
        
        exit_conditions = (
            # Price in upper portion of channel
            (dataframe['channel_position'] >= self.channel_exit_threshold) |
            
            # RSI overbought
            (dataframe['rsi'] > 75)
        )
        
        dataframe.loc[exit_conditions, 'exit_long'] = 1
        
        return dataframe
    
    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, 
                   current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        """
        Custom exit logic - simplified
        """
        
        # Quick profit taking
        if current_profit > 0.02:  # 2% profit
            return "quick_profit"
        
        # Cut losses if dropping fast
        if current_profit < -0.05:  # 5% loss
            return "stop_loss"
        
        # Time-based exit (hold max 4 hours)
        if (current_time - trade.open_date_utc).total_seconds() > 14400:  # 4 hours
            if current_profit > 0:
                return "time_exit_profit"
            elif current_profit < -0.02:
                return "time_exit_loss"
        
        return None
