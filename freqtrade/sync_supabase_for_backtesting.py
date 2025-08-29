#!/usr/bin/env python3
"""
Sync Supabase OHLC data to Freqtrade format for backtesting
Converts data from Supabase to Freqtrade's expected JSON format
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List
import logging

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import Supabase client
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SupabaseToFreqtradeSync:
    """
    Syncs OHLC data from Supabase to Freqtrade format for backtesting
    """
    
    def __init__(self):
        """Initialize Supabase connection"""
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY')
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment")
        
        self.client: Client = create_client(self.supabase_url, self.supabase_key)
        
        # Freqtrade data directory
        self.data_dir = Path(__file__).parent / "user_data" / "data" / "kraken"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Data will be saved to: {self.data_dir}")
    
    def fetch_ohlc_data(self, symbol: str, days: int = 30) -> pd.DataFrame:
        """
        Fetch OHLC data from Supabase
        
        Args:
            symbol: Cryptocurrency symbol (e.g., "BTC")
            days: Number of days of historical data to fetch
            
        Returns:
            DataFrame with OHLC data
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days)
        
        logger.info(f"Fetching {days} days of data for {symbol}")
        
        try:
            # Query OHLC data from Supabase
            response = (
                self.client.table("ohlc_data")
                .select("timestamp, open, high, low, close, volume")
                .eq("symbol", symbol)
                .gte("timestamp", start_time.isoformat())
                .lte("timestamp", end_time.isoformat())
                .order("timestamp")
                .execute()
            )
            
            if not response.data:
                logger.warning(f"No data found for {symbol}")
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(response.data)
            
            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Ensure numeric types
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            logger.info(f"Fetched {len(df)} candles for {symbol}")
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()
    
    def convert_to_freqtrade_format(self, df: pd.DataFrame, pair: str) -> List[List]:
        """
        Convert DataFrame to Freqtrade's expected format
        
        Freqtrade expects JSON with structure:
        [
            [timestamp_ms, open, high, low, close, volume],
            ...
        ]
        
        Args:
            df: DataFrame with OHLC data
            pair: Trading pair (e.g., "BTC/USDT")
            
        Returns:
            List of lists in Freqtrade format
        """
        if df.empty:
            return []
        
        # Convert to Freqtrade format
        # Timestamp needs to be in milliseconds
        freqtrade_data = []
        
        for _, row in df.iterrows():
            timestamp_ms = int(row['timestamp'].timestamp() * 1000)
            freqtrade_data.append([
                timestamp_ms,
                float(row['open']),
                float(row['high']),
                float(row['low']),
                float(row['close']),
                float(row['volume'])
            ])
        
        return freqtrade_data
    
    def save_to_json(self, data: List[List], pair: str, timeframe: str = "1h"):
        """
        Save data in Freqtrade's expected JSON format
        
        Args:
            data: OHLC data in Freqtrade format
            pair: Trading pair (e.g., "BTC/USDT")
            timeframe: Timeframe (e.g., "1h", "5m")
        """
        if not data:
            logger.warning(f"No data to save for {pair}")
            return
        
        # Freqtrade expects filename format: {pair}-{timeframe}.json
        # Replace / with _ in pair name
        filename = f"{pair.replace('/', '_')}-{timeframe}.json"
        filepath = self.data_dir / filename
        
        # Save to JSON
        with open(filepath, 'w') as f:
            json.dump(data, f)
        
        logger.info(f"Saved {len(data)} candles to {filepath}")
    
    def sync_pair(self, symbol: str, days: int = 30, timeframe: str = "1h"):
        """
        Sync a single trading pair from Supabase to Freqtrade format
        
        Args:
            symbol: Cryptocurrency symbol (e.g., "BTC")
            days: Number of days of historical data
            timeframe: Timeframe for the data
        """
        pair = f"{symbol}/USDT"
        logger.info(f"Syncing {pair}")
        
        # Fetch data from Supabase
        df = self.fetch_ohlc_data(symbol, days)
        
        if df.empty:
            logger.warning(f"No data available for {pair}")
            return
        
        # Convert to Freqtrade format
        freqtrade_data = self.convert_to_freqtrade_format(df, pair)
        
        # Save to JSON
        self.save_to_json(freqtrade_data, pair, timeframe)
    
    def sync_all_pairs(self, symbols: List[str] = None, days: int = 30, timeframe: str = "1h"):
        """
        Sync multiple trading pairs
        
        Args:
            symbols: List of symbols to sync (default: common pairs)
            days: Number of days of historical data
            timeframe: Timeframe for the data
        """
        if symbols is None:
            # Default to common trading pairs
            symbols = [
                "BTC", "ETH", "SOL", "BNB", "XRP", 
                "ADA", "AVAX", "DOGE", "DOT", "LINK",
                "ATOM", "ALGO", "MANA"
            ]
        
        logger.info(f"Starting sync for {len(symbols)} pairs")
        
        success_count = 0
        for symbol in symbols:
            try:
                self.sync_pair(symbol, days, timeframe)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to sync {symbol}: {e}")
        
        logger.info(f"Successfully synced {success_count}/{len(symbols)} pairs")
        
        # Create metadata file for Freqtrade
        self.create_metadata()
    
    def create_metadata(self):
        """Create metadata file that Freqtrade might expect"""
        metadata = {
            "exchange": "kraken",
            "data_source": "supabase",
            "sync_date": datetime.now(timezone.utc).isoformat(),
            "timeframe": "1h",
            "data_format": "json"
        }
        
        metadata_file = self.data_dir / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Created metadata file: {metadata_file}")
    
    def verify_data(self, pair: str = "BTC/USDT", timeframe: str = "1h"):
        """
        Verify that data was saved correctly and can be loaded
        
        Args:
            pair: Trading pair to verify
            timeframe: Timeframe to verify
        """
        filename = f"{pair.replace('/', '_')}-{timeframe}.json"
        filepath = self.data_dir / filename
        
        if not filepath.exists():
            logger.error(f"File not found: {filepath}")
            return False
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            if not data:
                logger.error(f"No data in file: {filepath}")
                return False
            
            # Check data structure
            first_candle = data[0]
            if len(first_candle) != 6:
                logger.error(f"Invalid data structure. Expected 6 fields, got {len(first_candle)}")
                return False
            
            logger.info(f"✓ Verified {pair}: {len(data)} candles")
            logger.info(f"  First candle: {datetime.fromtimestamp(first_candle[0]/1000, tz=timezone.utc)}")
            logger.info(f"  Last candle:  {datetime.fromtimestamp(data[-1][0]/1000, tz=timezone.utc)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error verifying data: {e}")
            return False


