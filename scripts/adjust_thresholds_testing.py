#!/usr/bin/env python3
"""
Temporarily adjust strategy thresholds for testing
WARNING: These are aggressive settings for testing only!
"""

import sys
sys.path.append('.')

from src.data.supabase_client import SupabaseClient
from datetime import datetime
import json


def adjust_thresholds_for_testing():
    """
    Adjust thresholds to be more aggressive for testing
    """
    supabase = SupabaseClient()
    
    print("\n" + "="*60)
    print("ADJUSTING THRESHOLDS FOR TESTING")
    print("WARNING: These are aggressive settings!")
    print("="*60)
    
    # More aggressive DCA settings
    dca_config = {
        "strategy_name": "DCA",
        "is_active": True,
        "parameters": {
            "drop_threshold": -2.0,  # Was -5.0
            "rsi_oversold": 40,      # Was 30
            "min_volume_ratio": 1.0,  # Was 1.5
            "grid_levels": 5,
            "grid_spacing": 1.0,
            "base_size": 100,
            "take_profit": 5.0,      # Was 10.0
            "stop_loss": -5.0,       # Was -8.0
            "time_exit_hours": 48,   # Was 72
            "ml_confidence_threshold": 0.50  # Was 0.60
        },
        "updated_at": datetime.now().isoformat()
    }
    
    # More aggressive Swing settings
    swing_config = {
        "strategy_name": "Swing",
        "is_active": True,
        "parameters": {
            "breakout_threshold": 1.0,   # Was 2.0
            "volume_surge_min": 1.5,     # Was 2.0
            "momentum_threshold": 2.0,   # Was 3.0
            "momentum_period": 14,
            "ml_confidence_threshold": 0.50,  # Was 0.60
            "default_take_profit": 5.0,  # Was 10.0
            "default_stop_loss": -3.0    # Was -5.0
        },
        "updated_at": datetime.now().isoformat()
    }
    
    # More aggressive Channel settings
    channel_config = {
        "strategy_name": "Channel",
        "is_active": True,
        "parameters": {
            "channel_period": 20,
            "min_channel_width": 1.0,    # Was 2.0
            "max_channel_width": 15.0,   # Was 10.0
            "min_touches": 2,            # Was 3
            "position_threshold": 0.15,  # Was 0.2 (closer to boundaries)
            "ml_confidence_threshold": 0.50,  # Was 0.60
            "default_take_profit": 3.0,  # Was 5.0
            "default_stop_loss": -2.0    # Was -3.0
        },
        "updated_at": datetime.now().isoformat()
    }
    
    # Save to database (optional - uncomment to actually save)
    save_to_db = input("\nSave to database? (y/n): ").lower() == 'y'
    
    if save_to_db:
        try:
            # Update or insert DCA config
            supabase.client.table("strategy_configs").upsert(dca_config).execute()
            print("✅ DCA config updated")
            
            # Update or insert Swing config
            supabase.client.table("strategy_configs").upsert(swing_config).execute()
            print("✅ Swing config updated")
            
            # Update or insert Channel config
            supabase.client.table("strategy_configs").upsert(channel_config).execute()
            print("✅ Channel config updated")
            
            print("\n⚠️  REMEMBER: These are testing thresholds!")
            print("Revert to production settings when done testing.")
            
        except Exception as e:
            print(f"❌ Error saving configs: {e}")
    else:
        print("\nTest configurations (not saved):")
        print("\nDCA:", json.dumps(dca_config['parameters'], indent=2))
        print("\nSwing:", json.dumps(swing_config['parameters'], indent=2))
        print("\nChannel:", json.dumps(channel_config['parameters'], indent=2))
    
    # Also suggest local config changes
    print("\n" + "="*60)
    print("ALTERNATIVE: Update scripts/run_paper_trading.py directly")
    print("="*60)
    print("""
    In run_paper_trading.py, update the config dictionary:
    
    'dca_config': {
        'drop_threshold': -2.0,    # More aggressive
        'min_volume_ratio': 1.0,   # Less strict
        'rsi_oversold': 40,        # Higher RSI threshold
        ...
    },
    
    'swing_config': {
        'breakout_threshold': 1.0,  # Lower breakout requirement
        'volume_surge_min': 1.5,    # Less volume needed
        'momentum_threshold': 2.0,  # Less momentum needed
        ...
    }
    """)


if __name__ == "__main__":
    adjust_thresholds_for_testing()
