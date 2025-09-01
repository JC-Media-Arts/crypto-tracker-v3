#!/usr/bin/env python3
"""
Apply optimized hyperopt parameters to Supabase trading_config table.
Updates the Channel and DCA strategies with the optimized values from hyperopt.
"""

import os
import json
import sys
from pathlib import Path
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("Supabase credentials not found in environment variables")
    sys.exit(1)

# Initialize Supabase client
client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Optimized parameters from hyperopt
CHANNEL_PARAMS = {
    "buy": {
        "bb_period": 30,  # Bollinger Band period
        "bb_std": 2.0,  # Bollinger Band std dev
        "channel_entry_threshold": 0.1,  # Channel position threshold (10%)
        "price_drop_min": -8.9,  # Min price drop percentage
        "rsi_max": 65,  # Max RSI for entry
        "rsi_min": 32,  # Min RSI for entry
        "volatility_max": 0.03,  # Max volatility threshold (3%)
        "volume_ratio_min": 1.0,  # Min volume ratio
    },
    "sell": {
        "channel_exit_threshold": 0.94,  # Channel exit position (94%)
        "rsi_high": 72,  # RSI high threshold
        "take_profit": 0.04,  # Take profit percentage (4%)
    },
    "stoploss": -0.146,  # 14.6% stoploss
    "trailing": {
        "trailing_stop": True,
        "trailing_stop_positive": 0.222,  # Start trailing at 22.2% profit
        "trailing_stop_positive_offset": 0.248,  # Trail by 24.8% from peak
        "trailing_only_offset_is_reached": True,
    }
}

DCA_PARAMS = {
    "buy": {
        "drop_threshold": -3.75,  # Min price drop to trigger
        "grid_levels": 3,  # Number of DCA levels
        "grid_spacing": 0.014,  # Spacing between levels (1.4%)
        "rsi_max": 56,  # Max RSI for entry
        "rsi_min": 28,  # Min RSI for entry
        "volatility_max": 0.15,  # Max volatility (15%)
        "volume_requirement": 1.29,  # Volume ratio requirement
        "volume_threshold": 73815,  # Min volume in USDT
    },
    "sell": {
        "rsi_high": 77,  # RSI exit threshold
        "take_profit": 0.03,  # Take profit percentage (3%)
    },
    "stoploss": -0.279,  # 27.9% stoploss
    "trailing": {
        "trailing_stop": True,
        "trailing_stop_positive": 0.011,  # Start trailing at 1.1% profit
        "trailing_stop_positive_offset": 0.026,  # Trail by 2.6% from peak
        "trailing_only_offset_is_reached": False,
    }
}

def get_current_config():
    """Fetch the current trading configuration from Supabase."""
    try:
        response = client.table("trading_config").select("*").eq("config_key", "active").single().execute()
        if response.data:
            return response.data
        else:
            logger.error("No active configuration found in trading_config")
            return None
    except Exception as e:
        logger.error(f"Error fetching current config: {e}")
        return None

def update_channel_params(config_data):
    """Update CHANNEL strategy parameters with hyperopt values."""
    strategies = config_data.get("strategies", {})
    channel = strategies.get("CHANNEL", {})
    
    # Update detection thresholds (buy parameters)
    channel["detection_thresholds"] = {
        "channel_entry_threshold": CHANNEL_PARAMS["buy"]["channel_entry_threshold"],
        "price_drop_min": CHANNEL_PARAMS["buy"]["price_drop_min"],
        "rsi_max": CHANNEL_PARAMS["buy"]["rsi_max"],
        "rsi_min": CHANNEL_PARAMS["buy"]["rsi_min"],
        "volatility_max": CHANNEL_PARAMS["buy"]["volatility_max"],
        "volume_ratio_min": CHANNEL_PARAMS["buy"]["volume_ratio_min"],
        "bb_period": CHANNEL_PARAMS["buy"]["bb_period"],
        "bb_std": CHANNEL_PARAMS["buy"]["bb_std"],
    }
    
    # Update exit parameters for all tiers with optimized values
    for tier in ["large_cap", "mid_cap", "small_cap", "memecoin"]:
        if tier in channel.get("exits_by_tier", {}):
            channel["exits_by_tier"][tier].update({
                "stop_loss": abs(CHANNEL_PARAMS["stoploss"]),  # Convert to positive
                "take_profit": CHANNEL_PARAMS["sell"]["take_profit"],
                "trailing_stop": CHANNEL_PARAMS["trailing"]["trailing_stop_positive_offset"],
                "trailing_activation": CHANNEL_PARAMS["trailing"]["trailing_stop_positive"],
                "channel_exit_threshold": CHANNEL_PARAMS["sell"]["channel_exit_threshold"],
                "rsi_high": CHANNEL_PARAMS["sell"]["rsi_high"],
            })
    
    # Add hyperopt metadata
    channel["hyperopt_optimized"] = True
    channel["hyperopt_date"] = "2025-08-31"
    channel["hyperopt_performance"] = {
        "win_rate": 0.702,
        "avg_profit": 0.004,
        "total_profit": 0.0015,
    }
    
    strategies["CHANNEL"] = channel
    config_data["strategies"] = strategies
    return config_data

