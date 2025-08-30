#!/usr/bin/env python3
"""
Test that Freqtrade sees admin panel config changes
"""

import sys
import json
import time
from pathlib import Path

# Add Freqtrade path
sys.path.append(str(Path(__file__).parent.parent / "freqtrade" / "user_data"))
sys.path.append(str(Path(__file__).parent.parent))

from config_bridge import ConfigBridge
from src.config.config_loader import ConfigLoader


def test_config_sync():
    """Test that admin panel changes reach Freqtrade"""
    
    print("\n" + "="*60)
    print("🔄 TESTING ADMIN PANEL → FREQTRADE CONFIG SYNC")
    print("="*60)
    
    # Initialize components
    config_loader = ConfigLoader()  # What admin panel uses
    config_bridge = ConfigBridge()  # What Freqtrade uses
    
    # 1. Show current values from admin panel
    admin_config = config_loader.load()
    channel_admin = admin_config.get('strategies', {}).get('CHANNEL', {})
    detection = channel_admin.get('detection_thresholds', {})
    
    print("\n📊 Current Values in Admin Panel (unified config):")
    print(f"   buy_zone: {detection.get('buy_zone', 'N/A')}")
    print(f"   channel_strength_min: {detection.get('channel_strength_min', 'N/A')}")
    print(f"   sell_zone: {detection.get('sell_zone', 'N/A')}")
    print(f"   volume_ratio_min: {detection.get('volume_ratio_min', 1.0)}")
    
    # 2. Show what Freqtrade sees
    print("\n🤖 What Freqtrade Strategy Sees (via ConfigBridge):")
    thresholds = config_bridge.get_channel_thresholds()
    print(f"   entry_threshold (buy_zone): {thresholds.get('entry_threshold', 'N/A')}")
    print(f"   channel_strength_min: {thresholds.get('channel_strength_min', 'N/A')}")
    print(f"   rsi_min (rsi_oversold): {thresholds.get('rsi_min', 'N/A')}")
    print(f"   volume_ratio_min: {thresholds.get('volume_ratio_min', 'N/A')}")
    
    # 3. Check if they match
    print("\n✅ Verification:")
    if detection.get('buy_zone') == thresholds.get('entry_threshold'):
        print("   ✅ buy_zone matches!")
    else:
        print(f"   ❌ buy_zone mismatch: {detection.get('buy_zone')} vs {thresholds.get('entry_threshold')}")
    
    if detection.get('channel_strength_min') == thresholds.get('channel_strength_min'):
        print("   ✅ channel_strength_min matches!")
    else:
        print(f"   ❌ channel_strength_min mismatch: {detection.get('channel_strength_min')} vs {thresholds.get('channel_strength_min')}")
    
    # 4. Test a change
    print("\n🔧 Testing Live Update:")
    original_buy_zone = detection.get('buy_zone', 0.03)
    test_value = 0.04 if original_buy_zone != 0.04 else 0.02
    
    print(f"   1. Changing buy_zone: {original_buy_zone} → {test_value}")
    
    # Make the change (simulating admin panel) - using correct path
    result = config_loader.update_config(
        updates={'strategies.CHANNEL.detection_thresholds.buy_zone': test_value},
        change_type='test',
        changed_by='freqtrade_config_test',
        description='Testing Freqtrade sees changes'
    )
    
    if result['success']:
        print("   2. Config updated in admin panel")
        
        # Check if Freqtrade sees it
        time.sleep(0.5)
        new_thresholds = config_bridge.get_channel_thresholds()
        new_entry = new_thresholds.get('entry_threshold')
        
        if new_entry == test_value:
            print(f"   3. ✅ Freqtrade sees new value: {new_entry}")
        else:
            print(f"   3. ❌ Freqtrade still shows: {new_entry} (expected {test_value})")
        
        # Restore original
        print(f"\n   4. Restoring original value: {original_buy_zone}")
        config_loader.update_config(
            updates={'strategies.CHANNEL.detection_thresholds.buy_zone': original_buy_zone},
            change_type='test',
            changed_by='freqtrade_config_test',
            description='Restoring original value'
        )
        print("   ✅ Original value restored")
    
    # 5. Show how it works in production
    print("\n💡 How It Works in Production:")
    print("   1. You change a value in the admin panel")
    print("   2. Admin panel updates configs/paper_trading_config_unified.json")
    print("   3. Freqtrade's ConfigBridge reads from the same file")
    print("   4. On next trade evaluation, strategy uses new values")
    print("   5. No restart needed - ConfigBridge reloads on each call")
    
    print("\n📝 Key Methods:")
    print("   • config_bridge.get_channel_thresholds() - Entry/exit thresholds")
    print("   • config_bridge.get_exit_params(symbol) - Stop loss, take profit")
    print("   • config_bridge.get_config() - Full config with position limits")
    
    print("="*60 + "\n")


if __name__ == "__main__":
    test_config_sync()
