"""
CHANNEL Strategy for Freqtrade
Ported from crypto-tracker-v3 SimplePaperTraderV2
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

# Import our custom modules
from config_bridge import ConfigBridge
from scan_logger import get_scan_logger
from data.supabase_dataprovider import SupabaseDataProvider


class ChannelStrategyV1(IStrategy):
    """
    CHANNEL Strategy - Trades based on Bollinger Band channel positions

    This strategy:
    - Enters when price is in lower 15% of Bollinger Band channel
    - Uses market cap tiers for position sizing and stop loss
    - Implements dynamic take profit and stop loss based on market conditions
    """

    # Strategy interface version
    INTERFACE_VERSION = 3

    # Define minimal ROI - we'll use dynamic exits instead
    minimal_roi = {"0": 100}  # Effectively disabled, we use custom exit logic

    # Stop loss - will be overridden by custom logic
    stoploss = -0.10  # Default 10% stop loss

    # Optimal timeframe for the strategy
    timeframe = "1h"

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
        self.scan_logger = get_scan_logger()

        # Initialize data provider
        self.data_provider_supabase = SupabaseDataProvider()

        # Load configuration from unified config
        self._load_configuration()

    def _load_configuration(self):
        """Load configuration from unified config file"""

        # Get thresholds
        thresholds = self.config_bridge.get_channel_thresholds()
        self.channel_entry_threshold = thresholds["entry_threshold"]
        self.channel_exit_threshold = thresholds["exit_threshold"]
        self.rsi_min = thresholds["rsi_min"]
        self.rsi_max = thresholds["rsi_max"]
        self.volume_ratio_min = thresholds["volume_ratio_min"]
        self.volatility_max = thresholds["volatility_max"]

        # Get market cap tiers
        self.market_cap_tiers = self.config_bridge.get_market_cap_tiers()

        # Get risk parameters
        risk_params = self.config_bridge.get_risk_parameters()
        self.max_positions = risk_params["max_positions"]
        self.position_timeout = risk_params["position_timeout_hours"]

        # Technical indicator parameters
        self.bb_period = 20
        self.bb_std = 2.0  # Must be float for TA-Lib
        self.rsi_period = 14

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Calculate all technical indicators needed for the strategy
        """

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

        # Channel position (0 = at lower band, 1 = at upper band)
        dataframe["channel_position"] = (
            (dataframe["close"] - dataframe["bb_lower"])
            / (dataframe["bb_upper"] - dataframe["bb_lower"])
        ).fillna(
            0.5
        )  # Default to middle if bands are invalid

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=int(self.rsi_period))

        # Volume indicators
        dataframe["volume_sma"] = dataframe["volume"].rolling(window=20).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_sma"]

        # Price drop from recent high
        dataframe["high_24h"] = dataframe["high"].rolling(window=24).max()
        dataframe["price_drop_pct"] = (
            (dataframe["close"] - dataframe["high_24h"]) / dataframe["high_24h"] * 100
        ).fillna(0)

        # Volatility
        dataframe["volatility"] = (
            dataframe["close"].pct_change().rolling(window=24).std() * 100
        )

        # Market cap (this will need to be fetched from our database)
        # For now, using a placeholder
        dataframe["market_cap"] = 1000  # millions, will be replaced with actual data

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Define conditions for entering a position
        """

        # Create entry conditions using loaded configuration
        conditions = (
            # Price is in lower portion of Bollinger Band channel
            (dataframe["channel_position"] <= self.channel_entry_threshold)
            &
            # RSI not oversold (avoid catching falling knives)
            (dataframe["rsi"] > self.rsi_min)
            & (dataframe["rsi"] < self.rsi_max)
            &
            # Volume confirmation
            (dataframe["volume_ratio"] > self.volume_ratio_min)
            &
            # Volatility check (avoid extremely volatile conditions)
            (dataframe["volatility"] < self.volatility_max)
            &
            # Ensure we have valid Bollinger Bands
            (dataframe["bb_upper"] > dataframe["bb_lower"])
            &
            # Volume > 0 (ensure market is active)
            (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1

        # Log scan decisions for the latest candle
        if len(dataframe) > 0:
            latest_row = dataframe.iloc[-1]
            if not pd.isna(latest_row.get("enter_long", 0)):
                self.scan_logger.log_entry_analysis(
                    pair=metadata.get("pair", "UNKNOWN"),
                    dataframe_row=latest_row.to_dict(),
                    entry_signal=bool(latest_row.get("enter_long", 0)),
                    strategy="CHANNEL",
                )

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Define conditions for exiting a position
        """

        dataframe.loc[
            (
                # Price is in upper portion of Bollinger Band channel
                (dataframe["channel_position"] >= self.channel_exit_threshold)
                |
                # RSI overbought
                (dataframe["rsi"] > 80)
            ),
            "exit_long",
        ] = 1

        return dataframe

    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        """
        Custom stop loss based on market cap tier
        """

        # Get market cap tier for the symbol
        # This will need to be fetched from our database
        # For now, using default medium tier
        market_cap = 1000  # placeholder

        # Determine tier
        tier = self._get_market_cap_tier(market_cap)

        # Return the stop loss for this tier
        return -self.market_cap_tiers[tier]["sl"]

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> Optional[str]:
        """
        Custom exit logic based on take profit targets
        """

        # Get market cap tier
        tier = self._get_market_cap_tier(pair)

        # Get exit parameters for this tier
        exit_params = self.config_bridge.get_exit_params("CHANNEL", pair.replace("/USDT", ""))
        
        # Check if we've hit take profit
        if current_profit >= exit_params.get("take_profit", 0.05):
            return f"take_profit_{tier}"

        # Check for position timeout
        if trade.open_date_utc:
            hours_open = (current_time - trade.open_date_utc).total_seconds() / 3600
            if hours_open > self.position_timeout:
                return "position_timeout"

        return None

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: datetime,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> bool:
        """
        Called right before placing a buy order.
        Can be used to log scan decisions for ML training.
        """

        # Log scan decision for ML training
        # This will be implemented to write to scan_history table
        self._log_scan_decision(
            symbol=pair,
            strategy="CHANNEL",
            decision="TAKE",
            timestamp=current_time,
            features={
                "channel_position": kwargs.get("channel_position", 0),
                "rsi": kwargs.get("rsi", 50),
                "volume_ratio": kwargs.get("volume_ratio", 1),
                "volatility": kwargs.get("volatility", 0),
                "price_drop_pct": kwargs.get("price_drop_pct", 0),
            },
        )

        return True

    def _get_market_cap_tier(self, symbol: str) -> str:
        """
        Determine market cap tier for a given symbol
        Uses the same logic as SimplePaperTraderV2
        """
        # Remove /USDT suffix if present
        base_symbol = symbol.replace("/USDT", "").replace("-USDT", "")
        
        # Check each tier list in config
        for tier_name, symbols in self.market_cap_tiers.items():
            if base_symbol in symbols:
                return tier_name
        
        # Default to small_cap if not found
        return "small_cap"

    def _log_scan_decision(
        self,
        symbol: str,
        strategy: str,
        decision: str,
        timestamp: datetime,
        features: dict,
    ):
        """
        Log scan decision to database for ML training.
        This will be implemented to connect to Supabase.
        """
        # TODO: Implement Supabase logging
        # For now, just print to console
        print(f"[SCAN] {timestamp} - {symbol} - {strategy} - {decision}")
        print(f"       Features: {features}")

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> float:
        """
        Customize leverage for each new trade. We don't use leverage.
        """
        return 1.0