def update_dca_params(config_data):
    """Update DCA strategy parameters with hyperopt values."""
    strategies = config_data.get("strategies", {})
    dca = strategies.get("DCA", {})
    
    # Update detection thresholds (buy parameters)
    dca["detection_thresholds"] = {
        "drop_threshold": DCA_PARAMS["buy"]["drop_threshold"],
        "grid_levels": DCA_PARAMS["buy"]["grid_levels"],
        "grid_spacing": DCA_PARAMS["buy"]["grid_spacing"],
        "rsi_max": DCA_PARAMS["buy"]["rsi_max"],
        "rsi_min": DCA_PARAMS["buy"]["rsi_min"],
        "volatility_max": DCA_PARAMS["buy"]["volatility_max"],
        "volume_requirement": DCA_PARAMS["buy"]["volume_requirement"],
        "volume_threshold": DCA_PARAMS["buy"]["volume_threshold"],
    }
    
    # Update exit parameters for all tiers with optimized values
    for tier in ["large_cap", "mid_cap", "small_cap", "memecoin"]:
        if tier in dca.get("exits_by_tier", {}):
            dca["exits_by_tier"][tier].update({
                "stop_loss": abs(DCA_PARAMS["stoploss"]),  # Convert to positive
                "take_profit": DCA_PARAMS["sell"]["take_profit"],
                "trailing_stop": DCA_PARAMS["trailing"]["trailing_stop_positive_offset"],
                "trailing_activation": DCA_PARAMS["trailing"]["trailing_stop_positive"],
                "rsi_high": DCA_PARAMS["sell"]["rsi_high"],
            })
    
    # Update detection thresholds by tier with base values
    for tier in ["large_cap", "mid_cap", "small_cap", "memecoin"]:
        if tier in dca.get("detection_thresholds_by_tier", {}):
            # Keep tier-specific adjustments but update base values
            tier_config = dca["detection_thresholds_by_tier"][tier]
            tier_config["grid_levels"] = DCA_PARAMS["buy"]["grid_levels"]
            tier_config["grid_spacing"] = DCA_PARAMS["buy"]["grid_spacing"]
            tier_config["drop_threshold"] = DCA_PARAMS["buy"]["drop_threshold"]
            tier_config["volume_requirement"] = DCA_PARAMS["buy"]["volume_requirement"]
            
            # Adjust volume threshold by tier
            if tier == "large_cap":
                tier_config["volume_threshold"] = DCA_PARAMS["buy"]["volume_threshold"] * 1.5
            elif tier == "mid_cap":
                tier_config["volume_threshold"] = DCA_PARAMS["buy"]["volume_threshold"]
            elif tier == "small_cap":
                tier_config["volume_threshold"] = DCA_PARAMS["buy"]["volume_threshold"] * 0.75
            else:  # memecoin
                tier_config["volume_threshold"] = DCA_PARAMS["buy"]["volume_threshold"] * 0.5
    
    # Add hyperopt metadata
    dca["hyperopt_optimized"] = True
    dca["hyperopt_date"] = "2025-08-31"
    dca["hyperopt_performance"] = {
        "win_rate": 0.685,
        "avg_profit": 0.004,
        "total_profit": 0.002,
    }
    
    strategies["DCA"] = dca
    config_data["strategies"] = strategies
    return config_data

