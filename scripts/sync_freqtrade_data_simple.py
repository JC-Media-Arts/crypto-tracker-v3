#!/usr/bin/env python3
"""
Simple sync script for OHLC data from Supabase to Freqtrade format.
Focuses on 1h data which we know exists in the database.
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def sync_freqtrade_data():
    """Sync OHLC data from Supabase to Freqtrade format."""
    
    # Initialize Supabase client
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        logger.error("SUPABASE_URL and SUPABASE_KEY must be set")
        return False
    
    client = create_client(supabase_url, supabase_key)
    
    # Freqtrade data directory
    data_dir = Path("/Users/justincoit/crypto-tracker-v3/freqtrade/user_data/data/kraken")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Pairs to sync (from config)
    pairs = [
        "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
        "ADA/USDT", "AVAX/USDT", "DOGE/USDT", "DOT/USDT", "MATIC/USDT",
        "LINK/USDT", "UNI/USDT", "ATOM/USDT", "FTM/USDT", "NEAR/USDT",
        "ALGO/USDT", "AAVE/USDT", "SAND/USDT", "MANA/USDT", "AXS/USDT"
    ]
    
    # Calculate date range (2 years of data)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=730)  # 2 years
    
    logger.info(f"Syncing data from {start_date.date()} to {end_date.date()}")
    logger.info(f"Data directory: {data_dir}")
    logger.info("-" * 60)
    
    total_candles = 0
    successful_pairs = 0
    
    for pair in pairs:
        # Extract symbol from pair
        symbol = pair.split("/")[0]
        
        logger.info(f"Syncing {pair}...")
        
        try:
            # Fetch data with pagination to get ALL records
            all_data = []
            page_size = 1000
            offset = 0
            
            while True:
                # Query OHLC data from Supabase with pagination
                # Note: Your data has timeframe='1h' set
                response = client.table("ohlc_data") \
                    .select("timestamp, open, high, low, close, volume") \
                    .eq("symbol", symbol) \
                    .eq("timeframe", "1h") \
                    .gte("timestamp", start_date.isoformat()) \
                    .lte("timestamp", end_date.isoformat()) \
                    .order("timestamp") \
                    .range(offset, offset + page_size - 1) \
                    .execute()
                
                if not response.data:
                    break
                
                all_data.extend(response.data)
                
                # Check if we got less than page_size records (meaning we're at the end)
                if len(response.data) < page_size:
                    break
                
                offset += page_size
                
                # Log progress for large datasets
                if offset % 5000 == 0:
                    logger.info(f"    Fetched {offset} records for {symbol}...")
            
            if not all_data:
                logger.warning(f"  No data found for {symbol}")
                continue
            
            # Convert to Freqtrade format
            candles = []
            for row in all_data:
                # Parse timestamp and convert to milliseconds
                ts = row['timestamp']
                if 'Z' in ts or '+' in ts:
                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                else:
                    # Assume UTC if no timezone
                    dt = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
                
                timestamp_ms = int(dt.timestamp() * 1000)
                
                candles.append([
                    timestamp_ms,
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    float(row['volume'])
                ])
            
            # Sort by timestamp
            candles.sort(key=lambda x: x[0])
            
            # Calculate date range info
            if candles:
                first_date = datetime.fromtimestamp(candles[0][0]/1000, tz=timezone.utc)
                last_date = datetime.fromtimestamp(candles[-1][0]/1000, tz=timezone.utc)
                days_of_data = (last_date - first_date).days
            
            # Save to file
            pair_filename = pair.replace("/", "_")
            filename = f"{pair_filename}-1h.json"
            filepath = data_dir / filename
            
            with open(filepath, 'w') as f:
                json.dump(candles, f)
            
            # Log detailed info about the data
            if candles:
                logger.info(f"  ✓ Saved {len(candles)} candles to {filename}")
                logger.info(f"    Date range: {first_date.date()} to {last_date.date()} ({days_of_data} days)")
            else:
                logger.info(f"  ✓ Saved {len(candles)} candles to {filename}")
            
            total_candles += len(candles)
            successful_pairs += 1
            
        except Exception as e:
            logger.error(f"  ✗ Error syncing {pair}: {e}")
    
    # Calculate storage used
    total_size = sum(f.stat().st_size for f in data_dir.glob("*-1h.json"))
    size_mb = total_size / (1024 * 1024)
    
    logger.info("-" * 60)
    logger.info(f"Sync complete!")
    logger.info(f"Successful pairs: {successful_pairs}/{len(pairs)}")
    logger.info(f"Total candles: {total_candles:,}")
    logger.info(f"Storage used: {size_mb:.1f} MB")
    
    return successful_pairs > 0


if __name__ == "__main__":
    success = sync_freqtrade_data()
    if success:
        print("\n✓ Data ready for Freqtrade backtesting!")
        print("You can now use the Freqtrade web UI to run backtests")
    else:
        print("\n✗ Sync failed - check the logs above")
        sys.exit(1)