def main():
    """Main function to run the sync"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Sync Supabase data to Freqtrade format')
    parser.add_argument('--days', type=int, default=30, help='Number of days of historical data')
    parser.add_argument('--symbols', nargs='+', help='Symbols to sync (e.g., BTC ETH SOL)')
    parser.add_argument('--timeframe', default='1h', help='Timeframe (e.g., 1h, 5m, 15m)')
    parser.add_argument('--verify', action='store_true', help='Verify data after sync')
    
    args = parser.parse_args()
    
    # Initialize syncer
    syncer = SupabaseToFreqtradeSync()
    
    # Sync data
    logger.info("=" * 50)
    logger.info("Starting Supabase to Freqtrade sync")
    logger.info("=" * 50)
    
    syncer.sync_all_pairs(
        symbols=args.symbols,
        days=args.days,
        timeframe=args.timeframe
    )
    
    # Verify if requested
    if args.verify:
        logger.info("\nVerifying synced data...")
        test_pairs = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        for pair in test_pairs:
            syncer.verify_data(pair, args.timeframe)
    
    logger.info("\n✅ Sync complete!")
    logger.info(f"Data saved to: {syncer.data_dir}")
    logger.info("\nTo run backtesting with this data:")
    logger.info("freqtrade backtesting --strategy ChannelStrategyV1 --timeframe 1h")


if __name__ == "__main__":
    main()
