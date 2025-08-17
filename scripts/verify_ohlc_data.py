#!/usr/bin/env python3
"""Verify OHLC data in database."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient

s = SupabaseClient()

# Check daily data
daily = s.client.table('ohlc_data').select(
    'timestamp,open,high,low,close,volume'
).eq('symbol', 'BTC').eq('timeframe', '1d').order(
    'timestamp', desc=True
).limit(5).execute()

print('Latest 5 daily bars for BTC:')
for bar in daily.data:
    print(f"  {bar['timestamp'][:10]}: O={bar['open']:.0f} H={bar['high']:.0f} L={bar['low']:.0f} C={bar['close']:.0f}")

# Check hourly data  
hourly = s.client.table('ohlc_data').select(
    'timestamp,close'
).eq('symbol', 'BTC').eq('timeframe', '1h').order(
    'timestamp', desc=True
).limit(5).execute()

print('\nLatest 5 hourly bars for BTC:')
for bar in hourly.data:
    print(f"  {bar['timestamp'][:16]}: ${bar['close']:.0f}")

# Get counts
daily_count = s.client.table('ohlc_data').select(
    'timestamp', count='exact'
).eq('symbol', 'BTC').eq('timeframe', '1d').execute()

hourly_count = s.client.table('ohlc_data').select(
    'timestamp', count='exact'
).eq('symbol', 'BTC').eq('timeframe', '1h').execute()

print(f'\nTotal bars in database:')
print(f'  Daily: {len(daily_count.data)} bars')
print(f'  Hourly: {len(hourly_count.data)} bars')
print(f'  Total: {len(daily_count.data) + len(hourly_count.data)} bars')
