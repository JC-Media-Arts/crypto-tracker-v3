#!/usr/bin/env python3
"""
Freqtrade-Supabase Bridge
This script acts as a bridge between Freqtrade and Supabase data
It downloads data from Supabase and saves it in Freqtrade's expected format
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
import logging
from typing import List, Dict

# Load environment variables from .env file if it exists
from dotenv import load_dotenv
load_dotenv()

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))
from data.supabase_dataprovider import SupabaseDataProvider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FreqtradeSupabaseBridge:
    """
    Bridge to sync Supabase data to Freqtrade format
    """
    
    def __init__(self):
        """Initialize the bridge"""
        self.supabase = SupabaseDataProvider()
        self.data_dir = Path(__file__).parent.parent / "user_data" / "data" / "kraken"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
    def sync_pair(self, pair: str, timeframe: str = "5m", days: int = 30) -> bool:
        """
        Sync data for a single pair from Supabase to Freqtrade format
        
        Args:
            pair: Trading pair (e.g., "BTC/USDT")
            timeframe: Timeframe to sync
            days: Number of days of history to fetch
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Calculate candle count based on timeframe and days
            timeframe_minutes = {
                '1m': 1,
                '5m': 5,
                '15m': 15,
                '30m': 30,
                '1h': 60,
                '4h': 240,
                '1d': 1440
            }
            
            minutes_per_candle = timeframe_minutes.get(timeframe, 5)
            candles_needed = (days * 24 * 60) // minutes_per_candle
            
            logger.info(f"Fetching {candles_needed} candles for {pair} {timeframe}")
            
            # Fetch data from Supabase
            df = self.supabase.get_pair_dataframe(
                pair=pair,
                timeframe=timeframe,
                candle_count=candles_needed
            )
            
            if df.empty:
                logger.warning(f"No data available for {pair}")
                return False
                
            # Convert to Freqtrade JSON format
            # Freqtrade expects: [[timestamp, open, high, low, close, volume], ...]
            data = []
            for idx, row in df.iterrows():
                timestamp = int(idx.timestamp() * 1000)  # Convert to milliseconds
                data.append([
                    timestamp,
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    float(row['volume'])
                ])
            
            # Sort by timestamp
            data.sort(key=lambda x: x[0])
            
            # Save to JSON file in Freqtrade format
            # Format: SYMBOL_QUOTE-TIMEFRAME.json (e.g., BTC_USDT-5m.json)
            symbol = pair.replace("/", "_")
            filename = f"{symbol}-{timeframe}.json"
            filepath = self.data_dir / filename
            
            with open(filepath, 'w') as f:
                json.dump(data, f)
                
            logger.info(f"✅ Saved {len(data)} candles to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error syncing {pair}: {e}")
            return False
            
    def sync_all_pairs(self, pairs: List[str] = None, timeframe: str = "5m", days: int = 30):
        """
        Sync multiple pairs from Supabase to Freqtrade format
        
        Args:
            pairs: List of pairs to sync (None = all available)
            timeframe: Timeframe to sync
            days: Number of days of history
        """
        if pairs is None:
            # Get all available pairs
            pairs = self.supabase.get_available_pairs()
            
        logger.info(f"Starting sync for {len(pairs)} pairs")
        
        success_count = 0
        for pair in pairs:
            if self.sync_pair(pair, timeframe, days):
                success_count += 1
                
        logger.info(f"✅ Successfully synced {success_count}/{len(pairs)} pairs")
        
    def continuous_sync(self, pairs: List[str] = None, timeframe: str = "5m", interval_minutes: int = 5):
        """
        Continuously sync data at regular intervals
        
        Args:
            pairs: List of pairs to sync
            timeframe: Timeframe to sync
            interval_minutes: How often to sync (in minutes)
        """
        import time
        
        logger.info(f"Starting continuous sync every {interval_minutes} minutes")
        
        while True:
            try:
                # Sync recent data (last 2 days for efficiency)
                self.sync_all_pairs(pairs, timeframe, days=2)
                
                # Wait for next sync
                logger.info(f"Sleeping for {interval_minutes} minutes...")
                time.sleep(interval_minutes * 60)
                
            except KeyboardInterrupt:
                logger.info("Continuous sync stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in continuous sync: {e}")
                time.sleep(60)  # Wait 1 minute on error


def main():
    """Main function to sync data"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Sync Supabase data to Freqtrade format")
    parser.add_argument('--pairs', nargs='+', help='Pairs to sync (e.g., BTC/USDT ETH/USDT)')
    parser.add_argument('--timeframe', default='5m', help='Timeframe (default: 5m)')
    parser.add_argument('--days', type=int, default=30, help='Days of history (default: 30)')
    parser.add_argument('--continuous', action='store_true', help='Run continuous sync')
    parser.add_argument('--interval', type=int, default=5, help='Sync interval in minutes (default: 5)')
    
    args = parser.parse_args()
    
    # Initialize bridge
    bridge = FreqtradeSupabaseBridge()
    
    # Default pairs if none specified
    if not args.pairs:
        args.pairs = [
            "BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD",
            "ADA/USD", "AVAX/USD", "DOGE/USD", "DOT/USD",
            "LINK/USD", "ATOM/USD", "ALGO/USD", "MANA/USD"
        ]
    
    if args.continuous:
        # Run continuous sync
        bridge.continuous_sync(args.pairs, args.timeframe, args.interval)
    else:
        # Run one-time sync
        bridge.sync_all_pairs(args.pairs, args.timeframe, args.days)


if __name__ == "__main__":
    main()
