"""
SWING Strategy - Hyperoptable Version
For finding optimal parameters through backtesting
DO NOT USE FOR PRODUCTION - Use SwingStrategyV1.py instead
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


class SwingStrategyV1_HO(IStrategy):
    """
    SWING Strategy - Hyperoptable Version
    
    This version is designed for hyperparameter optimization to find
    the best initial values for the SWING strategy parameters.
    
    After optimization, apply the discovered values to your Admin config
    and use the production SwingStrategyV1.py for actual trading.
    """

    # Strategy interface version
    INTERFACE_VERSION = 3

    # Disable ROI - we'll optimize stoploss and trailing stop instead
    minimal_roi = {"0": 100}

    # Hyperoptable stoploss
    stoploss = -0.12  # Will be optimized

    # Trailing stop parameters (will be optimized)
    trailing_stop = True
    trailing_stop_positive = 0.025
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # Optimal timeframe for the strategy
    timeframe = "1h"

    # Run "populate_indicators()" for all tickers in whitelist
    process_only_new_candles = False

    # -------------------------------------------------------------------------
    # HYPEROPTABLE PARAMETERS - These will be optimized
    # -------------------------------------------------------------------------
    
    # Buy space parameters (entry conditions)
    buy_breakout_threshold = DecimalParameter(1.005, 1.03, decimals=3, default=1.01, space='buy', optimize=True)
    buy_breakout_confirmation = DecimalParameter(0.005, 0.03, decimals=3, default=0.015, space='buy', optimize=True)
    buy_volume_surge = DecimalParameter(1.1, 2.0, decimals=1, default=1.3, space='buy', optimize=True)
    buy_rsi_min = IntParameter(35, 55, default=45, space='buy', optimize=True)
    buy_rsi_max = IntParameter(65, 85, default=75, space='buy', optimize=True)
    buy_momentum_score_min = IntParameter(30, 60, default=40, space='buy', optimize=True)
    buy_trend_strength_min = DecimalParameter(0.01, 0.05, decimals=3, default=0.02, space='buy', optimize=True)
    buy_volatility_max = DecimalParameter(0.05, 0.15, decimals=2, default=0.10, space='buy', optimize=True)
    
    # Sell space parameters (exit conditions)
    sell_take_profit = DecimalParameter(0.04, 0.20, decimals=2, default=0.08, space='sell', optimize=True)
    sell_rsi_high = IntParameter(75, 90, default=80, space='sell', optimize=True)
    sell_volume_ratio_low = DecimalParameter(0.3, 0.7, decimals=1, default=0.5, space='sell', optimize=True)
    sell_trend_reversal = DecimalParameter(-0.02, -0.005, decimals=3, default=-0.01, space='sell', optimize=True)
    
    # Protection/Stoploss parameters - no buy_ prefix for stoploss
    stoploss_value = DecimalParameter(-0.12, -0.03, decimals=2, default=-0.06, space='stoploss', optimize=True)
    trailing_stop_positive_value = DecimalParameter(0.01, 0.05, decimals=3, default=0.025, space='trailing', optimize=True)
    trailing_stop_positive_offset_value = DecimalParameter(0.02, 0.08, decimals=3, default=0.04, space='trailing', optimize=True)
    
    # Breakout detection parameters
    buy_breakout_lookback = IntParameter(10, 30, default=20, space='buy', optimize=True)
    
    # Technical indicator parameters (fixed for consistency)
    rsi_period = 14
    macd_fast = 12
    macd_slow = 26
    macd_signal = 9
    sma_fast = 20
    sma_slow = 50

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Calculate all technical indicators needed for the strategy
        """
        
        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=int(self.rsi_period))
        
        # MACD
        macd = ta.MACD(
            dataframe,
            fastperiod=self.macd_fast,
            slowperiod=self.macd_slow,
            signalperiod=self.macd_signal
        )
        dataframe["macd"] = macd["macd"]
        dataframe["macd_signal"] = macd["macdsignal"]
        dataframe["macd_hist"] = macd["macdhist"]
        
        # Moving Averages
        dataframe["sma_fast"] = ta.SMA(dataframe, timeperiod=self.sma_fast)
        dataframe["sma_slow"] = ta.SMA(dataframe, timeperiod=self.sma_slow)
        
        # Trend strength
        dataframe["trend_strength"] = (
            (dataframe["sma_fast"] - dataframe["sma_slow"]) / dataframe["sma_slow"]
        )
        
        # Volume indicators
        dataframe["volume_sma"] = dataframe["volume"].rolling(window=20).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_sma"]
        dataframe["volume_usd"] = dataframe["volume"] * dataframe["close"]
        
        # Resistance levels (for breakout detection) - using hyperopt parameter
        # Note: We'll use the default value during indicator calculation
        # The actual value will be used in populate_entry_trend
        dataframe["resistance_20"] = dataframe["high"].rolling(window=20).max()
        
        # Support levels
        dataframe["support_20"] = dataframe["low"].rolling(window=20).min()
        
        # Price momentum
        dataframe["price_change_1h"] = dataframe["close"].pct_change(periods=1)
        dataframe["price_change_4h"] = dataframe["close"].pct_change(periods=4)
        dataframe["price_change_24h"] = dataframe["close"].pct_change(periods=24)
        
        # Volatility
        dataframe["volatility"] = dataframe["close"].pct_change().rolling(window=24).std()
        
        # Bollinger Bands (for volatility context)
        bollinger = ta.BBANDS(
            dataframe,
            timeperiod=20,
            nbdevup=2.0,
            nbdevdn=2.0,
        )
        dataframe["bb_upper"] = bollinger["upperband"]
        dataframe["bb_middle"] = bollinger["middleband"]
        dataframe["bb_lower"] = bollinger["lowerband"]
        dataframe["bb_width"] = (dataframe["bb_upper"] - dataframe["bb_lower"]) / dataframe["bb_middle"]
        
        # Momentum score (simplified for hyperopt)
        dataframe["momentum_score"] = 0
        
        # Add points for positive indicators
        dataframe.loc[dataframe["rsi"] > 50, "momentum_score"] += 10
        dataframe.loc[dataframe["rsi"] > 60, "momentum_score"] += 10
        dataframe.loc[dataframe["macd"] > dataframe["macd_signal"], "momentum_score"] += 15
        dataframe.loc[dataframe["macd_hist"] > 0, "momentum_score"] += 10
        dataframe.loc[dataframe["sma_fast"] > dataframe["sma_slow"], "momentum_score"] += 15
        dataframe.loc[dataframe["trend_strength"] > 0.02, "momentum_score"] += 10
        dataframe.loc[dataframe["volume_ratio"] > 1.2, "momentum_score"] += 10
        dataframe.loc[dataframe["price_change_4h"] > 0, "momentum_score"] += 10
        dataframe.loc[dataframe["price_change_24h"] > 0.03, "momentum_score"] += 10
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate buy signals for the SWING strategy
        Uses hyperoptable parameters
        """
        
        # Calculate dynamic resistance based on hyperopt parameter
        dataframe[f"resistance_dynamic"] = dataframe["high"].rolling(
            window=int(self.buy_breakout_lookback.value)
        ).max()
        dataframe["breakout"] = dataframe["close"] / dataframe["resistance_dynamic"]
        
        # SWING entry conditions using hyperoptable parameters
        conditions = []
        
        # 1. Breakout detected (price above resistance)
        conditions.append(dataframe["breakout"] >= self.buy_breakout_threshold.value)
        
        # 2. Volume surge confirmation
        conditions.append(dataframe["volume_ratio"] >= self.buy_volume_surge.value)
        
        # 3. RSI in bullish range
        conditions.append(dataframe["rsi"] >= self.buy_rsi_min.value)
        conditions.append(dataframe["rsi"] <= self.buy_rsi_max.value)
        
        # 4. Momentum score above threshold
        conditions.append(dataframe["momentum_score"] >= self.buy_momentum_score_min.value)
        
        # 5. Positive trend (using hyperopt parameter)
        conditions.append(dataframe["trend_strength"] >= self.buy_trend_strength_min.value)
        
        # 6. MACD bullish
        conditions.append(
            (dataframe["macd"] > dataframe["macd_signal"]) |
            (dataframe["macd_hist"] > 0)
        )
        
        # 7. Minimum USD volume (fixed for liquidity)
        conditions.append(dataframe["volume_usd"] >= 100000)
        
        # 8. Not too volatile
        conditions.append(dataframe["volatility"] < self.buy_volatility_max.value)
        
        # 9. Price momentum positive (confirming breakout)
        conditions.append(dataframe["price_change_4h"] > self.buy_breakout_confirmation.value)
        
        # Combine all conditions
        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                ['enter_long', 'enter_tag']
            ] = (1, 'swing_breakout_hyperopt')
        
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate sell signals for the SWING strategy
        Uses hyperoptable parameters
        """
        
        # Exit conditions using hyperoptable parameters
        conditions = []
        
        # 1. Take profit reached (simplified)
        conditions.append(
            dataframe["price_change_24h"] >= self.sell_take_profit.value
        )
        
        # 2. RSI overbought
        conditions.append(dataframe["rsi"] >= self.sell_rsi_high.value)
        
        # 3. MACD bearish crossover
        conditions.append(
            (dataframe["macd"] < dataframe["macd_signal"]) &
            (dataframe["macd_hist"] < 0)
        )
        
        # 4. Trend reversal
        conditions.append(
            (dataframe["sma_fast"] < dataframe["sma_slow"]) &
            (dataframe["trend_strength"] < self.sell_trend_reversal.value)
        )
        
        # 5. Volume drying up
        conditions.append(
            (dataframe["volume_ratio"] < self.sell_volume_ratio_low.value) &
            (dataframe["price_change_1h"] < 0)
        )
        
        # Combine exit conditions (any of them triggers exit)
        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x | y, conditions),
                ['exit_long', 'exit_tag']
            ] = (1, 'swing_exit_hyperopt')
        
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
        Protection parameters for risk management
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
                "method": "CooldownPeriod",
                "stop_duration_candles": 2
            }
        ]

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str,
                 side: str, **kwargs) -> float:
        """
        No leverage for SWING strategy (spot trading only)
        """
        return 1.0
