"""
SWING Strategy for Freqtrade
Momentum and breakout strategy for multi-day trades
Ported from crypto-tracker-v3 Swing detector
"""

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import sys
import os

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from freqtrade.strategy import IStrategy, informative
from freqtrade.strategy.interface import IStrategy
from freqtrade.persistence import Trade
from loguru import logger

# Import our custom modules
from config_bridge import ConfigBridge
from scan_logger import get_scan_logger
from data.supabase_dataprovider import SupabaseDataProvider


class SwingStrategyV1(IStrategy):
    """
    SWING Strategy - Momentum and breakout trading
    
    This strategy:
    - Enters on breakouts with volume confirmation
    - Uses momentum indicators (RSI, MACD) for confirmation
    - Targets multi-day swing trades
    - Uses market cap tiers for position sizing and risk management
    """

    # Strategy interface version
    INTERFACE_VERSION = 3

    # Define minimal ROI - we'll use dynamic exits instead
    minimal_roi = {"0": 100}  # Effectively disabled, we use custom exit logic

    # Stop loss - will be overridden by custom logic based on tiers
    stoploss = -0.12  # Default 12% stop loss (for memecoins)
    
    # Enable trailing stop loss
    trailing_stop = True
    trailing_stop_positive = 0.025  # Start trailing at 2.5% profit
    trailing_stop_positive_offset = 0.04  # Trail 4% behind peak
    trailing_only_offset_is_reached = True  # Only trail after offset is reached

    # Optimal timeframe for the strategy
    timeframe = "1h"  # 1 hour for swing detection

    # Run "populate_indicators()" for all tickers in whitelist
    process_only_new_candles = False

    def __init__(self, config: dict) -> None:
        """
        Initialize the strategy with configuration
        """
        super().__init__(config)

        # Initialize configuration bridge
        self.config_bridge = ConfigBridge()

        # Initialize scan logger
        try:
            self.scan_logger = get_scan_logger()
            logger.info("✅ Scan logger initialized in SwingStrategyV1")
        except Exception as e:
            logger.error(f"❌ Failed to initialize scan logger: {e}")
            # Create dummy logger
            class DummyScanLogger:
                def log_entry_analysis(self, *args, **kwargs):
                    pass
                def log_exit_analysis(self, *args, **kwargs):
                    pass
            self.scan_logger = DummyScanLogger()

        # Initialize data provider
        self.data_provider_supabase = SupabaseDataProvider()

        # Load configuration from unified config
        self._load_configuration()

    def _load_configuration(self):
        """Load configuration from unified config file"""
        
        # Get SWING configuration
        swing_config = self.config_bridge.get_swing_config()
        
        # Default detection thresholds
        detection = swing_config.get("detection_thresholds", {})
        self.breakout_threshold = detection.get("breakout_threshold", 1.01)  # 1% breakout
        self.breakout_confirmation = detection.get("breakout_confirmation", 0.015)  # 1.5% confirmation
        self.volume_surge = detection.get("volume_surge", 1.3)  # 30% volume increase
        self.rsi_min = detection.get("rsi_min", 45)
        self.rsi_max = detection.get("rsi_max", 75)
        self.min_score = detection.get("min_score", 40)
        
        # Get market cap tiers
        self.market_cap_tiers = self.config_bridge.get_market_cap_tiers()
        
        # Get risk parameters
        risk_params = self.config_bridge.get_risk_parameters()
        self.max_positions = risk_params["max_positions"]
        self.position_timeout = risk_params["position_timeout_hours"]

        # Technical indicator parameters
        self.rsi_period = 14
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.sma_fast = 20
        self.sma_slow = 50
        self.breakout_lookback = 20  # Look back 20 periods for resistance

    def _get_market_cap_tier(self, pair: str) -> str:
        """Get market cap tier for a pair"""
        symbol = pair.split('/')[0]
        
        # Try to get from config
        for tier, symbols in self.market_cap_tiers.items():
            if symbol in symbols:
                return tier
        
        # Default based on common knowledge
        if symbol in ['BTC', 'ETH']:
            return 'large_cap'
        elif symbol in ['SOL', 'ADA', 'AVAX', 'DOT', 'LINK', 'ATOM']:
            return 'mid_cap'
        elif symbol in ['SHIB', 'DOGE', 'PEPE', 'FLOKI', 'BONK']:
            return 'memecoin'
        else:
            return 'small_cap'

    def _get_tier_thresholds(self, tier: str) -> Dict:
        """Get SWING thresholds for a specific tier"""
        swing_config = self.config_bridge.get_swing_config()
        tier_thresholds = swing_config.get("detection_thresholds_by_tier", {}).get(tier, {})
        
        # Return tier-specific or default thresholds
        return {
            "breakout_threshold": tier_thresholds.get("breakout_threshold", self.breakout_threshold),
            "breakout_confirmation": tier_thresholds.get("breakout_confirmation", self.breakout_confirmation),
            "volume_surge": tier_thresholds.get("volume_surge", self.volume_surge),
            "rsi_min": tier_thresholds.get("rsi_min", self.rsi_min),
            "rsi_max": tier_thresholds.get("rsi_max", self.rsi_max),
            "min_score": tier_thresholds.get("min_score", self.min_score),
        }

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
        
        # Resistance levels (for breakout detection)
        dataframe["resistance"] = dataframe["high"].rolling(window=self.breakout_lookback).max()
        dataframe["breakout"] = dataframe["close"] / dataframe["resistance"]
        
        # Support levels
        dataframe["support"] = dataframe["low"].rolling(window=self.breakout_lookback).min()
        
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
        
        # Momentum score (custom indicator)
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
        """
        
        # Get market cap tier for this pair
        tier = self._get_market_cap_tier(metadata['pair'])
        thresholds = self._get_tier_thresholds(tier)
        
        # Log analysis
        self.scan_logger.log_entry_analysis(
            strategy="SWING",
            symbol=metadata['pair'],
            tier=tier,
            thresholds=thresholds,
            indicators={
                "breakout": dataframe["breakout"].iloc[-1] if len(dataframe) > 0 else 1,
                "rsi": dataframe["rsi"].iloc[-1] if len(dataframe) > 0 else 50,
                "volume_ratio": dataframe["volume_ratio"].iloc[-1] if len(dataframe) > 0 else 1,
                "momentum_score": dataframe["momentum_score"].iloc[-1] if len(dataframe) > 0 else 0,
            }
        )
        
        # SWING entry conditions
        conditions = []
        
        # 1. Breakout detected (price above resistance)
        conditions.append(dataframe["breakout"] >= thresholds["breakout_threshold"])
        
        # 2. Volume surge confirmation
        conditions.append(dataframe["volume_ratio"] >= thresholds["volume_surge"])
        
        # 3. RSI in bullish range (not oversold, not overbought)
        conditions.append(dataframe["rsi"] >= thresholds["rsi_min"])
        conditions.append(dataframe["rsi"] <= thresholds["rsi_max"])
        
        # 4. Momentum score above threshold
        conditions.append(dataframe["momentum_score"] >= thresholds["min_score"])
        
        # 5. Positive trend (fast SMA above slow SMA)
        conditions.append(dataframe["sma_fast"] > dataframe["sma_slow"])
        
        # 6. MACD bullish crossover or positive
        conditions.append(
            (dataframe["macd"] > dataframe["macd_signal"]) |
            (dataframe["macd_hist"] > 0)
        )
        
        # 7. Minimum USD volume (liquidity filter)
        conditions.append(dataframe["volume_usd"] >= 100000)  # $100k minimum
        
        # 8. Not too volatile (avoid pump and dumps)
        conditions.append(dataframe["volatility"] < 0.10)  # Less than 10% daily volatility
        
        # 9. Price momentum positive (confirming breakout)
        conditions.append(dataframe["price_change_4h"] > thresholds["breakout_confirmation"])
        
        # Combine all conditions
        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                ['enter_long', 'enter_tag']
            ] = (1, f'swing_{tier}_breakout')
        
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate sell signals for the SWING strategy
        """
        
        # Get market cap tier for this pair
        tier = self._get_market_cap_tier(metadata['pair'])
        
        # Get exit parameters for this tier
        swing_config = self.config_bridge.get_swing_config()
        exits = swing_config.get("exits_by_tier", {}).get(tier, {})
        
        take_profit = exits.get("take_profit", 0.08)  # Default 8%
        
        # Exit conditions
        conditions = []
        
        # 1. Take profit reached (simplified)
        conditions.append(
            dataframe["price_change_24h"] >= take_profit
        )
        
        # 2. RSI overbought (momentum exhausted)
        conditions.append(dataframe["rsi"] >= 80)
        
        # 3. MACD bearish crossover
        conditions.append(
            (dataframe["macd"] < dataframe["macd_signal"]) &
            (dataframe["macd_hist"] < 0)
        )
        
        # 4. Trend reversal (fast SMA crosses below slow SMA)
        conditions.append(
            (dataframe["sma_fast"] < dataframe["sma_slow"]) &
            (dataframe["trend_strength"] < -0.01)
        )
        
        # 5. Volume drying up (momentum lost)
        conditions.append(
            (dataframe["volume_ratio"] < 0.5) &
            (dataframe["price_change_1h"] < 0)
        )
        
        # Combine exit conditions (any of them triggers exit)
        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x | y, conditions),
                ['exit_long', 'exit_tag']
            ] = (1, f'swing_{tier}_exit')
        
        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool, **kwargs) -> Optional[float]:
        """
        Custom stoploss logic based on market cap tier
        """
        
        # Get market cap tier
        tier = self._get_market_cap_tier(pair)
        
        # Get exit parameters for this tier
        swing_config = self.config_bridge.get_swing_config()
        exits = swing_config.get("exits_by_tier", {}).get(tier, {})
        
        stop_loss = exits.get("stop_loss", 0.06)  # Default 6% stop loss
        trailing_stop = exits.get("trailing_stop", 0.04)
        trailing_activation = exits.get("trailing_activation", 0.04)
        
        # Implement trailing stop loss
        if current_profit >= trailing_activation:
            # Trailing stop is active
            return -(trailing_stop)
        
        # Regular stop loss
        return -(stop_loss)

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        """
        Custom exit logic for SWING positions
        """
        
        # Get market cap tier
        tier = self._get_market_cap_tier(pair)
        
        # Get exit parameters for this tier
        swing_config = self.config_bridge.get_swing_config()
        exits = swing_config.get("exits_by_tier", {}).get(tier, {})
        
        take_profit = exits.get("take_profit", 0.08)
        
        # Check if we've reached take profit
        if current_profit >= take_profit:
            return f"swing_take_profit_{tier}"
        
        # Check if position is too old (timeout)
        if trade.open_date_utc:
            trade_duration = (current_time - trade.open_date_utc).total_seconds() / 3600
            # Swing trades can run longer than DCA
            if trade_duration >= self.position_timeout * 2:  # Double the timeout for swing trades
                return f"swing_timeout_{tier}"
        
        return None

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str,
                 side: str, **kwargs) -> float:
        """
        Customize leverage based on market cap tier
        """
        # No leverage for SWING strategy (spot trading only)
        return 1.0


# Required for Freqtrade to find the strategy
from functools import reduce
