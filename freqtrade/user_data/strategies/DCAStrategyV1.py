"""
DCA Strategy for Freqtrade
Dollar Cost Averaging strategy that buys on significant dips
Ported from crypto-tracker-v3 DCA detector
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


class DCAStrategyV1(IStrategy):
    """
    DCA Strategy - Dollar Cost Averaging on significant price drops
    
    This strategy:
    - Enters when price drops 2.25-4% from recent highs (tier-based)
    - Uses market cap tiers for position sizing and risk management
    - Implements grid-based entries for averaging down
    - Uses dynamic exits based on market conditions
    """

    # Strategy interface version
    INTERFACE_VERSION = 3

    # Define minimal ROI - we'll use dynamic exits instead
    minimal_roi = {"0": 100}  # Effectively disabled, we use custom exit logic

    # Stop loss - will be overridden by custom logic based on tiers
    stoploss = -0.15  # Default 15% stop loss (for memecoins)
    
    # Enable trailing stop loss
    trailing_stop = True
    trailing_stop_positive = 0.02  # Start trailing at 2% profit
    trailing_stop_positive_offset = 0.035  # Trail 3.5% behind peak
    trailing_only_offset_is_reached = True  # Only trail after offset is reached

    # Optimal timeframe for the strategy
    timeframe = "1h"  # 1 hour for DCA detection

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
            logger.info("✅ Scan logger initialized in DCAStrategyV1")
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
        
        # Get DCA configuration
        dca_config = self.config_bridge.get_dca_config()
        
        # Default detection thresholds
        self.drop_threshold = dca_config.get("detection_thresholds", {}).get("drop_threshold", -2.25)
        self.volume_threshold = dca_config.get("detection_thresholds", {}).get("volume_threshold", 100000)
        self.volume_requirement = dca_config.get("detection_thresholds", {}).get("volume_requirement", 0.85)
        
        # Grid settings
        grid_settings = dca_config.get("grid_settings", {})
        self.grid_levels = grid_settings.get("grid_levels", 5)
        self.grid_spacing = grid_settings.get("grid_spacing", 0.02)
        
        # Get market cap tiers
        self.market_cap_tiers = self.config_bridge.get_market_cap_tiers()
        
        # Get risk parameters
        risk_params = self.config_bridge.get_risk_parameters()
        self.max_positions = risk_params["max_positions"]
        self.position_timeout = risk_params["position_timeout_hours"]

        # Technical indicator parameters
        self.rsi_period = 14
        self.bb_period = 20
        self.bb_std = 2.0
        self.high_lookback = 24  # 24 hours for recent high

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
        """Get DCA thresholds for a specific tier"""
        dca_config = self.config_bridge.get_dca_config()
        tier_thresholds = dca_config.get("detection_thresholds_by_tier", {}).get(tier, {})
        
        # Return tier-specific or default thresholds
        return {
            "drop_threshold": tier_thresholds.get("drop_threshold", self.drop_threshold),
            "volume_threshold": tier_thresholds.get("volume_threshold", self.volume_threshold),
            "volume_requirement": tier_thresholds.get("volume_requirement", self.volume_requirement),
            "grid_levels": tier_thresholds.get("grid_levels", self.grid_levels),
            "grid_spacing": tier_thresholds.get("grid_spacing", self.grid_spacing),
        }

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
        """
        
        # Get market cap tier for this pair
        tier = self._get_market_cap_tier(metadata['pair'])
        thresholds = self._get_tier_thresholds(tier)
        
        # Log analysis
        self.scan_logger.log_entry_analysis(
            strategy="DCA",
            symbol=metadata['pair'],
            tier=tier,
            thresholds=thresholds,
            indicators={
                "price_drop": dataframe["price_drop_pct"].iloc[-1] if len(dataframe) > 0 else 0,
                "rsi": dataframe["rsi"].iloc[-1] if len(dataframe) > 0 else 50,
                "volume_ratio": dataframe["volume_ratio"].iloc[-1] if len(dataframe) > 0 else 1,
            }
        )
        
        # DCA entry conditions
        conditions = []
        
        # 1. Price has dropped from recent high
        conditions.append(dataframe["price_drop_pct"] <= thresholds["drop_threshold"])
        
        # 2. Volume requirement (at least X% of average)
        conditions.append(dataframe["volume_ratio"] >= thresholds["volume_requirement"])
        
        # 3. Minimum USD volume
        conditions.append(dataframe["volume_usd"] >= thresholds["volume_threshold"])
        
        # 4. RSI not oversold (avoid catching falling knives)
        conditions.append(dataframe["rsi"] >= 25)  # Not extremely oversold
        conditions.append(dataframe["rsi"] <= 65)  # Not overbought
        
        # 5. Price above lower Bollinger Band (not in extreme sell-off)
        conditions.append(dataframe["close"] > dataframe["bb_lower"] * 0.98)
        
        # 6. Optional: Bull market filter (can be toggled)
        # Uncomment to only trade in bull markets
        # conditions.append(dataframe["bull_market"] == True)
        
        # 7. Not too volatile (avoid pump and dumps)
        conditions.append(dataframe["volatility"] < 0.10)  # Less than 10% daily volatility
        
        # Combine all conditions
        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                ['enter_long', 'enter_tag']
            ] = (1, f'dca_{tier}_drop')
        
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate sell signals for the DCA strategy
        """
        
        # Get market cap tier for this pair
        tier = self._get_market_cap_tier(metadata['pair'])
        
        # Get exit parameters for this tier
        dca_config = self.config_bridge.get_dca_config()
        exits = dca_config.get("exits_by_tier", {}).get(tier, {})
        
        take_profit = exits.get("take_profit", 0.07)  # Default 7%
        
        # Exit conditions
        conditions = []
        
        # 1. Take profit reached
        # Calculate profit from entry (simplified - Freqtrade handles this better internally)
        conditions.append(
            dataframe["close"].pct_change(periods=24) >= take_profit
        )
        
        # 2. RSI overbought (momentum exhausted)
        conditions.append(dataframe["rsi"] >= 75)
        
        # 3. Price above upper Bollinger Band (overextended)
        conditions.append(dataframe["close"] > dataframe["bb_upper"])
        
        # Combine exit conditions (any of them triggers exit)
        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x | y, conditions),
                ['exit_long', 'exit_tag']
            ] = (1, f'dca_{tier}_exit')
        
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
        dca_config = self.config_bridge.get_dca_config()
        exits = dca_config.get("exits_by_tier", {}).get(tier, {})
        
        stop_loss = exits.get("stop_loss", 0.08)  # Default 8% stop loss
        trailing_stop = exits.get("trailing_stop", 0.035)
        trailing_activation = exits.get("trailing_activation", 0.035)
        
        # Implement trailing stop loss
        if current_profit >= trailing_activation:
            # Trailing stop is active
            return -(trailing_stop)
        
        # Regular stop loss
        return -(stop_loss)

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        """
        Custom exit logic for DCA positions
        """
        
        # Get market cap tier
        tier = self._get_market_cap_tier(pair)
        
        # Get exit parameters for this tier
        dca_config = self.config_bridge.get_dca_config()
        exits = dca_config.get("exits_by_tier", {}).get(tier, {})
        
        take_profit = exits.get("take_profit", 0.07)
        
        # Check if we've reached take profit
        if current_profit >= take_profit:
            return f"dca_take_profit_{tier}"
        
        # Check if position is too old (timeout)
        if trade.open_date_utc:
            trade_duration = (current_time - trade.open_date_utc).total_seconds() / 3600
            if trade_duration >= self.position_timeout:
                return f"dca_timeout_{tier}"
        
        return None

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str,
                 side: str, **kwargs) -> float:
        """
        Customize leverage based on market cap tier
        """
        # No leverage for DCA strategy (spot trading only)
        return 1.0


# Required for Freqtrade to find the strategy
from functools import reduce
