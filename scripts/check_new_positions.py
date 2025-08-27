#!/usr/bin/env python3
"""Check new positions opened recently"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime, timezone, timedelta
from src.data.supabase_client import SupabaseClient
import pandas as pd

db = SupabaseClient()

# Get trades from last 2 hours
cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()

result = db.client.table('paper_trades').select(
    'trade_group_id, symbol, side, created_at, strategy_name, price'
).gte('created_at', cutoff).eq('side', 'BUY').eq('strategy_name', 'CHANNEL').order('created_at', desc=True).execute()

if result.data:
    df = pd.DataFrame(result.data)
    df['created_at'] = pd.to_datetime(df['created_at'])
    df['minutes_ago'] = (datetime.now(timezone.utc) - df['created_at']).dt.total_seconds() / 60
    
    print(f'CHANNEL positions opened in last 2 hours: {len(df)}')
    print(f'\nPositions by time:')
    print(f'  Last 10 min: {len(df[df["minutes_ago"] <= 10])}')
    print(f'  Last 30 min: {len(df[df["minutes_ago"] <= 30])}')
    print(f'  Last 60 min: {len(df[df["minutes_ago"] <= 60])}')
    
    # Show rate of opening
    if len(df) > 0:
        oldest = df['minutes_ago'].max()
        rate = len(df) / (oldest / 60)  # positions per hour
        print(f'\nOpening rate: {rate:.1f} positions/hour')
        
    # Show last 5
    print(f'\nLast 5 CHANNEL positions opened:')
    for _, row in df.head(5).iterrows():
        print(f'  {row["symbol"]}: {row["minutes_ago"]:.0f} min ago at ${row["price"]:.4f}')
        
    # Group by time buckets
    cleanup_time = datetime.now(timezone.utc) - timedelta(minutes=7)  # When cleanup ran
    before_cleanup = df[df['created_at'] < cleanup_time]
    after_cleanup = df[df['created_at'] >= cleanup_time]
    
    print(f'\n📊 Timeline:')
    print(f'  Before cleanup (7+ min ago): {len(before_cleanup)} positions')
    print(f'  After cleanup (last 7 min): {len(after_cleanup)} positions')
else:
    print("No new CHANNEL positions in last 2 hours")
