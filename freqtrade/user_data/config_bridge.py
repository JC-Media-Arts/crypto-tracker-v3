"""
Configuration Bridge between unified config and Freqtrade
Syncs settings from paper_trading_config_unified.json to Freqtrade
"""

import json
import os
from typing import Dict, Any
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class ConfigBridge:
    """
    Bridges the gap between our unified configuration system
    and Freqtrade's configuration format
    """

    def __init__(self, unified_config_path: str = None):
        """
        Initialize the configuration bridge

        Args:
            unified_config_path: Path to unified config file
        """
        if unified_config_path is None:
            unified_config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "configs",
                "paper_trading_config_unified.json",
            )

        self.unified_config_path = unified_config_path
        self.config = self.load_unified_config()

    def load_unified_config(self) -> Dict[str, Any]:
        """Load the unified configuration file"""
        try:
            with open(self.unified_config_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading unified config: {e}")
            return {}
    
    def get_config(self) -> Dict[str, Any]:
        """Get the full unified config (reloads to get latest)"""
        self.config = self.load_unified_config()
        return self.config

    def get_strategy_config(self, strategy_name: str = "CHANNEL") -> Dict[str, Any]:
        """
        Get strategy-specific configuration

        Args:
            strategy_name: Name of the strategy

        Returns:
            Strategy configuration dict
        """
        # Updated to read from correct location in unified config
        strategies = self.config.get("strategies", {})

        if strategy_name not in strategies:
            logger.warning(f"Strategy {strategy_name} not found in config")
            return {}

        return strategies[strategy_name]

    def get_channel_thresholds(self) -> Dict[str, float]:
        """Get CHANNEL strategy thresholds"""
        # Reload config to get latest values
        self.config = self.load_unified_config()
        channel_config = self.get_strategy_config("CHANNEL")
        
        # Get detection thresholds (where the actual values are)
        detection = channel_config.get("detection_thresholds", {})
        
        # IMPORTANT: Use the actual configured values from admin panel
        # buy_zone appears to be the correct field for entry (0.03 = bottom 3% of channel)
        # sell_zone appears to be the correct field for exit (0.97 = top 3% of channel)
        
        return {
            "entry_threshold": detection.get("buy_zone", 0.15),  # Use buy_zone from config
            "exit_threshold": detection.get("sell_zone", 0.85),   # Use sell_zone from config
            "rsi_min": detection.get("rsi_oversold", 30),  # RSI oversold threshold
            "rsi_max": detection.get("rsi_overbought", 70),  # RSI overbought threshold
            "volume_ratio_min": detection.get("volume_ratio_min", 1.0),
            "volatility_max": detection.get("volatility_max", 10),
            "channel_strength_min": detection.get("channel_strength_min", 0.90),
        }

    def get_market_cap_tiers(self) -> Dict[str, Dict[str, float]]:
        """Get market cap tier configuration"""
        risk_config = self.config.get("risk_management", {})
        tiers = risk_config.get("market_cap_tiers", {})

        # Convert to format expected by strategy
        result = {}
        for tier_name, tier_config in tiers.items():
            result[tier_name] = {
                "min": tier_config.get("min_market_cap", 0),
                "sl": tier_config.get("stop_loss", 0.10),
                "tp": tier_config.get("take_profit", 0.15),
                "size_pct": tier_config.get("position_size_pct", 0.01),
            }

        return result

    def get_exit_params(self, strategy: str, symbol: str) -> Dict[str, float]:
        """
        Get exit parameters for a strategy and symbol
        Matches the logic from ConfigLoader
        """
        # Get tier for symbol
        tier = self.get_tier_for_symbol(symbol)
        
        # Get strategy config
        strategy_config = self.config.get("strategies", {}).get(strategy.upper(), {})
        
        # Get exits by tier
        exits_by_tier = strategy_config.get("exits_by_tier", {})
        tier_exits = exits_by_tier.get(tier, {})
        
        # Return with defaults if not found
        return {
            "take_profit": tier_exits.get("take_profit", 0.05),
            "stop_loss": tier_exits.get("stop_loss", 0.05),
            "trailing_stop": tier_exits.get("trailing_stop", 0.02),
            "trailing_activation": tier_exits.get("trailing_activation", 0.02),
        }
    
    def get_tier_for_symbol(self, symbol: str) -> str:
        """
        Get market cap tier for a symbol
        """
        # Remove any suffixes
        base_symbol = symbol.replace("/USDT", "").replace("-USDT", "").upper()
        
        # Check market_cap_tiers
        tiers = self.config.get("market_cap_tiers", {})
        
        for tier_name, symbols in tiers.items():
            if base_symbol in symbols:
                return tier_name
        
        # Default to small_cap
        return "small_cap"

    def get_risk_parameters(self) -> Dict[str, Any]:
        """Get risk management parameters"""
        risk_config = self.config.get("risk_management", {})

        return {
            "max_positions": risk_config.get("max_positions", 10),
            "max_position_size": risk_config.get("max_position_size", 0.1),
            "daily_loss_limit": risk_config.get("daily_loss_limit", 0.05),
            "position_timeout_hours": risk_config.get("position_timeout_hours", 72),
        }

    def get_symbols_whitelist(self) -> list:
        """Get list of symbols to trade"""
        symbols = self.config.get("symbols", [])

        # Convert to Freqtrade pair format
        return [f"{symbol}/USDT" for symbol in symbols]

    def update_freqtrade_config(self, freqtrade_config_path: str) -> bool:
        """
        Update Freqtrade configuration file with unified config values

        Args:
            freqtrade_config_path: Path to Freqtrade config.json

        Returns:
            True if successful
        """
        try:
            # Load existing Freqtrade config
            with open(freqtrade_config_path, "r") as f:
                ft_config = json.load(f)

            # Update with unified config values
            risk_params = self.get_risk_parameters()

            ft_config["max_open_trades"] = risk_params["max_positions"]
            ft_config["exchange"]["pair_whitelist"] = self.get_symbols_whitelist()

            # Save updated config
            with open(freqtrade_config_path, "w") as f:
                json.dump(ft_config, f, indent=4)

            logger.info(f"Updated Freqtrade config at {freqtrade_config_path}")
            return True

        except Exception as e:
            logger.error(f"Error updating Freqtrade config: {e}")
            return False

    def sync_to_strategy(self, strategy_instance: Any) -> None:
        """
        Sync configuration to a running strategy instance

        Args:
            strategy_instance: Instance of the Freqtrade strategy
        """
        # Update strategy parameters
        thresholds = self.get_channel_thresholds()
        strategy_instance.channel_entry_threshold = thresholds["entry_threshold"]
        strategy_instance.channel_exit_threshold = thresholds["exit_threshold"]

        # Update market cap tiers
        strategy_instance.market_cap_tiers = self.get_market_cap_tiers()

        # Update risk parameters
        risk_params = self.get_risk_parameters()
        strategy_instance.max_positions = risk_params["max_positions"]
        strategy_instance.position_timeout = risk_params["position_timeout_hours"]

        logger.info("Synced configuration to strategy instance")

    def watch_for_changes(self, callback=None, interval: int = 60) -> None:
        """
        Watch unified config file for changes and trigger updates

        Args:
            callback: Function to call when config changes
            interval: Check interval in seconds
        """
        import time
        import hashlib

        last_hash = None

        while True:
            try:
                # Calculate file hash
                with open(self.unified_config_path, "rb") as f:
                    current_hash = hashlib.md5(f.read()).hexdigest()

                # Check if file has changed
                if last_hash and current_hash != last_hash:
                    logger.info("Configuration file changed, reloading...")
                    self.config = self.load_unified_config()

                    if callback:
                        callback(self.config)

                last_hash = current_hash

            except Exception as e:
                logger.error(f"Error watching config file: {e}")

            time.sleep(interval)
