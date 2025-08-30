#!/usr/bin/env python3
"""
Test Kill Switch functionality
"""

import sys
import json
import time
from pathlib import Path
from loguru import logger

sys.path.append(str(Path(__file__).parent.parent))

from src.config.config_loader import ConfigLoader
from src.data.supabase_client import SupabaseClient
from src.trading.risk_manager import RiskManager


def test_kill_switch():
    """Test the kill switch functionality"""
    
    print("\n" + "="*60)
    print("🔧 TESTING KILL SWITCH FUNCTIONALITY")
    print("="*60)
    
    # Initialize components
    config_loader = ConfigLoader()
    supabase = SupabaseClient()
    risk_manager = RiskManager(supabase, config_loader)
    
    # Get current config
    config = config_loader.load()
    current_state = config.get('global_settings', {}).get('trading_enabled', True)
    
    print(f"\n📊 Current State:")
    print(f"   Trading enabled in config: {current_state}")
    
    # Check Freqtrade config
    freqtrade_config_path = Path("freqtrade/config/config.json")
    if freqtrade_config_path.exists():
        with open(freqtrade_config_path, 'r') as f:
            ft_config = json.load(f)
            print(f"   Freqtrade max_open_trades: {ft_config.get('max_open_trades', 'N/A')}")
    else:
        print("   ⚠️ Freqtrade config not found locally")
    
    print("\n1️⃣ Testing Kill Switch OFF (disable trading)...")
    
    # Update config to disable trading
    result = config_loader.update_config(
        updates={'global_settings.trading_enabled': False},
        change_type='test',
        changed_by='test_script',
        description='Testing kill switch OFF'
    )
    
    if result['success']:
        print("   ✅ Config updated to disable trading")
        
        # Reload and check kill switch
        risk_manager.reload_config()
        
        # Check if Freqtrade config was updated
        time.sleep(1)  # Give it a moment to update
        
        if freqtrade_config_path.exists():
            with open(freqtrade_config_path, 'r') as f:
                ft_config = json.load(f)
                max_trades = ft_config.get('max_open_trades', 'N/A')
                if max_trades == 0:
                    print(f"   ✅ Freqtrade max_open_trades set to 0 (trading disabled)")
                else:
                    print(f"   ❌ Freqtrade max_open_trades is {max_trades} (expected 0)")
    else:
        print(f"   ❌ Failed to update config: {result.get('errors')}")
    
    print("\n2️⃣ Testing Kill Switch ON (enable trading)...")
    
    # Update config to enable trading
    result = config_loader.update_config(
        updates={'global_settings.trading_enabled': True},
        change_type='test',
        changed_by='test_script',
        description='Testing kill switch ON'
    )
    
    if result['success']:
        print("   ✅ Config updated to enable trading")
        
        # Reload and check kill switch
        risk_manager.reload_config()
        
        # Check if Freqtrade config was updated
        time.sleep(1)  # Give it a moment to update
        
        if freqtrade_config_path.exists():
            with open(freqtrade_config_path, 'r') as f:
                ft_config = json.load(f)
                max_trades = ft_config.get('max_open_trades', 'N/A')
                expected_max = config.get('position_management', {}).get('max_positions_total', 10)
                if max_trades == expected_max:
                    print(f"   ✅ Freqtrade max_open_trades set to {expected_max} (from admin panel)")
                else:
                    print(f"   ❌ Freqtrade max_open_trades is {max_trades} (expected {expected_max})")
    else:
        print(f"   ❌ Failed to update config: {result.get('errors')}")
    
    # Restore original state
    print(f"\n3️⃣ Restoring original state (trading_enabled: {current_state})...")
    result = config_loader.update_config(
        updates={'global_settings.trading_enabled': current_state},
        change_type='test',
        changed_by='test_script',
        description='Restoring original state'
    )
    
    if result['success']:
        print(f"   ✅ Restored to original state")
        risk_manager.reload_config()
    else:
        print(f"   ❌ Failed to restore: {result.get('errors')}")
    
    # Show current max positions setting
    config = config_loader.load()
    max_positions = config.get('position_management', {}).get('max_positions_total', 10)
    
    print("\n" + "="*60)
    print("✅ Kill switch test complete!")
    print("\n💡 Notes:")
    print("   • Kill switch updates Freqtrade's max_open_trades")
    print("   • 0 = trading disabled (no new trades)")
    print(f"   • {max_positions} = trading enabled (value from admin panel)")
    print("   • Risk Manager checks config every 5 minutes in production")
    print("   • Changes from admin panel will be picked up automatically")
    print("   • Max positions value comes from Position Management settings")
    print("="*60 + "\n")


if __name__ == "__main__":
    test_kill_switch()
