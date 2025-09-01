#!/usr/bin/env python3
"""
Sync OHLC data from Supabase to Freqtrade format for backtesting.

This script fetches historical OHLC data from Supabase and saves it in 
Freqtrade's expected JSON format for use with the backtesting web UI.
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FreqtradeDataSync:
    """Sync OHLC data from Supabase to Freqtrade format."""
    
    def __init__(self):
        """Initialize the data sync."""
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        
        self.client: Client = create_client(self.supabase_url, self.supabase_key)
        
        # Freqtrade data directory
        self.data_dir = Path("/Users/justincoit/crypto-tracker-v3/freqtrade/user_data/data/kraken")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Pairs to sync (from your config)
        self.pairs = [
            "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
            "ADA/USDT", "AVAX/USDT", "DOGE/USDT", "DOT/USDT", "MATIC/USDT",
            "LINK/USDT", "UNI/USDT", "ATOM/USDT", "FTM/USDT", "NEAR/USDT",
            "ALGO/USDT", "AAVE/USDT", "SAND/USDT", "MANA/USDT", "AXS/USDT"
        ]
        
        # Timeframes to sync (1h for main, 5m and 15m for detail)
        self.timeframes = {
            "1h": 60,      # 60 minutes
            "5m": 5,       # 5 minutes
            "15m": 15      # 15 minutes
        }
        
        # How much history to fetch (2 years)
        self.days_of_history = 730  # 2 years
        
    def get_ohlc_data(self, symbol: str, timeframe: str, start_date: datetime, end_date: datetime) -> List[List]:
        """
        Fetch OHLC data from Supabase.
        
        Args:
            symbol: Cryptocurrency symbol (e.g., "BTC")
            timeframe: Timeframe string (e.g., "1h", "5m")
            start_date: Start date for data
            end_date: End date for data
            
        Returns:
            List of OHLC candles in Freqtrade format
        """
        try:
            # Determine the interval based on timeframe
            interval_minutes = self.timeframes[timeframe]
            
            # For 1h data, use the ohlc_data table
            if timeframe == "1h":
                response = self.client.table("ohlc_data") \
                    .select("timestamp, open, high, low, close, volume") \
                    .eq("symbol", symbol) \
                    .gte("timestamp", start_date.isoformat()) \
                    .lte("timestamp", end_date.isoformat()) \
                    .order("timestamp") \
                    .execute()
            else:
                # For 5m and 15m, we need to query the appropriate table
                # Assuming you have 5m and 15m data in separate tables or with interval column
                table_name = f"ohlc_data_{timeframe}" if timeframe != "1h" else "ohlc_data"
                
                # Check if specific timeframe table exists, otherwise aggregate from 1m data
                try:
                    response = self.client.table(table_name) \
                        .select("timestamp, open, high, low, close, volume") \
                        .eq("symbol", symbol) \
                        .gte("timestamp", start_date.isoformat()) \
                        .lte("timestamp", end_date.isoformat()) \
                        .order("timestamp") \
                        .execute()
                except:
                    # If specific table doesn't exist, try to aggregate from 1m data
                    logger.warning(f"Table {table_name} not found, trying to aggregate from 1m data")
                    response = self.aggregate_from_1m(symbol, timeframe, start_date, end_date)
            
            if not response.data:
                logger.warning(f"No data found for {symbol} {timeframe}")
                return []
            
            # Convert to Freqtrade format [timestamp_ms, open, high, low, close, volume]
            candles = []
            for row in response.data:
                timestamp_ms = int(datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00')).timestamp() * 1000)
                candles.append([
                    timestamp_ms,
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    float(row['volume'])
                ])
            
            return candles
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol} {timeframe}: {e}")
            return []
    
    def aggregate_from_1m(self, symbol: str, timeframe: str, start_date: datetime, end_date: datetime) -> Dict:
        """
        Aggregate 1-minute data to create higher timeframes.
        
        This is a fallback if specific timeframe tables don't exist.
        """
        try:
            # Fetch 1m data
            response = self.client.table("ohlc_data") \
                .select("timestamp, open, high, low, close, volume") \
                .eq("symbol", symbol) \
                .eq("interval", "1m") \
                .gte("timestamp", start_date.isoformat()) \
                .lte("timestamp", end_date.isoformat()) \
                .order("timestamp") \
                .execute()
            
            if not response.data:
                return {"data": []}
            
            # Aggregate to desired timeframe
            interval_minutes = self.timeframes[timeframe]
            aggregated = []
            current_candle = None
            
            for row in response.data:
                timestamp = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
                
                # Check if we need to start a new candle
                if current_candle is None or \
                   (timestamp - current_candle['start']).total_seconds() >= interval_minutes * 60:
                    
                    if current_candle:
                        aggregated.append(current_candle['data'])
                    
                    # Start new candle
                    current_candle = {
                        'start': timestamp.replace(minute=(timestamp.minute // interval_minutes) * interval_minutes, second=0, microsecond=0),
                        'data': {
                            'timestamp': timestamp.isoformat(),
                            'open': float(row['open']),
                            'high': float(row['high']),
                            'low': float(row['low']),
                            'close': float(row['close']),
                            'volume': float(row['volume'])
                        }
                    }
                else:
                    # Update current candle
                    current_candle['data']['high'] = max(current_candle['data']['high'], float(row['high']))
                    current_candle['data']['low'] = min(current_candle['data']['low'], float(row['low']))
                    current_candle['data']['close'] = float(row['close'])
                    current_candle['data']['volume'] += float(row['volume'])
            
            # Add last candle
            if current_candle:
                aggregated.append(current_candle['data'])
            
            return {"data": aggregated}
            
        except Exception as e:
            logger.error(f"Error aggregating 1m data: {e}")
            return {"data": []}
    
    def save_data_file(self, pair: str, timeframe: str, data: List[List]):
        """
        Save data to JSON file in Freqtrade format.
        
        Args:
            pair: Trading pair (e.g., "BTC/USDT")
            timeframe: Timeframe (e.g., "1h")
            data: OHLC data in Freqtrade format
        """
        # Convert pair format: "BTC/USDT" -> "BTC_USDT"
        pair_filename = pair.replace("/", "_")
        
        # Create filename: BTC_USDT-1h.json
        filename = f"{pair_filename}-{timeframe}.json"
        filepath = self.data_dir / filename
        
        # Save to file
        with open(filepath, 'w') as f:
            json.dump(data, f)
        
        logger.info(f"Saved {len(data)} candles to {filename}")
    
    def sync_pair(self, pair: str):
        """
        Sync all timeframes for a single pair.
        
        Args:
            pair: Trading pair (e.g., "BTC/USDT")
        """
        # Extract symbol from pair
        symbol = pair.split("/")[0]
        
        # Calculate date range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=self.days_of_history)
        
        logger.info(f"Syncing {pair} from {start_date.date()} to {end_date.date()}")
        
        # Sync each timeframe
        for timeframe in self.timeframes.keys():
            logger.info(f"  Fetching {timeframe} data...")
            
            # Get data from Supabase
            data = self.get_ohlc_data(symbol, timeframe, start_date, end_date)
            
            if data:
                # Save to file
                self.save_data_file(pair, timeframe, data)
                logger.info(f"  ✓ Synced {len(data)} {timeframe} candles")
            else:
                logger.warning(f"  ✗ No {timeframe} data available")
    
    def validate_data(self):
        """
        Validate that all expected files exist and have recent data.
        """
        logger.info("\nValidating synced data...")
        
        missing_files = []
        outdated_files = []
        
        for pair in self.pairs:
            pair_filename = pair.replace("/", "_")
            
            for timeframe in self.timeframes.keys():
                filename = f"{pair_filename}-{timeframe}.json"
                filepath = self.data_dir / filename
                
                if not filepath.exists():
                    missing_files.append(filename)
                else:
                    # Check if data is recent (last candle within 24 hours)
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        if data:
                            last_timestamp = data[-1][0]
                            last_date = datetime.fromtimestamp(last_timestamp / 1000, tz=timezone.utc)
                            age = datetime.now(timezone.utc) - last_date
                            
                            if age > timedelta(days=1):
                                outdated_files.append(f"{filename} (last update: {last_date.date()})")
        
        if missing_files:
            logger.warning(f"Missing files: {missing_files}")
        
        if outdated_files:
            logger.warning(f"Outdated files: {outdated_files}")
        
        if not missing_files and not outdated_files:
            logger.info("✓ All data files are present and up to date")
        
        return len(missing_files) == 0 and len(outdated_files) == 0
    
    def run(self):
        """
        Run the complete sync process.
        """
        logger.info("=" * 60)
        logger.info("Starting Freqtrade Data Sync")
        logger.info(f"Syncing {len(self.pairs)} pairs × {len(self.timeframes)} timeframes")
        logger.info(f"History: {self.days_of_history} days")
        logger.info(f"Data directory: {self.data_dir}")
        logger.info("=" * 60)
        
        # Track statistics
        total_candles = 0
        start_time = datetime.now()
        
        # Sync each pair
        for i, pair in enumerate(self.pairs, 1):
            logger.info(f"\n[{i}/{len(self.pairs)}] Syncing {pair}...")
            self.sync_pair(pair)
        
        # Calculate statistics
        duration = datetime.now() - start_time
        
        # Count total candles
        for filepath in self.data_dir.glob("*.json"):
            with open(filepath, 'r') as f:
                data = json.load(f)
                total_candles += len(data)
        
        # Calculate storage used
        total_size = sum(f.stat().st_size for f in self.data_dir.glob("*.json"))
        size_mb = total_size / (1024 * 1024)
        
        # Validate data
        is_valid = self.validate_data()
        
        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("Sync Complete!")
        logger.info(f"Duration: {duration}")
        logger.info(f"Total candles: {total_candles:,}")
        logger.info(f"Storage used: {size_mb:.1f} MB")
        logger.info(f"Files created: {len(list(self.data_dir.glob('*.json')))}")
        logger.info(f"Data valid: {'✓' if is_valid else '✗'}")
        logger.info("=" * 60)
        
        return is_valid


def main():
    """Main entry point."""
    try:
        syncer = FreqtradeDataSync()
        success = syncer.run()
        
        if success:
            logger.info("\n✓ Data sync completed successfully!")
            logger.info("You can now run backtests through the Freqtrade web UI")
            sys.exit(0)
        else:
            logger.error("\n✗ Data sync completed with issues")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
