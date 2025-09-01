#!/usr/bin/env python3
"""
Test script to verify Supabase data integration with Freqtrade
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add user_data to path
sys.path.insert(0, str(Path(__file__).parent / "user_data"))

# Set up environment variables if not already set
from dotenv import load_dotenv
load_dotenv()

def test_supabase_connection():
    """Test basic Supabase connection"""
    print("\n🔍 Testing Supabase Connection...")
    
    from data.supabase_dataprovider import SupabaseDataProvider
    
    try:
        provider = SupabaseDataProvider()
        print("✅ Supabase connection successful")
        return provider
    except Exception as e:
        print(f"❌ Failed to connect to Supabase: {e}")
        return None

def test_data_fetch(provider):
    """Test fetching data for different pairs"""
    print("\n📊 Testing Data Fetch...")
    
    test_pairs = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    
    for pair in test_pairs:
        print(f"\n  Testing {pair}:")
        try:
            # Test 1h data
            df_1h = provider.get_pair_dataframe(pair, timeframe="1h", candle_count=100)
            if not df_1h.empty:
                print(f"    ✅ 1h data: {len(df_1h)} candles")
                print(f"       Latest: {df_1h.index[-1]}")
                print(f"       Close: ${df_1h['close'].iloc[-1]:,.2f}")
            else:
                print(f"    ⚠️ No 1h data available")
                
            # Test 5m data (if available)
            df_5m = provider.get_pair_dataframe(pair, timeframe="5m", candle_count=100)
            if not df_5m.empty:
                print(f"    ✅ 5m data: {len(df_5m)} candles")
            else:
                print(f"    ⚠️ No 5m data available")
                
        except Exception as e:
            print(f"    ❌ Error: {e}")

def test_custom_dataprovider():
    """Test the custom data provider for Freqtrade"""
    print("\n🔧 Testing Custom DataProvider...")
    
    from custom_dataprovider import CustomDataProvider
    
    # Mock config
    config = {
        'timeframe': '5m',
        'exchange': {
            'name': 'kraken',
            'pair_whitelist': ['BTC/USDT', 'ETH/USDT']
        }
    }
    
    try:
        provider = CustomDataProvider(config)
        print("✅ Custom DataProvider initialized")
        
        # Test getting OHLCV data
        df = provider.ohlcv("BTC/USDT", "5m")
        if not df.empty:
            print(f"✅ OHLCV data retrieved: {len(df)} candles")
            print(f"   Columns: {df.columns.tolist()}")
        else:
            print("⚠️ No OHLCV data available")
            
        # Test available pairs
        pairs = provider.available_pairs()
        print(f"📋 Available pairs: {len(pairs)}")
        if pairs:
            print(f"   First 5: {pairs[:5]}")
            
    except Exception as e:
        print(f"❌ Custom DataProvider error: {e}")
        import traceback
        traceback.print_exc()

def test_strategy_compatibility():
    """Test if the strategy can work with Supabase data"""
    print("\n🎯 Testing Strategy Compatibility...")
    
    from strategies.ChannelStrategyV1 import ChannelStrategyV1
    
    # Mock config
    config = {
        'timeframe': '5m',
        'strategy': 'ChannelStrategyV1',
        'exchange': {
            'name': 'kraken',
            'pair_whitelist': ['BTC/USDT']
        }
    }
    
    try:
        strategy = ChannelStrategyV1(config)
        print("✅ Strategy initialized successfully")
        
        # Test indicator population
        from custom_dataprovider import CustomDataProvider
        provider = CustomDataProvider(config)
        
        df = provider.ohlcv("BTC/USDT", "5m")
        if not df.empty:
            # Add required columns for testing
            metadata = {'pair': 'BTC/USDT'}
            
            # Populate indicators
            df_with_indicators = strategy.populate_indicators(df, metadata)
            print(f"✅ Indicators populated: {len(df_with_indicators.columns)} columns")
            
            # Check for required indicators
            required_indicators = ['bb_upper', 'bb_lower', 'bb_middle', 'rsi', 'channel_position']
            missing = [ind for ind in required_indicators if ind not in df_with_indicators.columns]
            
            if missing:
                print(f"⚠️ Missing indicators: {missing}")
            else:
                print("✅ All required indicators present")
                
            # Test entry signal generation
            df_with_signals = strategy.populate_entry_trend(df_with_indicators, metadata)
            entry_signals = df_with_signals['enter_long'].sum() if 'enter_long' in df_with_signals.columns else 0
            print(f"📈 Entry signals generated: {entry_signals}")
            
    except Exception as e:
        print(f"❌ Strategy compatibility error: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Run all tests"""
    print("=" * 60)
    print("🚀 FREQTRADE SUPABASE INTEGRATION TEST")
    print("=" * 60)
    
    # Check environment variables
    print("\n🔐 Environment Variables:")
    print(f"   SUPABASE_URL: {'✅ Set' if os.getenv('SUPABASE_URL') else '❌ Not set'}")
    print(f"   SUPABASE_KEY: {'✅ Set' if os.getenv('SUPABASE_KEY') else '❌ Not set'}")
    
    # Test Supabase connection
    provider = test_supabase_connection()
    
    if provider:
        # Test data fetching
        test_data_fetch(provider)
        
        # Test custom data provider
        test_custom_dataprovider()
        
        # Test strategy compatibility
        test_strategy_compatibility()
    
    print("\n" + "=" * 60)
    print("✅ TESTS COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
