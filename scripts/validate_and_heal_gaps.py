#!/usr/bin/env python3
"""
OHLC Data Gap Detection and Healing
Finds and fixes gaps in OHLC data across all timeframes
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dateutil import tz
import argparse

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from src.data.supabase_client import SupabaseClient
from loguru import logger
import pandas as pd

# Configure logging
logger.remove()
logger.add(
    "logs/gap_detection.log",
    rotation="1 day",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)
logger.add(sys.stdout, level="INFO")

class GapDetector:
    """Detects and heals gaps in OHLC data"""
    
    def __init__(self):
        self.settings = get_settings()
        self.supabase = SupabaseClient()
        
        # Expected intervals for each timeframe (in minutes)
        self.expected_intervals = {
            '1m': 1,
            '15m': 15,
            '1h': 60,
            '1d': 1440
        }
        
        # Maximum acceptable gap before considering it a real gap (in intervals)
        # e.g., for 1m data, 5 means gaps > 5 minutes are real gaps
        self.max_acceptable_gap = {
            '1m': 5,      # 5 minutes
            '15m': 2,     # 30 minutes
            '1h': 2,      # 2 hours
            '1d': 2       # 2 days
        }
        
        self.gaps_found = []
        
    def get_all_symbols(self) -> List[str]:
        """Get list of all symbols"""
        symbols = [
            # Tier 1: Core (20 coins)
            'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'AVAX', 'DOGE', 'DOT', 'POL',
            'LINK', 'TON', 'SHIB', 'TRX', 'UNI', 'ATOM', 'BCH', 'APT', 'NEAR', 'ICP',
            
            # Tier 2: DeFi/Layer 2 (20 coins)
            'ARB', 'OP', 'AAVE', 'CRV', 'MKR', 'LDO', 'SUSHI', 'COMP', 'SNX', 'BAL',
            'INJ', 'SEI', 'PENDLE', 'BLUR', 'ENS', 'GRT', 'RENDER', 'FET', 'RPL', 'SAND',
            
            # Tier 3: Trending/Memecoins (20 coins)
            'PEPE', 'WIF', 'BONK', 'FLOKI', 'MEME', 'POPCAT', 'MEW', 'TURBO', 'NEIRO', 'PNUT',
            'GOAT', 'ACT', 'TRUMP', 'FARTCOIN', 'MOG', 'PONKE', 'TREMP', 'BRETT', 'GIGA', 'HIPPO',
            
            # Tier 4: Solid Mid-Caps (40 coins)
            'FIL', 'RUNE', 'IMX', 'FLOW', 'MANA', 'AXS', 'CHZ', 'GALA', 'LRC', 'OCEAN',
            'QNT', 'ALGO', 'XLM', 'XMR', 'ZEC', 'DASH', 'HBAR', 'VET', 'THETA', 'EOS',
            'KSM', 'STX', 'KAS', 'TIA', 'JTO', 'JUP', 'PYTH', 'DYM', 'STRK', 'ALT',
            'PORTAL', 'BEAM', 'BLUR', 'MASK', 'API3', 'ANKR', 'CTSI', 'YFI', 'AUDIO', 'ENJ'
        ]
        return symbols
    
    def detect_gaps_for_symbol(self, symbol: str, timeframe: str, 
                               start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None) -> List[Dict]:
        """Detect gaps in data for a specific symbol and timeframe"""
        gaps = []
        
        try:
            # Set default date range if not provided
            if not end_date:
                end_date = datetime.now(tz.UTC)
            if not start_date:
                # Look back based on timeframe
                lookback_days = {
                    '1m': 7,     # 1 week for minute data
                    '15m': 30,   # 1 month for 15-min data
                    '1h': 90,    # 3 months for hourly data
                    '1d': 365    # 1 year for daily data
                }
                start_date = end_date - timedelta(days=lookback_days[timeframe])
            
            # Fetch data for the period
            query = self.supabase.client.table('ohlc_data').select('timestamp').eq(
                'symbol', symbol
            ).eq(
                'timeframe', timeframe
            ).gte(
                'timestamp', start_date.isoformat()
            ).lte(
                'timestamp', end_date.isoformat()
            ).order('timestamp')
            
            # Execute query in batches if needed
            all_data = []
            offset = 0
            batch_size = 1000
            
            while True:
                response = query.range(offset, offset + batch_size - 1).execute()
                if not response.data:
                    break
                all_data.extend(response.data)
                if len(response.data) < batch_size:
                    break
                offset += batch_size
            
            if len(all_data) < 2:
                return gaps
            
            # Convert to pandas for easier gap detection
            df = pd.DataFrame(all_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            
            # Calculate time differences
            df['time_diff'] = df['timestamp'].diff()
            expected_timedelta = timedelta(minutes=self.expected_intervals[timeframe])
            max_gap_timedelta = expected_timedelta * self.max_acceptable_gap[timeframe]
            
            # Find gaps
            gap_mask = df['time_diff'] > max_gap_timedelta
            gap_indices = df[gap_mask].index.tolist()
            
            for idx in gap_indices:
                gap_start = df.loc[idx - 1, 'timestamp'] if idx > 0 else None
                gap_end = df.loc[idx, 'timestamp']
                gap_duration = df.loc[idx, 'time_diff']
                
                gap_info = {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'gap_start': gap_start.isoformat() if gap_start else None,
                    'gap_end': gap_end.isoformat(),
                    'gap_duration_minutes': gap_duration.total_seconds() / 60,
                    'expected_bars_missing': int(gap_duration / expected_timedelta)
                }
                gaps.append(gap_info)
                
            if gaps:
                logger.warning(f"Found {len(gaps)} gaps for {symbol}/{timeframe}")
                
        except Exception as e:
            logger.error(f"Error detecting gaps for {symbol}/{timeframe}: {e}")
        
        return gaps
    
    def heal_gap(self, gap: Dict) -> bool:
        """Attempt to heal a single gap by fetching missing data"""
        try:
            from scripts.incremental_ohlc_updater import IncrementalOHLCUpdater
            
            updater = IncrementalOHLCUpdater()
            
            symbol = gap['symbol']
            timeframe = gap['timeframe']
            
            # Parse gap boundaries
            gap_start = pd.to_datetime(gap['gap_start']) if gap['gap_start'] else None
            gap_end = pd.to_datetime(gap['gap_end'])
            
            if not gap_start:
                logger.warning(f"Cannot heal gap for {symbol}/{timeframe} - no start time")
                return False
            
            # Ensure timezone aware
            if gap_start.tzinfo is None:
                gap_start = gap_start.replace(tzinfo=tz.UTC)
            if gap_end.tzinfo is None:
                gap_end = gap_end.replace(tzinfo=tz.UTC)
            
            logger.info(f"Attempting to heal gap for {symbol}/{timeframe} from {gap_start} to {gap_end}")
            
            # Fetch data for the gap period
            data = updater.fetch_ohlc_from_polygon(symbol, timeframe, gap_start, gap_end)
            
            if data:
                records_saved = updater.save_ohlc_batch(data, symbol, timeframe)
                if records_saved > 0:
                    logger.success(f"Healed gap for {symbol}/{timeframe}: {records_saved} records added")
                    return True
                else:
                    logger.warning(f"No records saved for gap in {symbol}/{timeframe}")
                    return False
            else:
                logger.warning(f"No data available to heal gap for {symbol}/{timeframe}")
                return False
                
        except Exception as e:
            logger.error(f"Error healing gap: {e}")
            return False
    
    def scan_all_symbols(self, timeframe: str = None) -> Dict:
        """Scan all symbols for gaps"""
        results = {
            'gaps_found': 0,
            'gaps_healed': 0,
            'gaps_unhealable': 0,
            'symbols_scanned': 0,
            'gap_details': []
        }
        
        symbols = self.get_all_symbols()
        timeframes = [timeframe] if timeframe else ['1m', '15m', '1h', '1d']
        
        logger.info(f"Starting gap scan for {len(symbols)} symbols across {len(timeframes)} timeframes")
        
        for tf in timeframes:
            logger.info(f"Scanning {tf} timeframe...")
            
            for symbol in symbols:
                gaps = self.detect_gaps_for_symbol(symbol, tf)
                results['symbols_scanned'] += 1
                
                if gaps:
                    results['gaps_found'] += len(gaps)
                    results['gap_details'].extend(gaps)
                    
                    # Attempt to heal each gap
                    for gap in gaps:
                        if self.heal_gap(gap):
                            results['gaps_healed'] += 1
                        else:
                            results['gaps_unhealable'] += 1
        
        # Save gap report
        self.save_gap_report(results)
        
        logger.info(f"""
        ========================================
        GAP SCAN COMPLETE
        ========================================
        Symbols Scanned: {results['symbols_scanned']}
        Gaps Found: {results['gaps_found']}
        Gaps Healed: {results['gaps_healed']}
        Gaps Unhealable: {results['gaps_unhealable']}
        ========================================
        """)
        
        return results
    
    def save_gap_report(self, results: Dict):
        """Save gap report to file and database"""
        try:
            # Save to file
            report_path = Path('data/gap_reports')
            report_path.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_file = report_path / f'gap_report_{timestamp}.json'
            
            with open(report_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            
            logger.info(f"Gap report saved to {report_file}")
            
            # Save summary to database
            for gap in results['gap_details']:
                try:
                    self.supabase.client.table('data_gaps').insert({
                        'symbol': gap['symbol'],
                        'timeframe': gap['timeframe'],
                        'gap_start': gap['gap_start'],
                        'gap_end': gap['gap_end'],
                        'duration_minutes': gap['gap_duration_minutes'],
                        'detected_at': datetime.now(tz.UTC).isoformat(),
                        'healed': False  # Will be updated if healed
                    }).execute()
                except Exception as e:
                    logger.debug(f"Gap record may already exist: {e}")
                    
        except Exception as e:
            logger.error(f"Error saving gap report: {e}")
    
    def get_data_completeness(self, symbol: str = None) -> Dict:
        """Calculate data completeness metrics"""
        results = {}
        
        symbols = [symbol] if symbol else self.get_all_symbols()
        
        for sym in symbols:
            sym_stats = {}
            
            for timeframe in ['1m', '15m', '1h', '1d']:
                try:
                    # Get date range
                    response = self.supabase.client.table('ohlc_data').select(
                        'timestamp'
                    ).eq(
                        'symbol', sym
                    ).eq(
                        'timeframe', timeframe
                    ).order(
                        'timestamp', desc=False
                    ).limit(1).execute()
                    
                    if response.data:
                        first_timestamp = pd.to_datetime(response.data[0]['timestamp'])
                        
                        response = self.supabase.client.table('ohlc_data').select(
                            'timestamp'
                        ).eq(
                            'symbol', sym
                        ).eq(
                            'timeframe', timeframe
                        ).order(
                            'timestamp', desc=True
                        ).limit(1).execute()
                        
                        if response.data:
                            last_timestamp = pd.to_datetime(response.data[0]['timestamp'])
                            
                            # Calculate expected vs actual bars
                            time_range = last_timestamp - first_timestamp
                            expected_bars = time_range.total_seconds() / (self.expected_intervals[timeframe] * 60)
                            
                            # Get actual count
                            count_response = self.supabase.client.table('ohlc_data').select(
                                'symbol', count='exact'
                            ).eq(
                                'symbol', sym
                            ).eq(
                                'timeframe', timeframe
                            ).execute()
                            
                            actual_bars = count_response.count if hasattr(count_response, 'count') else 0
                            
                            completeness = (actual_bars / expected_bars * 100) if expected_bars > 0 else 0
                            
                            sym_stats[timeframe] = {
                                'first_date': first_timestamp.isoformat(),
                                'last_date': last_timestamp.isoformat(),
                                'expected_bars': int(expected_bars),
                                'actual_bars': actual_bars,
                                'completeness_pct': round(completeness, 2)
                            }
                        
                except Exception as e:
                    logger.error(f"Error calculating completeness for {sym}/{timeframe}: {e}")
                    sym_stats[timeframe] = {'error': str(e)}
            
            results[sym] = sym_stats
        
        return results

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='OHLC Data Gap Detection and Healing')
    parser.add_argument('--action', choices=['scan', 'heal', 'report', 'completeness'],
                       default='scan', help='Action to perform')
    parser.add_argument('--timeframe', choices=['1m', '15m', '1h', '1d'],
                       help='Specific timeframe to check')
    parser.add_argument('--symbol', help='Specific symbol to check')
    
    args = parser.parse_args()
    
    detector = GapDetector()
    
    if args.action == 'scan':
        detector.scan_all_symbols(args.timeframe)
    elif args.action == 'completeness':
        results = detector.get_data_completeness(args.symbol)
        print(json.dumps(results, indent=2, default=str))
    elif args.action == 'heal':
        # Heal will be done automatically during scan
        detector.scan_all_symbols(args.timeframe)
    elif args.action == 'report':
        results = detector.get_data_completeness(args.symbol)
        print("\n=== Data Completeness Report ===\n")
        for symbol, stats in results.items():
            print(f"\n{symbol}:")
            for tf, data in stats.items():
                if 'completeness_pct' in data:
                    print(f"  {tf}: {data['completeness_pct']}% complete ({data['actual_bars']}/{data['expected_bars']} bars)")

if __name__ == "__main__":
    main()
