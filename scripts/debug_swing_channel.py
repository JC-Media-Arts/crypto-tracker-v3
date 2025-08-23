#!/usr/bin/env python3
"""
Debug why SWING and CHANNEL strategies aren't scanning
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pandas as pd
from loguru import logger

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from src.data.hybrid_fetcher import HybridDataFetcher
from src.strategies.swing.detector import SwingDetector
from src.strategies.channel.detector import ChannelDetector


async def debug_strategies():
    """Deep dive into why SWING and CHANNEL aren't working"""
    
    print("=" * 60)
    print("🔍 SWING & CHANNEL STRATEGY DEBUGGING")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)
    
    # Initialize components
    supabase = SupabaseClient()
    data_fetcher = HybridDataFetcher()
    
    # Test with BTC as it should have plenty of data
    test_symbol = "BTC"
    
    print(f"\n📊 Testing with symbol: {test_symbol}")
    print("-" * 40)
    
    # ============================================
    # PART 1: Test SWING Strategy
    # ============================================
    print("\n1. TESTING SWING STRATEGY:")
    print("-" * 40)
    
    try:
        # Initialize SwingDetector
        swing_detector = SwingDetector(supabase)
        print("✅ SwingDetector initialized successfully")
        
        # Check what methods it has
        methods = [m for m in dir(swing_detector) if not m.startswith('_')]
        print(f"   Available methods: {', '.join(methods[:5])}...")
        
        # Try the detect_setups method (async)
        print("\n   Testing detect_setups method...")
        setups = await swing_detector.detect_setups([test_symbol])
        
        if setups:
            print(f"   ✅ SWING found {len(setups)} setups!")
            for setup in setups:
                print(f"      Symbol: {setup.get('symbol')}, Score: {setup.get('score')}")
        else:
            print("   ⚠️  No SWING setups detected")
            
            # Let's check if it's getting data
            print("\n   Checking data availability for SWING...")
            
            # Try to fetch data manually
            ohlc_data = await swing_detector._fetch_ohlc_data(test_symbol)
            if ohlc_data:
                print(f"   ✅ Found {len(ohlc_data)} OHLC records")
                
                # Convert to DataFrame to check data quality
                df = pd.DataFrame(ohlc_data)
                if not df.empty:
                    print(f"   Data range: {df['timestamp'].min()} to {df['timestamp'].max()}")
                    print(f"   Columns: {df.columns.tolist()}")
                    
                    # Check if data meets SWING requirements
                    if len(df) < 20:
                        print(f"   ❌ Insufficient data: {len(df)} rows (need 20+)")
                    else:
                        print(f"   ✅ Sufficient data: {len(df)} rows")
                        
                    # Check volume
                    avg_volume = df['volume'].mean() if 'volume' in df else 0
                    print(f"   Average volume: {avg_volume:,.0f}")
                    
                    # Try detect_setup directly with data
                    print("\n   Testing detect_setup with manual data...")
                    setup = swing_detector.detect_setup(test_symbol, ohlc_data)
                    if setup:
                        print(f"   ✅ Manual detection worked: {setup}")
                    else:
                        print("   ❌ Manual detection returned None")
            else:
                print("   ❌ No OHLC data found for SWING")
                
    except Exception as e:
        print(f"   ❌ SWING Error: {e}")
        logger.exception("SWING detection failed")
    
    # ============================================
    # PART 2: Test CHANNEL Strategy
    # ============================================
    print("\n2. TESTING CHANNEL STRATEGY:")
    print("-" * 40)
    
    try:
        # Initialize ChannelDetector
        channel_detector = ChannelDetector()
        print("✅ ChannelDetector initialized successfully")
        
        # Check configuration
        print(f"   Config: min_points={channel_detector.min_points}, "
              f"lookback={channel_detector.lookback_periods}")
        
        # Get data for CHANNEL
        print("\n   Fetching data for CHANNEL...")
        ohlc_data = await data_fetcher.get_recent_data(
            symbol=test_symbol,
            hours=24,
            timeframe="15m"
        )
        
        if ohlc_data:
            print(f"   ✅ Found {len(ohlc_data)} records for CHANNEL")
            
            # Check data structure
            if ohlc_data:
                sample = ohlc_data[0]
                print(f"   Data structure: {list(sample.keys())}")
                
                # Try channel detection
                print("\n   Testing detect_channel method...")
                channel = channel_detector.detect_channel(test_symbol, ohlc_data)
                
                if channel:
                    print(f"   ✅ Channel detected!")
                    print(f"      Valid: {channel.is_valid()}")
                    print(f"      Type: {channel.channel_type()}")
                    print(f"      Width: {channel.width:.4f}")
                    print(f"      Touches: {channel.touches}")
                    
                    # Try to get trading signal
                    signal = channel_detector.get_trading_signal(channel)
                    if signal:
                        print(f"   ✅ Trading signal: {signal}")
                    else:
                        print("   ⚠️  No trading signal from channel")
                else:
                    print("   ❌ No channel detected")
                    
                    # Debug why no channel
                    df = pd.DataFrame(ohlc_data)
                    if len(df) < channel_detector.min_points:
                        print(f"   Issue: Insufficient data points ({len(df)} < {channel_detector.min_points})")
                    
                    # Check price variance
                    if 'close' in df:
                        price_range = (df['close'].max() - df['close'].min()) / df['close'].mean()
                        print(f"   Price range: {price_range:.2%}")
                        if price_range < 0.02:
                            print("   Issue: Price range too narrow for channel detection")
        else:
            print("   ❌ No data returned for CHANNEL")
            
    except Exception as e:
        print(f"   ❌ CHANNEL Error: {e}")
        logger.exception("CHANNEL detection failed")
    
    # ============================================
    # PART 3: Check Historical Scan Attempts
    # ============================================
    print("\n3. CHECKING SCAN HISTORY:")
    print("-" * 40)
    
    try:
        # Check if SWING/CHANNEL ever worked
        for strategy in ["SWING", "CHANNEL"]:
            result = supabase.client.table("scan_history") \
                .select("*", count="exact") \
                .eq("strategy_name", strategy) \
                .execute()
            
            count = result.count if result else 0
            print(f"   {strategy}: {count} total scans in history")
            
            if count == 0:
                # Check shadow_testing_scans as backup
                try:
                    shadow_result = supabase.client.table("shadow_testing_scans") \
                        .select("*", count="exact") \
                        .eq("strategy_name", strategy) \
                        .execute()
                    
                    shadow_count = shadow_result.count if shadow_result else 0
                    print(f"   {strategy}: {shadow_count} scans in shadow_testing")
                except:
                    pass
                    
    except Exception as e:
        print(f"   Error checking history: {e}")
    
    # ============================================
    # PART 4: Test with Multiple Symbols
    # ============================================
    print("\n4. TESTING WITH MULTIPLE SYMBOLS:")
    print("-" * 40)
    
    test_symbols = ["BTC", "ETH", "SOL"]
    
    for symbol in test_symbols:
        print(f"\n   Testing {symbol}:")
        
        # Quick data check
        try:
            ohlc_data = await data_fetcher.get_recent_data(
                symbol=symbol,
                hours=24,
                timeframe="15m"
            )
            
            if ohlc_data:
                df = pd.DataFrame(ohlc_data)
                volume = df['volume'].sum() if 'volume' in df else 0
                print(f"      Data points: {len(ohlc_data)}, Total volume: {volume:,.0f}")
                
                # Quick SWING test
                swing = SwingDetector(supabase)
                setup = swing.detect_setup(symbol, ohlc_data)
                swing_result = "✅ Setup found" if setup else "❌ No setup"
                
                # Quick CHANNEL test
                channel = channel_detector.detect_channel(symbol, ohlc_data)
                channel_result = "✅ Channel found" if channel else "❌ No channel"
                
                print(f"      SWING: {swing_result}, CHANNEL: {channel_result}")
            else:
                print(f"      ❌ No data available")
                
        except Exception as e:
            print(f"      Error: {str(e)[:50]}")
    
    # ============================================
    # PART 5: Recommendations
    # ============================================
    print("\n" + "=" * 60)
    print("📝 DEBUGGING SUMMARY & RECOMMENDATIONS:")
    print("=" * 60)
    
    print("\nLikely issues:")
    print("1. Volume thresholds might be too high")
    print("2. Data timeframe mismatch (strategies might expect different timeframes)")
    print("3. Insufficient historical data for pattern detection")
    print("4. Strategy parameters too strict")
    
    print("\nSuggested fixes:")
    print("1. Lower volume thresholds in strategy configuration")
    print("2. Ensure sufficient historical data (at least 100 bars)")
    print("3. Check that strategies are using correct timeframe (15m)")
    print("4. Loosen detection parameters")


if __name__ == "__main__":
    asyncio.run(debug_strategies())
