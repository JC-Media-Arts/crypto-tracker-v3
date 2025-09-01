#!/usr/bin/env python3
"""
Sync 1-minute data from Supabase and resample to 5-minute for Freqtrade hyperopt
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Output directory for Freqtrade
DATA_DIR = Path("user_data/data/kraken")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Pairs to sync (from config)
PAIRS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "ADA/USDT", "AVAX/USDT", "DOGE/USDT", "DOT/USDT", "LINK/USDT",
    "ATOM/USDT", "ALGO/USDT", "MANA/USDT"
]

def fetch_1m_data(symbol: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """Fetch 1-minute data from Supabase with pagination"""
    logger.info(f"Fetching 1m data for {symbol}...")
    
    all_data = []
    page_size = 1000
    offset = 0
    
    while True:
        response = client.table("ohlc_data") \
            .select("timestamp, open, high, low, close, volume") \
            .eq("symbol", symbol) \
            .eq("timeframe", "1m") \
            .gte("timestamp", start_date.isoformat()) \
            .lte("timestamp", end_date.isoformat()) \
            .order("timestamp") \
            .range(offset, offset + page_size - 1) \
            .execute()
        
        if not response.data:
            break
        
        all_data.extend(response.data)
        
        if len(response.data) < page_size:
            break
        
        offset += page_size
        
        if offset % 10000 == 0:
            logger.info(f"    Fetched {offset} records for {symbol}...")
    
    if not all_data:
        logger.warning(f"No 1m data found for {symbol}")
        return pd.DataFrame()
    
    df = pd.DataFrame(all_data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df = df.sort_index()
    
    logger.info(f"  Fetched {len(df)} 1m candles for {symbol}")
    return df

def resample_to_5m(df_1m: pd.DataFrame) -> pd.DataFrame:
    """Resample 1-minute data to 5-minute"""
    if df_1m.empty:
        return pd.DataFrame()
    
    # Resample using OHLCV aggregation rules
    df_5m = df_1m.resample('5T').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    return df_5m

def save_to_freqtrade_format(df: pd.DataFrame, pair: str, timeframe: str = "5m"):
    """Save DataFrame in Freqtrade's expected JSON format"""
    if df.empty:
        logger.warning(f"No data to save for {pair}")
        return
    
    # Convert to Freqtrade format (timestamp in milliseconds)
    data = []
    for timestamp, row in df.iterrows():
        data.append([
            int(timestamp.timestamp() * 1000),  # timestamp in ms
            float(row['open']),
            float(row['high']),
            float(row['low']),
            float(row['close']),
            float(row['volume'])
        ])
    
    # Create filename in Freqtrade format
    pair_formatted = pair.replace("/", "_")
    filename = DATA_DIR / f"{pair_formatted}-{timeframe}.json"
    
    # Save to JSON
    with open(filename, 'w') as f:
        json.dump(data, f)
    
    logger.info(f"  Saved {len(data)} candles to {filename}")

def main():
    """Main sync function"""
    logger.info("Starting 5-minute data sync from 1-minute data")
    
    # Date range for hyperopt (6 months)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=180)  # 6 months
    
    logger.info(f"Date range: {start_date.date()} to {end_date.date()}")
    
    successful = 0
    failed = 0
    
    for pair in PAIRS:
        try:
            # Convert pair format (BTC/USDT -> BTC)
            symbol = pair.split("/")[0]
            
            # Fetch 1m data
            df_1m = fetch_1m_data(symbol, start_date, end_date)
            
            if df_1m.empty:
                logger.warning(f"Skipping {pair} - no 1m data available")
                failed += 1
                continue
            
            # Resample to 5m
            df_5m = resample_to_5m(df_1m)
            
            if df_5m.empty:
                logger.warning(f"Skipping {pair} - resampling failed")
                failed += 1
                continue
            
            # Save in Freqtrade format
            save_to_freqtrade_format(df_5m, pair, "5m")
            successful += 1
            
            # Show date range
            logger.info(f"  Date range: {df_5m.index[0]} to {df_5m.index[-1]}")
            
        except Exception as e:
            logger.error(f"Error processing {pair}: {e}")
            failed += 1
    
    logger.info(f"\nSync complete! Successfully synced {successful} pairs, {failed} failed")
    
    # List the created files
    logger.info("\nCreated files:")
    for file in sorted(DATA_DIR.glob("*-5m.json")):
        size = file.stat().st_size / 1024 / 1024  # MB
        logger.info(f"  {file.name} ({size:.2f} MB)")

if __name__ == "__main__":
    main()
