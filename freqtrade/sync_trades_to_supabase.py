#!/usr/bin/env python3
"""
Sync Freqtrade SQLite trades to Supabase freqtrade_trades table
This is a backup solution if PostgreSQL connection fails
"""

import os
import sys
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from supabase import create_client, Client

# Get Supabase credentials from environment
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ SUPABASE_URL and SUPABASE_KEY must be set in environment")
    sys.exit(1)

# Create Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def sync_trades():
    """Sync trades from SQLite to Supabase"""
    
    # Connect to SQLite
    db_path = Path(__file__).parent / "tradesv3.dryrun.sqlite"
    if not db_path.exists():
        print(f"❌ SQLite database not found: {db_path}")
        return
        
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    cursor = conn.cursor()
    
    # Get essential trade columns that exist in SQLite
    cursor.execute("""
        SELECT 
            id, pair, is_open, open_rate, close_rate,
            close_profit_abs, stake_amount, amount,
            open_date, close_date, stop_loss,
            exit_reason, strategy, timeframe
        FROM trades
    """)
    
    trades = cursor.fetchall()
    
    # Supabase client already created globally
    
    print(f"📊 Found {len(trades)} trades in SQLite")
    
    synced_count = 0
    for trade in trades:
        trade_dict = dict(trade)
        
        # Convert datetime strings to ISO format if needed
        for date_field in ['open_date', 'close_date']:
            if trade_dict.get(date_field):
                # Ensure it's in ISO format
                if not trade_dict[date_field].endswith('Z'):
                    trade_dict[date_field] = trade_dict[date_field].replace(' ', 'T')
                    if '+' not in trade_dict[date_field]:
                        trade_dict[date_field] += 'Z'
        
        # Check if trade already exists in Supabase
        existing = supabase.table("freqtrade_trades").select("id").eq("id", trade_dict['id']).execute()
        
        if existing.data:
            # Update existing trade
            response = supabase.table("freqtrade_trades").update(trade_dict).eq("id", trade_dict['id']).execute()
            print(f"✅ Updated trade {trade_dict['id']}: {trade_dict['pair']}")
        else:
            # Insert new trade
            response = supabase.table("freqtrade_trades").insert(trade_dict).execute()
            print(f"✅ Inserted trade {trade_dict['id']}: {trade_dict['pair']}")
        
        synced_count += 1
    
    conn.close()
    
    print(f"\n✅ Synced {synced_count} trades to Supabase")
    
    # Also sync to paper_trades table for backward compatibility
    print("\n📊 Syncing to paper_trades table for dashboard compatibility...")
    
    # Get trades again for paper_trades format
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            pair, open_rate, close_rate, amount, stake_amount,
            open_date, close_date, close_profit_abs, strategy,
            is_open, exit_reason
        FROM trades
        WHERE strategy = 'SimpleChannelStrategy'
    """)
    
    simple_trades = cursor.fetchall()
    
    for trade in simple_trades:
        # Convert to paper_trades format
        paper_trade = {
            'symbol': trade[0].replace('/USD', '').replace('/USDT', ''),
            'side': 'BUY' if trade[9] else 'SELL',  # is_open determines if it's still a BUY
            'price': trade[1] if trade[9] else trade[2],  # open_rate if open, close_rate if closed
            'amount': trade[3],
            'total': trade[4],
            'strategy_name': 'CHANNEL',  # Map SimpleChannelStrategy to CHANNEL
            'created_at': trade[5] if trade[9] else trade[6],  # open_date if open, close_date if closed
            'profit_loss': trade[7] if not trade[9] else 0,
            'trade_group_id': f"FT_{trade[5]}",  # Use open_date as unique ID
            'exit_reason': trade[10] if not trade[9] else None
        }
        
        # Check if we need to insert both BUY and SELL for closed trades
        if not trade[9]:  # Closed trade
            # Insert BUY record
            buy_trade = paper_trade.copy()
            buy_trade['side'] = 'BUY'
            buy_trade['price'] = trade[1]
            buy_trade['created_at'] = trade[5]
            buy_trade['profit_loss'] = 0
            
            # Insert SELL record
            sell_trade = paper_trade.copy()
            sell_trade['side'] = 'SELL'
            sell_trade['price'] = trade[2]
            sell_trade['created_at'] = trade[6]
            
            # Insert both
            supabase.table("paper_trades").upsert([buy_trade, sell_trade]).execute()
            print(f"✅ Synced closed trade pair: {trade[0]}")
        else:
            # Just insert the BUY for open trades
            supabase.table("paper_trades").upsert([paper_trade]).execute()
            print(f"✅ Synced open trade: {trade[0]}")
    
    conn.close()
    
    print("\n✅ Trade sync complete!")

if __name__ == "__main__":
    sync_trades()
