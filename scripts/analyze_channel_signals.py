#!/usr/bin/env python3
"""Analyze why CHANNEL is triggering so many signals"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime, timezone, timedelta
from src.data.supabase_client import SupabaseClient
import pandas as pd

db = SupabaseClient()

# Get recent market data
symbols = ['STX', 'PEPE', 'MKR', 'FIL', 'WIF', 'EOS', 'VET']  # Recent positions

for symbol in symbols[:3]:  # Check first 3
    print(f"\n📊 {symbol} Analysis:")
    
    # Get recent strategy signals
    result = db.client.table('strategy_signals').select(
        'symbol, signal_type, confidence, parameters, created_at'
    ).eq('symbol', symbol).eq('signal_type', 'CHANNEL_BUY').gte(
        'created_at', (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    ).order('created_at', desc=True).limit(5).execute()
    
    if result.data:
        df = pd.DataFrame(result.data)
        print(f"  Recent signals: {len(df)}")
        
        if len(df) > 0:
            latest = df.iloc[0]
            params = latest.get('parameters', {})
            print(f"  Confidence: {latest.get('confidence', 0):.2f}")
            print(f"  Parameters: {params}")
            
            # Check position in channel
            if isinstance(params, dict):
                channel_pos = params.get('channel_position', 0)
                print(f"  Channel Position: {channel_pos:.2%}")
    
    # Get recent price action
    price_result = db.client.table('price_data').select(
        'price, timestamp'
    ).eq('symbol', symbol).order('timestamp', desc=True).limit(10).execute()
    
    if price_result.data:
        prices = pd.DataFrame(price_result.data)
        prices['price'] = pd.to_numeric(prices['price'])
        
        high = prices['price'].max()
        low = prices['price'].min()
        current = prices['price'].iloc[0]
        
        channel_width = (high - low) / low if low > 0 else 0
        position_in_channel = (current - low) / (high - low) if high > low else 0
        
        print(f"\n  Price Analysis (last 10 samples):")
        print(f"    Current: ${current:.6f}")
        print(f"    10-sample High: ${high:.6f}")
        print(f"    10-sample Low: ${low:.6f}")
        print(f"    Channel Width: {channel_width:.2%}")
        print(f"    Position in Channel: {position_in_channel:.2%}")
        print(f"    Buy Zone (< 5%): {'✅ YES' if position_in_channel < 0.05 else '❌ NO'}")
        
# Check config being used
print("\n⚙️ Current Config Check:")
config_result = db.client.table('paper_trades').select(
    'parameters'
).eq('strategy_name', 'CHANNEL').order('created_at', desc=True).limit(1).execute()

if config_result.data and config_result.data[0].get('parameters'):
    params = config_result.data[0]['parameters']
    print(f"  Parameters from latest trade: {params}")
