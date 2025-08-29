#!/usr/bin/env python3
"""
Update configuration to support tier-specific entry thresholds
"""

import json
from pathlib import Path
import sys

sys.path.append(".")

from src.config.config_loader import ConfigLoader


def update_config_structure():
    """Update config to support tier-specific entry thresholds"""
    
    # Load config directly from file
    config_path = Path("configs/paper_trading_config_unified.json")
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Create new structure for each strategy
    strategies_update = {}
    
    # DCA Strategy - tier-specific thresholds
    strategies_update["DCA"] = {
        **config["strategies"]["DCA"],
        "detection_thresholds_by_tier": {
            "large_cap": {
                "drop_threshold": -3.5,  # Easier for stable coins
                "volume_requirement": 0.85,
                "volume_threshold": 100000,
                "grid_levels": 3,
                "grid_spacing": 0.02
            },
            "mid_cap": {
                "drop_threshold": -4.0,  # Current default
                "volume_requirement": 0.85,
                "volume_threshold": 75000,
                "grid_levels": 4,
                "grid_spacing": 0.025
            },
            "small_cap": {
                "drop_threshold": -4.5,
                "volume_requirement": 0.80,
                "volume_threshold": 50000,
                "grid_levels": 5,
                "grid_spacing": 0.03
            },
            "memecoin": {
                "drop_threshold": -5.0,  # Harder for volatile coins
                "volume_requirement": 0.75,
                "volume_threshold": 25000,
                "grid_levels": 5,  # More levels for volatility
                "grid_spacing": 0.04
            }
        }
    }
    
    # SWING Strategy - tier-specific thresholds
    strategies_update["SWING"] = {
        **config["strategies"]["SWING"],
        "detection_thresholds_by_tier": {
            "large_cap": {
                "breakout_threshold": 1.008,  # Smaller moves matter more
                "breakout_confirmation": 0.01,
                "volume_surge": 1.2,
                "rsi_min": 45,
                "rsi_max": 75,
                "min_score": 35
            },
            "mid_cap": {
                "breakout_threshold": 1.01,  # Current default
                "breakout_confirmation": 0.015,
                "volume_surge": 1.3,
                "rsi_min": 45,
                "rsi_max": 75,
                "min_score": 40
            },
            "small_cap": {
                "breakout_threshold": 1.015,
                "breakout_confirmation": 0.02,
                "volume_surge": 1.4,
                "rsi_min": 40,
                "rsi_max": 80,
                "min_score": 45
            },
            "memecoin": {
                "breakout_threshold": 1.02,  # Need bigger moves
                "breakout_confirmation": 0.025,
                "volume_surge": 1.5,
                "rsi_min": 35,
                "rsi_max": 85,
                "min_score": 50
            }
        }
    }
    
    # CHANNEL Strategy - tier-specific thresholds
    strategies_update["CHANNEL"] = {
        **config["strategies"]["CHANNEL"],
        "detection_thresholds_by_tier": {
            "large_cap": {
                "entry_threshold": 0.85,  # Tighter channels
                "exit_threshold": 0.15,
                "channel_width_min": 0.02,
                "channel_width_max": 0.08,
                "channel_strength_min": 0.80,
                "buy_zone": 0.03  # 3% from bottom
            },
            "mid_cap": {
                "entry_threshold": 0.9,  # Current default
                "exit_threshold": 0.1,
                "channel_width_min": 0.03,
                "channel_width_max": 0.10,
                "channel_strength_min": 0.75,
                "buy_zone": 0.05  # 5% from bottom
            },
            "small_cap": {
                "entry_threshold": 0.9,
                "exit_threshold": 0.1,
                "channel_width_min": 0.04,
                "channel_width_max": 0.12,
                "channel_strength_min": 0.70,
                "buy_zone": 0.07
            },
            "memecoin": {
                "entry_threshold": 0.95,  # Wider channels for volatility
                "exit_threshold": 0.05,
                "channel_width_min": 0.05,
                "channel_width_max": 0.15,
                "channel_strength_min": 0.65,
                "buy_zone": 0.10  # 10% from bottom
            }
        }
    }
    
    # Update the config
    config["strategies"]["DCA"] = strategies_update["DCA"]
    config["strategies"]["SWING"] = strategies_update["SWING"]
    config["strategies"]["CHANNEL"] = strategies_update["CHANNEL"]
    
    # Save the updated config
    config_path = Path("configs/paper_trading_config_unified.json")
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print("✅ Configuration updated with tier-specific entry thresholds")
    print("\nDCA Thresholds by Tier:")
    for tier, thresholds in strategies_update["DCA"]["detection_thresholds_by_tier"].items():
        print(f"  {tier}: drop={thresholds['drop_threshold']}%, grid_levels={thresholds['grid_levels']}")
    
    print("\nSWING Thresholds by Tier:")
    for tier, thresholds in strategies_update["SWING"]["detection_thresholds_by_tier"].items():
        print(f"  {tier}: breakout={thresholds['breakout_threshold']}, volume_surge={thresholds['volume_surge']}x")
    
    print("\nCHANNEL Thresholds by Tier:")
    for tier, thresholds in strategies_update["CHANNEL"]["detection_thresholds_by_tier"].items():
        print(f"  {tier}: entry={thresholds['entry_threshold']}, buy_zone={thresholds['buy_zone']*100}%")


if __name__ == "__main__":
    update_config_structure()
