#!/usr/bin/env python3
"""
Freqtrade Trade Sync
Syncs trades from Freqtrade's SQLite database to Supabase for ML training
This runs inside the Freqtrade container on Railway
"""

import os
import sys
import sqlite3
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
import time
from loguru import logger
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class FreqtradeTradeSync:
    """Syncs Freqtrade trades to Supabase for ML training"""
    
    def __init__(self):
        # Initialize Supabase client
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        self.supabase: Client = create_client(url, key)
        
        # Freqtrade creates the database in the working directory, not in user_data
        self.db_path = Path("/freqtrade/tradesv3.dryrun.sqlite")
        self.sync_interval = 300  # 5 minutes
        
    def sync_trades(self):
        """Sync all trades from Freqtrade to Supabase"""
        
        if not self.db_path.exists():
            logger.error(f"Freqtrade database not found at {self.db_path}")
            return 0
            
        try:
            # Connect to Freqtrade SQLite
            conn = sqlite3.connect(self.db_path)
            
            # Get all trades
            query = """
            SELECT 
                id as trade_id,
                pair,
                is_open,
                amount,
                open_rate,
                close_rate,
                open_date,
                close_date,
                close_profit,
                close_profit_abs,
                sell_reason,
                strategy,
                timeframe,
                fee_open,
                fee_close,
                stop_loss,
                initial_stop_loss,
                trailing_stop
            FROM trades
            ORDER BY id
            """
            
            trades_df = pd.read_sql_query(query, conn)
            conn.close()
            
            if trades_df.empty:
                logger.info("No trades to sync")
                return 0
            
            # Extract symbol from pair (remove /USD or /USDT)
            trades_df['symbol'] = trades_df['pair'].str.replace('/USD', '').str.replace('/USDT', '')
            
            # Convert to records for upsert
            trades_records = trades_df.to_dict('records')
            
            # Sync to Supabase (upsert to handle updates)
            synced_count = 0
            batch_size = 50
            
            for i in range(0, len(trades_records), batch_size):
                batch = trades_records[i:i + batch_size]
                
                try:
                    # Upsert batch (insert or update based on trade_id)
                    result = self.supabase.table('freqtrade_trades')\
                        .upsert(batch, on_conflict='trade_id')\
                        .execute()
                    
                    synced_count += len(batch)
                    logger.info(f"Synced batch {i//batch_size + 1}: {len(batch)} trades")
                    
                except Exception as e:
                    logger.error(f"Error syncing batch: {e}")
                    
                # Small delay between batches
                time.sleep(0.5)
            
            logger.info(f"✅ Successfully synced {synced_count} trades to Supabase")
            return synced_count
            
        except Exception as e:
            logger.error(f"Error during trade sync: {e}")
            return 0
    
    def run_continuous_sync(self):
        """Run continuous sync every 5 minutes"""
        logger.info("Starting Freqtrade trade sync service...")
        
        while True:
            try:
                synced = self.sync_trades()
                logger.info(f"Sync complete: {synced} trades synced")
                
            except Exception as e:
                logger.error(f"Sync error: {e}")
            
            # Wait for next sync
            logger.info(f"Next sync in {self.sync_interval} seconds...")
            time.sleep(self.sync_interval)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Freqtrade Trade Sync")
    parser.add_argument(
        "--once", 
        action="store_true", 
        help="Run sync once and exit"
    )
    
    args = parser.parse_args()
    
    sync = FreqtradeTradeSync()
    
    if args.once:
        # Single sync
        synced = sync.sync_trades()
        print(f"Synced {synced} trades")
    else:
        # Continuous sync
        sync.run_continuous_sync()


if __name__ == "__main__":
    main()
