"""
DCA Strategy - Hyperoptable Version
For finding optimal parameters through backtesting
DO NOT USE FOR PRODUCTION - Use DCAStrategyV1.py instead
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


class DCAStrategyV1_HO(IStrategy):
    """
    DCA Strategy - Hyperoptable Version
    
    This version is designed for hyperparameter optimization to find
    the best initial values for the DCA strategy parameters.
    
    After optimization, apply the discovered values to your Admin config
    and use the production DCAStrategyV1.py for actual trading.
    """

    # Strategy interface version
    INTERFACE_VERSION = 3

    # Disable ROI - we'll optimize stoploss and trailing stop instead
    minimal_roi = {"0": 100}

    # Hyperoptable stoploss
    stoploss = -0.15  # Will be optimized

    # Trailing stop parameters (will be optimized)
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.035
    trailing_only_offset_is_reached = True

    # Optimal timeframe for the strategy
    timeframe = "1h"

    # Run "populate_indicators()" for all tickers in whitelist
    process_only_new_candles = False

    # -------------------------------------------------------------------------
    # HYPEROPTABLE PARAMETERS - These will be optimized
    # -------------------------------------------------------------------------
    
    # Buy space parameters (entry conditions)
    buy_drop_threshold = DecimalParameter(-6.0, -1.0, decimals=2, default=-2.25, space='buy', optimize=True)
    buy_volume_requirement = DecimalParameter(0.5, 1.5, decimals=2, default=0.85, space='buy', optimize=True)
    buy_rsi_min = IntParameter(20, 40, default=25, space='buy', optimize=True)
    buy_rsi_max = IntParameter(55, 75, default=65, space='buy', optimize=True)
    buy_volume_threshold = IntParameter(50000, 200000, default=100000, space='buy', optimize=True)
    buy_volatility_max = DecimalParameter(0.05, 0.15, decimals=2, default=0.10, space='buy', optimize=True)
    
    # Sell space parameters (exit conditions)
    sell_take_profit = DecimalParameter(0.03, 0.15, decimals=2, default=0.07, space='sell', optimize=True)
    sell_rsi_high = IntParameter(70, 85, default=75, space='sell', optimize=True)
    
    # Protection/Stoploss parameters - no buy_ prefix for stoploss
    # Note: Negative values for stoploss
    stoploss_value = DecimalParameter(-0.15, -0.03, decimals=2, default=-0.08, space='stoploss', optimize=True)
    trailing_stop_positive_value = DecimalParameter(0.005, 0.05, decimals=3, default=0.02, space='trailing', optimize=True)
    trailing_stop_positive_offset_value = DecimalParameter(0.01, 0.06, decimals=3, default=0.035, space='trailing', optimize=True)
    
    # Grid parameters (for DCA specific behavior)
    buy_grid_levels = IntParameter(3, 7, default=5, space='buy', optimize=True)
    buy_grid_spacing = DecimalParameter(0.01, 0.04, decimals=3, default=0.02, space='buy', optimize=True)

    # Technical indicator parameters (fixed for consistency)
    rsi_period = 14
    bb_period = 20
    bb_std = 2.0
    high_lookback = 24  # 24 hours for recent high

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Calculate all technical indicators needed for the strategy
        """
        
        # Price drop from recent high
        dataframe["high_24h"] = dataframe["high"].rolling(window=self.high_lookback).max()
        dataframe["price_drop_pct"] = (
            (dataframe["close"] - dataframe["high_24h"]) / dataframe["high_24h"] * 100
        )
        
        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=int(self.rsi_period))
        
        # Bollinger Bands
        bollinger = ta.BBANDS(
            dataframe,
            timeperiod=int(self.bb_period),
            nbdevup=float(self.bb_std),
            nbdevdn=float(self.bb_std),
        )
        dataframe["bb_upper"] = bollinger["upperband"]
        dataframe["bb_middle"] = bollinger["middleband"]
        dataframe["bb_lower"] = bollinger["lowerband"]
        
        # Volume indicators
        dataframe["volume_sma"] = dataframe["volume"].rolling(window=20).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_sma"]
        dataframe["volume_usd"] = dataframe["volume"] * dataframe["close"]
        
        # Price momentum
        dataframe["price_change_1h"] = dataframe["close"].pct_change(periods=1)
        dataframe["price_change_4h"] = dataframe["close"].pct_change(periods=4)
        dataframe["price_change_24h"] = dataframe["close"].pct_change(periods=24)
        
        # Support levels (for grid entries)
        dataframe["support_1"] = dataframe["low"].rolling(window=24).min()
        dataframe["support_2"] = dataframe["low"].rolling(window=48).min()
        dataframe["support_3"] = dataframe["low"].rolling(window=72).min()
        
        # Volatility
        dataframe["volatility"] = dataframe["close"].pct_change().rolling(window=24).std()
        
        # Market regime indicator (simplified)
        dataframe["sma_50"] = dataframe["close"].rolling(window=50).mean()
        dataframe["sma_200"] = dataframe["close"].rolling(window=200).mean()
        dataframe["bull_market"] = dataframe["sma_50"] > dataframe["sma_200"]
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate buy signals for the DCA strategy
        Uses hyperoptable parameters
        """
        
        # DCA entry conditions using hyperoptable parameters
        conditions = []
        
        # 1. Price has dropped from recent high
        conditions.append(dataframe["price_drop_pct"] <= self.buy_drop_threshold.value)
        
        # 2. Volume requirement (at least X% of average)
        conditions.append(dataframe["volume_ratio"] >= self.buy_volume_requirement.value)
        
        # 3. Minimum USD volume
        conditions.append(dataframe["volume_usd"] >= self.buy_volume_threshold.value)
        
        # 4. RSI in acceptable range
        conditions.append(dataframe["rsi"] >= self.buy_rsi_min.value)
        conditions.append(dataframe["rsi"] <= self.buy_rsi_max.value)
        
        # 5. Price above lower Bollinger Band (not in extreme sell-off)
        conditions.append(dataframe["close"] > dataframe["bb_lower"] * 0.98)
        
        # 6. Not too volatile
        conditions.append(dataframe["volatility"] < self.buy_volatility_max.value)
        
        # Combine all conditions
        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                ['enter_long', 'enter_tag']
            ] = (1, 'dca_drop_hyperopt')
        
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate sell signals for the DCA strategy
        Uses hyperoptable parameters
        """
        
        # Exit conditions using hyperoptable parameters
        conditions = []
        
        # 1. Take profit reached (simplified)
        # Note: In real trading, Freqtrade handles this better with ROI
        conditions.append(
            dataframe["close"].pct_change(periods=24) >= self.sell_take_profit.value
        )
        
        # 2. RSI overbought
        conditions.append(dataframe["rsi"] >= self.sell_rsi_high.value)
        
        # 3. Price above upper Bollinger Band
        conditions.append(dataframe["close"] > dataframe["bb_upper"])
        
        # Combine exit conditions (any of them triggers exit)
        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x | y, conditions),
                ['exit_long', 'exit_tag']
            ] = (1, 'dca_exit_hyperopt')
        
        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool, **kwargs) -> Optional[float]:
        """
        Custom stoploss logic using hyperoptable parameters
        """
        
        # Use hyperoptable stoploss
        return self.stoploss_value.value

    @property
    def protections(self):
        """
        Protection parameters that can be optimized
        """
        return [
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 24,
                "trade_limit": 4,
                "stop_duration_candles": 12,
                "only_per_pair": False
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 48,
                "trade_limit": 20,
                "stop_duration_candles": 4,
                "max_allowed_drawdown": 0.2
            },
            {
                "method": "LowProfitPairs",
                "lookback_period_candles": 360,
                "trade_limit": 2,
                "stop_duration_candles": 60,
                "required_profit": 0.01
            }
        ]

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str,
                 side: str, **kwargs) -> float:
        """
        No leverage for DCA strategy (spot trading only)
        """
        return 1.0
