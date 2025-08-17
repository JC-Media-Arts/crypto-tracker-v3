#!/usr/bin/env python3
"""
Fetch 1-minute OHLC data for all symbols (1 year of history).
This is the most granular data for precise backtesting.
"""

import sys
import json
import time
from datetime import datetime, timedelta, timezone as tz
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd
from polygon import RESTClient
from loguru import logger

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from src.config.settings import get_settings

class OneMinuteFetcher:
    def __init__(self):
        settings = get_settings()
        self.client = RESTClient(api_key=settings.polygon_api_key)
        self.supabase = SupabaseClient()
        self.results = {}
        self.batch_size = 500  # Smaller batches for 1-minute data
        
    def get_all_symbols(self) -> List[str]:
        """Get all unique symbols from price_data table"""
        try:
            result = self.supabase.client.table('price_data').select('symbol').execute()
            symbols = list(set([r['symbol'] for r in result.data]))
            symbols.sort()
            logger.info(f"Found {len(symbols)} unique symbols to process")
            return symbols
        except Exception as e:
            logger.error(f"Error fetching symbols: {e}")
            return []
    
    def check_existing_data(self, symbol: str) -> int:
        """Check how many 1-minute bars we already have for this symbol"""
        try:
            result = self.supabase.client.table('ohlc_data')\
                .select('count', count='exact', head=True)\
                .eq('symbol', symbol)\
                .eq('timeframe', '1m')\
                .execute()
            return result.count
        except:
            return 0
    
    def fetch_batch(self, symbol: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Fetch a batch of 1-minute bars from Polygon"""
        try:
            bars = []
            for bar in self.client.list_aggs(
                ticker=f"X:{symbol}USD",
                multiplier=1,
                timespan="minute",
                from_=start_date.strftime('%Y-%m-%d'),
                to=end_date.strftime('%Y-%m-%d'),
                limit=50000
            ):
                bars.append({
                    'timestamp': pd.Timestamp(bar.timestamp, unit='ms', tz='UTC').isoformat(),
                    'symbol': symbol,
                    'timeframe': '1m',
                    'open': float(bar.open),
                    'high': float(bar.high),
                    'low': float(bar.low),
                    'close': float(bar.close),
                    'volume': float(bar.volume) if bar.volume else 0,
                    'vwap': float(bar.vwap) if hasattr(bar, 'vwap') and bar.vwap else None,
                    'trades': int(bar.transactions) if hasattr(bar, 'transactions') else None
                })
            
            if bars:
                logger.info(f"Fetched {len(bars)} bars for {symbol}")
            else:
                logger.warning(f"No data available for {symbol} from {start_date.date()} to {end_date.date()}")
            
            return bars
        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
            return []
    
    def save_batch(self, bars: List[Dict]) -> bool:
        """Save a batch of bars to the database"""
        if not bars:
            return True
            
        try:
            # Save in smaller chunks
            for i in range(0, len(bars), self.batch_size):
                chunk = bars[i:i+self.batch_size]
                self.supabase.client.table('ohlc_data').upsert(chunk).execute()
                logger.success(f"Saved {len(chunk)} bars")
            return True
        except Exception as e:
            logger.error(f"Error saving batch: {e}")
            return False
    
    def fetch_symbol(self, symbol: str) -> Dict:
        """Fetch 1 year of 1-minute data for a symbol"""
        logger.info(f"\n{'='*40}")
        logger.info(f"Fetching 1m data for {symbol}")
        logger.info(f"{'='*40}")
        
        # Check existing data
        existing_count = self.check_existing_data(symbol)
        if existing_count > 350000:  # ~1 year of minute data (365 * 24 * 60 * 0.3 for market hours)
            logger.success(f"✓ {symbol} already has {existing_count:,} bars, skipping")
            return {
                'status': 'skipped',
                'bars_saved': 0,
                'existing': existing_count
            }
        
        # Fetch 1 year of data in 30-day chunks
        end_date = datetime.now(tz.utc)
        start_date = end_date - timedelta(days=365)
        
        all_bars = []
        current_date = start_date
        
        while current_date < end_date:
            batch_end = min(current_date + timedelta(days=30), end_date)
            
            logger.info(f"Fetching {current_date.date()} to {batch_end.date()}...")
            bars = self.fetch_batch(symbol, current_date, batch_end)
            
            if bars:
                all_bars.extend(bars)
                logger.info(f"Progress: {current_date.date()} to {batch_end.date()} - {len(bars)} bars")
            
            current_date = batch_end
            time.sleep(0.2)  # Small delay between requests
        
        # Save all bars
        if all_bars:
            logger.info(f"Saving {len(all_bars)} total bars...")
            if self.save_batch(all_bars):
                logger.success(f"✅ Completed {symbol}: {len(all_bars)} bars")
                return {
                    'status': 'completed',
                    'bars_saved': len(all_bars)
                }
            else:
                logger.error(f"❌ Failed to save {symbol}")
                return {
                    'status': 'failed',
                    'bars_saved': 0
                }
        else:
            logger.warning(f"No data found for {symbol}")
            return {
                'status': 'no_data',
                'bars_saved': 0
            }
    
    def save_results(self):
        """Save results to JSON file"""
        with open('data/1min_all_symbols_results.json', 'w') as f:
            json.dump(self.results, f, indent=2)
        logger.info("Results saved to data/1min_all_symbols_results.json")
    
    def fetch_all(self):
        """Fetch 1-minute data for all symbols"""
        logger.info("\n" + "="*60)
        logger.info("1-MINUTE OHLC FETCHER FOR ALL SYMBOLS")
        logger.info("="*60)
        
        symbols = self.get_all_symbols()
        
        if not symbols:
            logger.error("No symbols found to process")
            return
        
        # Process each symbol
        for i, symbol in enumerate(symbols, 1):
            logger.info(f"\n[{i}/{len(symbols)}] Processing {symbol}")
            
            try:
                result = self.fetch_symbol(symbol)
                self.results[symbol] = result
                self.save_results()  # Save after each symbol
                
                # Small delay between symbols
                if i < len(symbols):
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                self.results[symbol] = {
                    'status': 'error',
                    'bars_saved': 0,
                    'error': str(e)
                }
        
        # Final summary
        logger.info("\n" + "="*60)
        logger.info("1-MINUTE DATA FETCH COMPLETE")
        logger.info("="*60)
        
        completed = sum(1 for r in self.results.values() if r['status'] == 'completed')
        skipped = sum(1 for r in self.results.values() if r['status'] == 'skipped')
        failed = sum(1 for r in self.results.values() if r['status'] in ['failed', 'error'])
        no_data = sum(1 for r in self.results.values() if r['status'] == 'no_data')
        
        logger.info(f"Successful: {completed}")
        logger.info(f"Skipped (already had data): {skipped}")
        logger.info(f"No data available: {no_data}")
        logger.info(f"Failed: {failed}")
        
        total_bars = sum(r.get('bars_saved', 0) for r in self.results.values())
        logger.info(f"Total bars saved: {total_bars:,}")

if __name__ == "__main__":
    fetcher = OneMinuteFetcher()
    fetcher.fetch_all()
