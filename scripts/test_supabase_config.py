#!/usr/bin/env python3
"""
Test script for Supabase configuration integration.
Tests the full flow: ConfigLoader -> Supabase -> config_bridge
"""

import sys
import os
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.config_loader import ConfigLoader
from freqtrade.user_data.config_bridge import ConfigBridge
from dotenv import load_dotenv
from loguru import logger
from supabase import create_client

# Load environment variables
load_dotenv()


def test_supabase_connection():
    """Test basic Supabase connection."""
    print("\n" + "="*60)
    print("1. Testing Supabase Connection")
    print("="*60)
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ SUPABASE_URL or SUPABASE_KEY not found in environment")
        print("   Please ensure .env file contains these variables")
        return False
    
    print(f"✅ Found Supabase credentials")
    print(f"   URL: {supabase_url[:30]}...")
    
    try:
        client = create_client(supabase_url, supabase_key)
        # Test with a simple query
        response = client.table("trading_config").select("config_key").limit(1).execute()
        print(f"✅ Successfully connected to Supabase")
        return True
    except Exception as e:
        print(f"❌ Failed to connect to Supabase: {e}")
        return False


def test_config_loader():
    """Test ConfigLoader with Supabase integration."""
    print("\n" + "="*60)
    print("2. Testing ConfigLoader")
    print("="*60)
    
    try:
        # Initialize ConfigLoader
        config_loader = ConfigLoader()
        
        # Load configuration
        config = config_loader.load()
        
        if config:
            print(f"✅ ConfigLoader loaded configuration")
            print(f"   Version: {config.get('version', 'unknown')}")
            print(f"   Last Updated: {config.get('last_updated', 'unknown')}")
            
            # Test getting specific values
            channel_enabled = config_loader.get("strategies.CHANNEL.enabled")
            print(f"   CHANNEL Strategy Enabled: {channel_enabled}")
            
            # Get channel thresholds
            buy_zone = config_loader.get("strategies.CHANNEL.detection_thresholds.buy_zone")
            sell_zone = config_loader.get("strategies.CHANNEL.detection_thresholds.sell_zone")
            print(f"   CHANNEL Buy Zone: {buy_zone}")
            print(f"   CHANNEL Sell Zone: {sell_zone}")
            
            return True
        else:
            print("❌ ConfigLoader failed to load configuration")
            return False
            
    except Exception as e:
        print(f"❌ ConfigLoader error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_save_to_supabase():
    """Test saving configuration to Supabase."""
    print("\n" + "="*60)
    print("3. Testing Save to Supabase")
    print("="*60)
    
    try:
        config_loader = ConfigLoader()
        
        # Load current config
        config = config_loader.load()
        
        # Make a small test change
        original_buy_zone = config["strategies"]["CHANNEL"]["detection_thresholds"]["buy_zone"]
        test_value = 0.05 if original_buy_zone != 0.05 else 0.03
        
        config["strategies"]["CHANNEL"]["detection_thresholds"]["buy_zone"] = test_value
        
        # Save to Supabase
        success = config_loader.save(config)
        
        if success:
            print(f"✅ Successfully saved config to Supabase")
            print(f"   Changed buy_zone from {original_buy_zone} to {test_value}")
            
            # Reload and verify
            config_loader_new = ConfigLoader()
            new_config = config_loader_new.load(force_reload=True)
            new_buy_zone = new_config["strategies"]["CHANNEL"]["detection_thresholds"]["buy_zone"]
            
            if new_buy_zone == test_value:
                print(f"✅ Verified: Config change persisted (buy_zone = {new_buy_zone})")
                
                # Restore original value
                config["strategies"]["CHANNEL"]["detection_thresholds"]["buy_zone"] = original_buy_zone
                config_loader.save(config)
                print(f"✅ Restored original value: {original_buy_zone}")
                return True
            else:
                print(f"❌ Config change did not persist (expected {test_value}, got {new_buy_zone})")
                return False
        else:
            print("❌ Failed to save config to Supabase")
            return False
            
    except Exception as e:
        print(f"❌ Save test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_bridge():
    """Test ConfigBridge (Freqtrade component) with Supabase."""
    print("\n" + "="*60)
    print("4. Testing ConfigBridge (Freqtrade)")
    print("="*60)
    
    try:
        # Initialize ConfigBridge
        bridge = ConfigBridge()
        
        # Get configuration
        config = bridge.get_config()
        
        if config:
            print(f"✅ ConfigBridge loaded configuration")
            print(f"   Version: {config.get('version', 'unknown')}")
            
            # Test getting channel thresholds
            thresholds = bridge.get_channel_thresholds()
            print(f"   Entry Threshold: {thresholds.get('entry_threshold')}")
            print(f"   Exit Threshold: {thresholds.get('exit_threshold')}")
            
            # Test getting symbols whitelist
            symbols = bridge.get_symbols_whitelist()
            print(f"   Number of symbols: {len(symbols)}")
            print(f"   First 3 symbols: {symbols[:3] if symbols else 'None'}")
            
            return True
        else:
            print("❌ ConfigBridge failed to load configuration")
            return False
            
    except Exception as e:
        print(f"❌ ConfigBridge error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_real_time_updates():
    """Test that config changes propagate in real-time."""
    print("\n" + "="*60)
    print("5. Testing Real-Time Updates")
    print("="*60)
    
    try:
        # Initialize components
        config_loader = ConfigLoader()
        bridge = ConfigBridge()
        
        # Get initial values
        config = config_loader.load()
        original_buy_zone = config["strategies"]["CHANNEL"]["detection_thresholds"]["buy_zone"]
        
        # Make a change via ConfigLoader
        test_value = 0.07 if original_buy_zone != 0.07 else 0.04
        config["strategies"]["CHANNEL"]["detection_thresholds"]["buy_zone"] = test_value
        config_loader.save(config)
        
        print(f"✅ Changed buy_zone to {test_value} via ConfigLoader")
        
        # Check if ConfigBridge sees the change (force reload by clearing cache)
        bridge._last_loaded = None  # Clear cache to force reload
        bridge_config = bridge.get_config()
        bridge_buy_zone = bridge_config["strategies"]["CHANNEL"]["detection_thresholds"]["buy_zone"]
        
        if bridge_buy_zone == test_value:
            print(f"✅ ConfigBridge sees updated value: {bridge_buy_zone}")
            
            # Restore original
            config["strategies"]["CHANNEL"]["detection_thresholds"]["buy_zone"] = original_buy_zone
            config_loader.save(config)
            print(f"✅ Restored original value: {original_buy_zone}")
            
            return True
        else:
            print(f"❌ ConfigBridge did not see update (expected {test_value}, got {bridge_buy_zone})")
            
            # Restore original
            config["strategies"]["CHANNEL"]["detection_thresholds"]["buy_zone"] = original_buy_zone
            config_loader.save(config)
            
            return False
            
    except Exception as e:
        print(f"❌ Real-time update test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("SUPABASE CONFIGURATION INTEGRATION TEST")
    print("="*60)
    
    tests = [
        ("Supabase Connection", test_supabase_connection),
        ("ConfigLoader", test_config_loader),
        ("Save to Supabase", test_save_to_supabase),
        ("ConfigBridge", test_config_bridge),
        ("Real-Time Updates", test_real_time_updates),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Test '{name}' failed with exception: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ ALL TESTS PASSED - Ready for deployment!")
        print("\nNext steps:")
        print("1. Run the migration to create the trading_config table:")
        print("   psql $DATABASE_URL < migrations/031_create_trading_config.sql")
        print("\n2. Deploy to Railway and verify:")
        print("   - Freqtrade service can read config")
        print("   - Admin UI changes propagate to Freqtrade")
    else:
        print("❌ SOME TESTS FAILED - Please fix issues before deployment")
        print("\nCommon issues:")
        print("1. Missing SUPABASE_URL or SUPABASE_KEY in .env")
        print("2. Table 'trading_config' not created (run migration)")
        print("3. Network/firewall blocking Supabase connection")
    
    print("="*60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
