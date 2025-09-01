#!/usr/bin/env python3
"""
Test if simplified strategies would generate trading signals
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from supabase import create_client, Client
import pandas as pd

load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

def calculate_rsi(series, period=14):
    """Calculate RSI"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def test_simple_channel_signals():
    """Test SimpleChannelStrategy signals"""
    print("\n" + "="*60)
    print("TESTING SIMPLE CHANNEL STRATEGY SIGNALS")
    print("="*60)
    
    # Get recent OHLC data for a few pairs
    test_pairs = ['BTC', 'ETH', 'SOL', 'DOGE', 'PEPE']
    
    for symbol in test_pairs:
        # Get last 100 candles
        response = supabase.table('ohlc_data').select('*').eq('symbol', symbol).eq('timeframe', '1m').order('timestamp', desc=True).limit(100).execute()
        
        if not response.data:
            print(f"\n❌ No data for {symbol}")
            continue
            
        # Convert to DataFrame
        df = pd.DataFrame(response.data)
        df = df.sort_values('timestamp')
        
        # Calculate indicators
        df['bb_middle'] = df['close'].rolling(window=20).mean()
        df['bb_std'] = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * 2)
        df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * 2)
        
        # Channel position
        bb_width = df['bb_upper'] - df['bb_lower']
        df['channel_position'] = (df['close'] - df['bb_lower']) / bb_width
        df['channel_position'] = df['channel_position'].fillna(0.5).clip(0, 1)
        
        # RSI
        df['rsi'] = calculate_rsi(df['close'], 14)
        
        # Get latest values
        if len(df) > 0:
            latest = df.iloc[-1]
            
            print(f"\n{'='*40}")
            print(f"{symbol}/USD Analysis:")
            print(f"  Close: ${latest['close']:.4f}")
            print(f"  Channel Position: {latest['channel_position']:.3f}")
            print(f"  RSI: {latest['rsi']:.1f}")
            print(f"  Volume: {latest['volume']:.2f}")
            
            # Check SimpleChannelStrategy conditions (loosened)
            channel_entry = latest['channel_position'] <= 0.70  # Lower 70% of channel
            rsi_valid = 20 < latest['rsi'] < 80
            has_bb = latest['bb_upper'] > latest['bb_lower']
            
            would_buy_channel = channel_entry and rsi_valid and has_bb
            
            print(f"\n  SimpleChannelStrategy:")
            print(f"    Channel < 0.70? {channel_entry} ({latest['channel_position']:.3f})")
            print(f"    RSI 20-80? {rsi_valid} ({latest['rsi']:.1f})")
            print(f"    Valid BB? {has_bb}")
            print(f"    ✅ WOULD BUY: {would_buy_channel}" if would_buy_channel else f"    ❌ NO SIGNAL")
            
            # Check UltraSimpleRSI conditions
            would_buy_rsi = latest['rsi'] < 40
            
            print(f"\n  UltraSimpleRSI:")
            print(f"    RSI < 40? {would_buy_rsi} ({latest['rsi']:.1f})")
            print(f"    ✅ WOULD BUY" if would_buy_rsi else f"    ❌ NO SIGNAL")
            
            # Count how many recent candles would trigger
            recent_signals_channel = 0
            recent_signals_rsi = 0
            
            for i in range(max(0, len(df)-20), len(df)):
                row = df.iloc[i]
                if row['channel_position'] <= 0.70 and 20 < row['rsi'] < 80:
                    recent_signals_channel += 1
                if row['rsi'] < 40:
                    recent_signals_rsi += 1
            
            print(f"\n  Last 20 candles:")
            print(f"    SimpleChannel signals: {recent_signals_channel}/20")
            print(f"    UltraRSI signals: {recent_signals_rsi}/20")

def check_current_market_conditions():
    """Check overall market conditions"""
    print("\n" + "="*60)
    print("CURRENT MARKET CONDITIONS")
    print("="*60)
    
    # Get all symbols with recent data
    response = supabase.table('ohlc_data').select('symbol, close, volume').eq('timeframe', '1m').gte(
        'timestamp', 
        (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    ).execute()
    
    if response.data:
        df = pd.DataFrame(response.data)
        
        # Group by symbol and get latest
        latest_prices = df.groupby('symbol').last()
        
        print(f"\n✅ {len(latest_prices)} symbols with recent data")
        print(f"📊 Average volume: {latest_prices['volume'].mean():.2f}")
        print(f"📊 Symbols with volume > 0: {(latest_prices['volume'] > 0).sum()}")
        print(f"📊 Symbols with volume = 0: {(latest_prices['volume'] == 0).sum()}")
        
        # Show some with zero volume
        zero_volume = latest_prices[latest_prices['volume'] == 0].index.tolist()[:5]
        if zero_volume:
            print(f"\n⚠️ Examples with zero volume: {', '.join(zero_volume)}")

if __name__ == "__main__":
    print("\n🔍 STRATEGY SIGNAL TESTER")
    print("Testing if simplified strategies would generate trades...")
    
    test_simple_channel_signals()
    check_current_market_conditions()
    
    print("\n" + "="*60)
    print("RECOMMENDATIONS:")
    print("="*60)
    print("""
    1. If NO signals with SimpleChannelStrategy:
       - Further loosen channel_entry_threshold to 0.80 or 0.90
       - Widen RSI range to 15-85
    
    2. If NO signals with UltraSimpleRSI:
       - Increase RSI buy threshold to 45 or 50
       - This guarantees more frequent trades
    
    3. For symbols with zero volume:
       - These need data pipeline fixes
       - Temporarily focus on high-volume pairs only
    
    4. Start with UltraSimpleRSI for immediate trades
       Then gradually tighten thresholds as needed
    """)
