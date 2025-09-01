"""
CHANNEL Strategy - Hyperoptable Version
For finding optimal parameters through backtesting
DO NOT USE FOR PRODUCTION - Use ChannelStrategyV1.py instead
"""

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from functools import reduce

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, CategoricalParameter
from freqtrade.persistence import Trade


class ChannelStrategyV1_HO(IStrategy):
    """
    CHANNEL Strategy - Hyperoptable Version
    
    This version is designed for hyperparameter optimization to find
    the best initial values for the CHANNEL strategy parameters.
    
    After optimization, apply the discovered values to your Admin config
    and use the production ChannelStrategyV1.py for actual trading.
    """

    # Strategy interface version
    INTERFACE_VERSION = 3

    # Disable ROI - we'll optimize stoploss and trailing stop instead
    minimal_roi = {"0": 100}

    # Hyperoptable stoploss
    stoploss = -0.10  # Will be optimized

    # Trailing stop parameters (will be optimized)
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    # Optimal timeframe for the strategy
    timeframe = "5m"  # 5 minutes for channel strategy

    # Run "populate_indicators()" for all tickers in whitelist
    process_only_new_candles = False

    # -------------------------------------------------------------------------
    # HYPEROPTABLE PARAMETERS - These will be optimized
    # -------------------------------------------------------------------------
    
    # Buy space parameters (entry conditions)
    buy_channel_entry_threshold = DecimalParameter(0.05, 0.25, decimals=2, default=0.15, space='buy', optimize=True)
    buy_rsi_min = IntParameter(25, 45, default=35, space='buy', optimize=True)
    buy_rsi_max = IntParameter(55, 75, default=65, space='buy', optimize=True)
    buy_volume_ratio_min = DecimalParameter(0.5, 1.5, decimals=1, default=0.8, space='buy', optimize=True)
    buy_volatility_max = DecimalParameter(0.02, 0.08, decimals=3, default=0.05, space='buy', optimize=True)
    buy_price_drop_min = DecimalParameter(-10.0, -1.0, decimals=1, default=-3.0, space='buy', optimize=True)
    
    # Bollinger Band parameters
    buy_bb_period = IntParameter(15, 30, default=20, space='buy', optimize=True)
    buy_bb_std = DecimalParameter(1.5, 2.5, decimals=1, default=2.0, space='buy', optimize=True)
    
    # Sell space parameters (exit conditions)
    sell_channel_exit_threshold = DecimalParameter(0.75, 0.95, decimals=2, default=0.85, space='sell', optimize=True)
    sell_take_profit = DecimalParameter(0.02, 0.10, decimals=2, default=0.05, space='sell', optimize=True)
    sell_rsi_high = IntParameter(70, 85, default=75, space='sell', optimize=True)
    
    # Protection/Stoploss parameters - no buy_ prefix for stoploss
    stoploss_value = DecimalParameter(-0.10, -0.02, decimals=2, default=-0.05, space='stoploss', optimize=True)
    trailing_stop_positive_value = DecimalParameter(0.005, 0.03, decimals=3, default=0.01, space='trailing', optimize=True)
    trailing_stop_positive_offset_value = DecimalParameter(0.01, 0.05, decimals=3, default=0.02, space='trailing', optimize=True)
    
    # Technical indicator parameters (some are hyperoptable)
    rsi_period = 14  # Fixed

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Calculate all technical indicators needed for the strategy
        """
        
        # Bollinger Bands with hyperoptable parameters
        # Note: We'll calculate multiple BB sets and choose in entry/exit
        for period in [15, 20, 25, 30]:
            for std in [1.5, 2.0, 2.5]:
                bollinger = ta.BBANDS(
                    dataframe,
                    timeperiod=int(period),
                    nbdevup=float(std),
                    nbdevdn=float(std),
                )
                dataframe[f"bb_upper_{period}_{std}"] = bollinger["upperband"]
                dataframe[f"bb_middle_{period}_{std}"] = bollinger["middleband"]
                dataframe[f"bb_lower_{period}_{std}"] = bollinger["lowerband"]
        
        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=int(self.rsi_period))
        
        # Volume indicators
        dataframe["volume_sma"] = dataframe["volume"].rolling(window=20).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_sma"]
        
        # Price drop from recent high
        dataframe["high_24h"] = dataframe["high"].rolling(window=288).max()  # 24h in 5m candles
        dataframe["price_drop_pct"] = (
            (dataframe["close"] - dataframe["high_24h"]) / dataframe["high_24h"] * 100
        )
        
        # Volatility (ATR based)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["volatility"] = dataframe["atr"] / dataframe["close"]
        
        # Price momentum
        dataframe["price_change_1h"] = dataframe["close"].pct_change(periods=12)  # 1h in 5m candles
        dataframe["price_change_4h"] = dataframe["close"].pct_change(periods=48)  # 4h in 5m candles
        
        # Moving averages for trend
        dataframe["sma_20"] = ta.SMA(dataframe, timeperiod=20)
        dataframe["sma_50"] = ta.SMA(dataframe, timeperiod=50)
        dataframe["trend"] = dataframe["sma_20"] > dataframe["sma_50"]
        
        # VWAP (Volume Weighted Average Price)
        dataframe["vwap"] = (dataframe["volume"] * (dataframe["high"] + dataframe["low"] + dataframe["close"]) / 3).cumsum() / dataframe["volume"].cumsum()
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate buy signals for the CHANNEL strategy
        Uses hyperoptable parameters
        """
        
        # Select the BB columns based on hyperopt parameters
        bb_period = int(self.buy_bb_period.value)
        bb_std = float(self.buy_bb_std.value)
        
        # Round to nearest available values
        bb_period = min([15, 20, 25, 30], key=lambda x: abs(x - bb_period))
        bb_std = min([1.5, 2.0, 2.5], key=lambda x: abs(x - bb_std))
        
        # Use the selected BB columns
        bb_upper_col = f"bb_upper_{bb_period}_{bb_std}"
        bb_lower_col = f"bb_lower_{bb_period}_{bb_std}"
        
        # Calculate channel position with selected BB
        dataframe["channel_position"] = (
            (dataframe["close"] - dataframe[bb_lower_col]) /
            (dataframe[bb_upper_col] - dataframe[bb_lower_col])
        ).fillna(0.5)
        
        # CHANNEL entry conditions using hyperoptable parameters
        conditions = []
        
        # 1. Price in lower portion of channel
        conditions.append(dataframe["channel_position"] <= self.buy_channel_entry_threshold.value)
        
        # 2. RSI in acceptable range (not oversold, not overbought)
        conditions.append(dataframe["rsi"] >= self.buy_rsi_min.value)
        conditions.append(dataframe["rsi"] <= self.buy_rsi_max.value)
        
        # 3. Volume confirmation
        conditions.append(dataframe["volume_ratio"] >= self.buy_volume_ratio_min.value)
        
        # 4. Not too volatile
        conditions.append(dataframe["volatility"] <= self.buy_volatility_max.value)
        
        # 5. Some price drop (but not extreme)
        conditions.append(dataframe["price_drop_pct"] <= self.buy_price_drop_min.value)
        conditions.append(dataframe["price_drop_pct"] >= -15)  # Not a crash
        
        # 6. Price above VWAP (value entry)
        conditions.append(dataframe["close"] <= dataframe["vwap"] * 1.01)
        
        # Combine all conditions
        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                ['enter_long', 'enter_tag']
            ] = (1, 'channel_entry_hyperopt')
        
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate sell signals for the CHANNEL strategy
        Uses hyperoptable parameters
        """
        
        # Select the BB columns based on hyperopt parameters (same as entry)
        bb_period = int(self.buy_bb_period.value)
        bb_std = float(self.buy_bb_std.value)
        
        # Round to nearest available values
        bb_period = min([15, 20, 25, 30], key=lambda x: abs(x - bb_period))
        bb_std = min([1.5, 2.0, 2.5], key=lambda x: abs(x - bb_std))
        
        # Use the selected BB columns
        bb_upper_col = f"bb_upper_{bb_period}_{bb_std}"
        bb_lower_col = f"bb_lower_{bb_period}_{bb_std}"
        
        # Recalculate channel position for exit
        dataframe["channel_position_exit"] = (
            (dataframe["close"] - dataframe[bb_lower_col]) /
            (dataframe[bb_upper_col] - dataframe[bb_lower_col])
        ).fillna(0.5)
        
        # Exit conditions using hyperoptable parameters
        conditions = []
        
        # 1. Price in upper portion of channel
        conditions.append(dataframe["channel_position_exit"] >= self.sell_channel_exit_threshold.value)
        
        # 2. Take profit reached (simplified)
        conditions.append(
            dataframe["price_change_1h"] >= self.sell_take_profit.value
        )
        
        # 3. RSI overbought
        conditions.append(dataframe["rsi"] >= self.sell_rsi_high.value)
        
        # 4. Price above upper BB (overextended)
        conditions.append(dataframe["close"] > dataframe[bb_upper_col])
        
        # Combine exit conditions (any of them triggers exit)
        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x | y, conditions),
                ['exit_long', 'exit_tag']
            ] = (1, 'channel_exit_hyperopt')
        
        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool, **kwargs) -> Optional[float]:
        """
        Custom stoploss logic using hyperoptable parameters
        """
        
        # Implement trailing stop loss with hyperopt parameters
        if current_profit >= self.trailing_stop_positive_offset_value.value:
            # Trailing stop is active
            return -(self.trailing_stop_positive_value.value)
        
        # Regular stop loss
        return self.stoploss_value.value

    @property
    def protections(self):
        """
        Protection parameters for risk management
        """
        return [
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 48,  # More candles for 5m timeframe
                "trade_limit": 4,
                "stop_duration_candles": 24,
                "only_per_pair": False
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 200,
                "trade_limit": 20,
                "stop_duration_candles": 12,
                "max_allowed_drawdown": 0.2
            },
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 5
            }
        ]

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str,
                 side: str, **kwargs) -> float:
        """
        No leverage for CHANNEL strategy (spot trading only)
        """
        return 1.0
