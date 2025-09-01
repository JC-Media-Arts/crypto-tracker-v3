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
from loguru import logger

# Import our custom modules
from config_bridge import ConfigBridge
from scan_logger import get_scan_logger


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
    
    # Enable trailing stop loss
    trailing_stop = True
    trailing_stop_positive = 0.01  # Start trailing at 1% profit
    trailing_stop_positive_offset = 0.02  # Trail 2% behind peak
    trailing_only_offset_is_reached = True  # Only trail after offset is reached

    # Optimal timeframe for the strategy
    # Using 1m since we have 1-minute data in Supabase
    # Note: More signals but also more noise - good for paper trading
    timeframe = "1m"

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
            logger.info("✅ Scan logger initialized in ChannelStrategyV1")
        except Exception as e:
            logger.error(f"❌ Failed to initialize scan logger: {e}")
            # Create dummy logger
            class DummyScanLogger:
                def log_entry_analysis(self, *args, **kwargs):
                    pass
                def log_exit_analysis(self, *args, **kwargs):
                    pass
            self.scan_logger = DummyScanLogger()

        # Note: Data provider is now handled by Freqtrade using our custom provider
        # No need to initialize SupabaseDataProvider here

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
        
        # Get tier-specific thresholds for this pair
        pair = metadata.get("pair", "UNKNOWN")
        symbol = pair.split("/")[0] if "/" in pair else pair
        
        # Get tier-specific thresholds
        tier_thresholds = self.config_bridge.get_tier_thresholds("CHANNEL", symbol)
        
        # Use tier-specific values or fall back to defaults
        entry_threshold = tier_thresholds.get("entry_threshold", self.channel_entry_threshold)
        volume_ratio_min = tier_thresholds.get("volume_ratio_min", self.volume_ratio_min)
        rsi_min = tier_thresholds.get("rsi_min", self.rsi_min)
        rsi_max = tier_thresholds.get("rsi_max", self.rsi_max)

        # Create entry conditions using tier-specific configuration
        conditions = (
            # Price is in lower portion of Bollinger Band channel
            (dataframe["channel_position"] <= entry_threshold)
            &
            # RSI not oversold (avoid catching falling knives)
            (dataframe["rsi"] > rsi_min)
            & (dataframe["rsi"] < rsi_max)
            &
            # Volume confirmation
            (dataframe["volume_ratio"] > volume_ratio_min)
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

        # Log scan decisions for the latest candle (always log, not just on entry signals)
        if len(dataframe) > 0:
            latest_row = dataframe.iloc[-1]
            try:
                # Always log the scan, whether there's an entry signal or not
                self.scan_logger.log_entry_analysis(
                    pair=metadata.get("pair", "UNKNOWN"),
                    dataframe_row=latest_row.to_dict(),
                    entry_signal=bool(latest_row.get("enter_long", 0)),
                    strategy="CHANNEL",
                )
                # Log every 10th scan to confirm it's working
                if hasattr(self, '_scan_count'):
                    self._scan_count += 1
                else:
                    self._scan_count = 1
                if self._scan_count % 10 == 0:
                    logger.info(f"📊 Logged scan #{self._scan_count} for {metadata.get('pair', 'UNKNOWN')} (signal={bool(latest_row.get('enter_long', 0))})")
            except Exception as e:
                logger.error(f"❌ Failed to log scan for {metadata.get('pair', 'UNKNOWN')}: {e}")

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
        Custom stop loss and trailing stop based on market cap tier
        """
        
        # Get market cap tier for the symbol
        # Extract base symbol from pair (works for both /USD and /USDT)
        symbol = pair.split("/")[0] if "/" in pair else pair
        tier = self._get_market_cap_tier(symbol)
        
        # Get exit parameters for this tier
        exit_params = self.config_bridge.get_exit_params("CHANNEL", symbol)
        
        # Get stop loss and trailing stop values
        stop_loss = exit_params.get("stop_loss", 0.10)
        trailing_stop = exit_params.get("trailing_stop", 0.02)
        trailing_activation = exit_params.get("trailing_activation", 0.02)
        
        # If we're in profit and above activation threshold, use trailing stop
        if current_profit >= trailing_activation:
            # Return trailing stop distance (negative value)
            return -trailing_stop
        
        # Otherwise use fixed stop loss
        return -stop_loss

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
        # Extract base symbol from pair
        symbol = pair.split("/")[0] if "/" in pair else pair
        exit_params = self.config_bridge.get_exit_params("CHANNEL", symbol)
        
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
        Enforces position limits and logs scan decisions for ML training.
        """
        
        # Get position limits from config
        config = self.config_bridge.get_config()
        position_mgmt = config.get('position_management', {})
        max_per_strategy = position_mgmt.get('max_positions_per_strategy', 50)
        max_per_symbol = position_mgmt.get('max_positions_per_symbol', 3)
        
        # Check per-strategy limit
        # Count all open trades for this strategy
        open_trades = Trade.get_open_trades()
        strategy_trades = [t for t in open_trades if t.strategy == 'ChannelStrategyV1']
        
        if len(strategy_trades) >= max_per_strategy:
            logger.info(
                f"Rejecting {pair} entry: Strategy limit reached "
                f"({len(strategy_trades)}/{max_per_strategy})"
            )
            # Log as SKIP for ML training
            self._log_scan_decision(
                symbol=pair,
                strategy="CHANNEL",
                decision="SKIP",
                timestamp=current_time,
                features={
                    "channel_position": kwargs.get("channel_position", 0),
                    "rsi": kwargs.get("rsi", 50),
                    "volume_ratio": kwargs.get("volume_ratio", 1),
                    "volatility": kwargs.get("volatility", 0),
                    "price_drop_pct": kwargs.get("price_drop_pct", 0),
                    "skip_reason": "strategy_limit",
                },
            )
            return False
        
        # Check per-symbol limit
        symbol_trades = [t for t in open_trades if t.pair == pair]
        
        if len(symbol_trades) >= max_per_symbol:
            logger.info(
                f"Rejecting {pair} entry: Symbol limit reached "
                f"({len(symbol_trades)}/{max_per_symbol})"
            )
            # Log as SKIP for ML training
            self._log_scan_decision(
                symbol=pair,
                strategy="CHANNEL",
                decision="SKIP",
                timestamp=current_time,
                features={
                    "channel_position": kwargs.get("channel_position", 0),
                    "rsi": kwargs.get("rsi", 50),
                    "volume_ratio": kwargs.get("volume_ratio", 1),
                    "volatility": kwargs.get("volatility", 0),
                    "price_drop_pct": kwargs.get("price_drop_pct", 0),
                    "skip_reason": "symbol_limit",
                },
            )
            return False

        # All limits passed, log as TAKE
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

        logger.info(
            f"Accepting {pair} entry: "
            f"Strategy {len(strategy_trades)}/{max_per_strategy}, "
            f"Symbol {len(symbol_trades)}/{max_per_symbol}"
        )
        
        return True

    def _get_market_cap_tier(self, symbol: str) -> str:
        """
        Determine market cap tier for a given symbol
        Uses the same logic as SimplePaperTraderV2
        """
        # Extract base symbol from pair (works for /USD, /USDT, etc.)
        base_symbol = symbol.split("/")[0] if "/" in symbol else symbol.split("-")[0] if "-" in symbol else symbol
        
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
    
    def confirm_trade_exit(
        self,
        pair: str,
        trade,  # Trade object
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        exit_reason: str,
        current_time: datetime,
        **kwargs,
    ) -> bool:
        """
        Called right before placing an exit order.
        Triggers trade sync to Supabase for ML training.
        """
        logger.info(
            f"Exit confirmed for {pair}: {exit_reason} at {rate}"
        )
        
        # Trigger trade sync after exit (runs in background)
        try:
            import subprocess
            subprocess.Popen(
                ["python", "/freqtrade/trade_sync.py", "--once"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            logger.debug("Trade sync triggered")
        except Exception as e:
            logger.warning(f"Trade sync not available: {e}")
        
        return True
