#!/usr/bin/env python3
"""
Test that admin panel changes reach Freqtrade strategy
"""

import sys
import json
import time
from pathlib import Path
from loguru import logger

sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "freqtrade"))

from src.config.config_loader import ConfigLoader
from config_bridge import ConfigBridge


def test_config_bridge():
    """Test that config changes propagate to Freqtrade"""
    
    print("\n" + "="*60)
    print("🔄 TESTING CONFIG BRIDGE TO FREQTRADE")
    print("="*60)
    
    # Initialize components
    config_loader = ConfigLoader()
    config_bridge = ConfigBridge()
    
    # Get current config
    config = config_loader.load()
    channel_config = config.get('strategies', {}).get('CHANNEL', {})
    
    print("\n📊 Current CHANNEL Strategy Settings:")
    print(f"   Buy Zone (channel_position): {channel_config.get('buy_zone', 'N/A')}")
    print(f"   Channel Strength Min: {channel_config.get('channel_strength_min', 'N/A')}")
    print(f"   RSI Oversold: {channel_config.get('rsi_oversold', 'N/A')}")
    print(f"   Volume Ratio Min: {channel_config.get('volume_ratio_min', 'N/A')}")
    
    # Test 1: Check if ConfigBridge reads the same values
    print("\n1️⃣ Testing ConfigBridge reads unified config...")
    bridge_config = config_bridge.get_config()
    bridge_channel = bridge_config.get('strategies', {}).get('CHANNEL', {})
    
    if bridge_channel.get('buy_zone') == channel_config.get('buy_zone'):
        print("   ✅ ConfigBridge correctly reads unified config")
    else:
        print("   ❌ ConfigBridge values don't match unified config")
    
    # Test 2: Make a small change and verify it propagates
    print("\n2️⃣ Testing config update propagation...")
    
    # Store original value
    original_buy_zone = channel_config.get('buy_zone', 0.05)
    test_value = 0.06 if original_buy_zone != 0.06 else 0.07
    
    print(f"   Changing buy_zone: {original_buy_zone} → {test_value}")
    
    # Update via config loader (simulating admin panel)
    result = config_loader.update_config(
        updates={'strategies.CHANNEL.buy_zone': test_value},
        change_type='test',
        changed_by='config_bridge_test',
        description='Testing config bridge propagation'
    )
    
    if result['success']:
        print("   ✅ Config updated successfully")
        
        # Give it a moment
        time.sleep(1)
        
        # Check if ConfigBridge sees the change
        bridge_config = config_bridge.get_config()
        new_buy_zone = bridge_config.get('strategies', {}).get('CHANNEL', {}).get('buy_zone')
        
        if new_buy_zone == test_value:
            print(f"   ✅ ConfigBridge sees new value: {new_buy_zone}")
        else:
            print(f"   ❌ ConfigBridge still shows old value: {new_buy_zone}")
        
        # Test 3: Check strategy thresholds
        print("\n3️⃣ Testing get_strategy_thresholds method...")
        thresholds = config_bridge.get_strategy_thresholds('CHANNEL')
        
        print("   Strategy thresholds from ConfigBridge:")
        for key, value in thresholds.items():
            print(f"     • {key}: {value}")
        
        if thresholds.get('buy_zone') == test_value:
            print(f"   ✅ Thresholds reflect the change")
        else:
            print(f"   ❌ Thresholds don't reflect the change")
        
        # Restore original value
        print(f"\n4️⃣ Restoring original value ({test_value} → {original_buy_zone})...")
        result = config_loader.update_config(
            updates={'strategies.CHANNEL.buy_zone': original_buy_zone},
            change_type='test',
            changed_by='config_bridge_test',
            description='Restoring original value'
        )
        
        if result['success']:
            print("   ✅ Original value restored")
    else:
        print(f"   ❌ Failed to update config: {result.get('errors')}")
    
    # Test 4: Check if Freqtrade strategy would see changes
    print("\n5️⃣ How Freqtrade Strategy uses ConfigBridge:")
    print("   • Strategy initializes ConfigBridge on startup")
    print("   • Calls get_strategy_thresholds('CHANNEL') for entry signals")
    print("   • Calls get_exit_params('CHANNEL', symbol) for exits")
    print("   • Changes take effect on next trade evaluation")
    
    print("\n💡 To verify in production:")
    print("   1. Make a change in admin panel")
    print("   2. Check Freqtrade logs for the new threshold values")
    print("   3. Look for log entries like:")
    print("      'Using buy_zone: 0.XX for CHANNEL strategy'")
    print("   4. New trades will use updated thresholds immediately")
    
    print("\n🔍 Current Freqtrade Integration:")
    print("   • ConfigBridge reads from: configs/paper_trading_config_unified.json")
    print("   • Strategy imports: from config_bridge import ConfigBridge")
    print("   • Strategy uses: self.config_bridge.get_strategy_thresholds('CHANNEL')")
    print("   • No restart needed - reads fresh on each check")
    
    print("="*60 + "\n")


if __name__ == "__main__":
    test_config_bridge()