def disable_swing_strategy(config_data):
    """Disable SWING strategy due to poor hyperopt results."""
    strategies = config_data.get("strategies", {})
    if "SWING" in strategies:
        strategies["SWING"]["enabled"] = False
        strategies["SWING"]["disabled_reason"] = "No profitable parameters found during hyperopt on 5m timeframe"
        strategies["SWING"]["hyperopt_date"] = "2025-08-31"
        strategies["SWING"]["hyperopt_result"] = "failed"
    
    config_data["strategies"] = strategies
    return config_data

def main():
    """Main function to apply hyperopt parameters."""
    logger.info("Starting hyperopt parameter application to Supabase...")
    
    # Get current config
    current_config = get_current_config()
    if not current_config:
        logger.error("Failed to fetch current configuration")
        return
    
    config_data = current_config["config_data"]
    logger.info(f"Current config version: {config_data.get('version', 'unknown')}")
    
    # Apply hyperopt parameters
    logger.info("Applying CHANNEL strategy hyperopt parameters...")
    config_data = update_channel_params(config_data)
    
    logger.info("Applying DCA strategy hyperopt parameters...")
    config_data = update_dca_params(config_data)
    
    logger.info("Disabling SWING strategy (no profitable parameters found)...")
    config_data = disable_swing_strategy(config_data)
    
    # Update version
    current_version = config_data.get("version", "1.0.0")
    version_parts = current_version.split(".")
    if len(version_parts) == 3:
        # Increment patch version
        version_parts[2] = str(int(version_parts[2]) + 1)
        new_version = ".".join(version_parts)
    else:
        new_version = "1.0.38"  # Default if version format is unexpected
    
    config_data["version"] = new_version
    config_data["last_hyperopt_update"] = datetime.utcnow().isoformat()
    
    # Update in Supabase
    try:
        response = client.table("trading_config").update({
            "config_data": config_data,
            "config_version": new_version,
            "updated_by": "hyperopt_script",
            "update_source": "hyperopt",
            "notes": "Applied optimized parameters from hyperopt run on 2025-08-31"
        }).eq("config_key", "active").execute()
        
        if response.data:
            logger.success(f"Successfully updated trading config to version {new_version}")
            logger.info("Summary of changes:")
            logger.info("  - CHANNEL: Updated with 70.2% win rate parameters")
            logger.info("  - DCA: Updated with 68.5% win rate parameters")
            logger.info("  - SWING: Disabled (no profitable parameters found)")
            
            # Display key parameters
            logger.info("\nKey optimized parameters:")
            logger.info("CHANNEL Strategy:")
            logger.info(f"  - Entry: {CHANNEL_PARAMS['buy']['price_drop_min']}% drop, {CHANNEL_PARAMS['buy']['channel_entry_threshold']} channel position")
            logger.info(f"  - Exit: {CHANNEL_PARAMS['sell']['channel_exit_threshold']} channel position, {CHANNEL_PARAMS['sell']['take_profit']*100}% take profit")
            logger.info(f"  - Stop Loss: {CHANNEL_PARAMS['stoploss']*100}%")
            
            logger.info("\nDCA Strategy:")
            logger.info(f"  - Entry: {DCA_PARAMS['buy']['drop_threshold']}% drop, {DCA_PARAMS['buy']['grid_levels']} grid levels")
            logger.info(f"  - Exit: RSI {DCA_PARAMS['sell']['rsi_high']}, {DCA_PARAMS['sell']['take_profit']*100}% take profit")
            logger.info(f"  - Stop Loss: {DCA_PARAMS['stoploss']*100}%")
        else:
            logger.error("Failed to update configuration")
            
    except Exception as e:
        logger.error(f"Error updating configuration: {e}")
        return
    
    logger.success("Hyperopt parameters successfully applied to Supabase!")

if __name__ == "__main__":
    main()


