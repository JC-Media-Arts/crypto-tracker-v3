#!/usr/bin/env python3
"""
Generate DCA training labels from historical data.

This script:
1. Scans historical price data for DCA setup conditions
2. Simulates what would have happened if we entered
3. Labels each setup as WIN/LOSS based on outcome
4. Saves labeled data for ML training
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from dotenv import load_dotenv
from loguru import logger

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from src.strategies.dca.detector import DCADetector
from src.strategies.dca.grid import GridCalculator

# Load environment variables
load_dotenv()


class DCALabelGenerator:
    """Generate training labels for DCA strategy."""
    
    def __init__(self, supabase_client: SupabaseClient):
        """Initialize label generator."""
        self.supabase = supabase_client
        self.detector = DCADetector(supabase_client)
        self.config = self.detector.config
        self.grid_calculator = GridCalculator(self.config)
        
    def generate_labels(self, symbols: List[str], lookback_days: int = 180) -> pd.DataFrame:
        """
        Generate DCA labels from historical data.
        
        Args:
            symbols: List of symbols to process
            lookback_days: How many days of history to scan
            
        Returns:
            DataFrame with labeled setups
        """
        all_setups = []
        
        for symbol in symbols:
            logger.info(f"Processing {symbol}...")
            setups = self.find_historical_setups(symbol, lookback_days)
            
            for setup in setups:
                # Simulate outcome
                outcome = self.simulate_dca_outcome(setup, symbol)
                setup.update(outcome)
                all_setups.append(setup)
        
        df = pd.DataFrame(all_setups)
        logger.info(f"Generated {len(df)} labeled setups")
        
        if len(df) > 0:
            win_rate = (df['label'] == 'WIN').mean()
            logger.info(f"Overall win rate: {win_rate:.2%}")
        
        return df
    
    def find_historical_setups(self, symbol: str, lookback_days: int) -> List[Dict]:
        """
        Find all DCA setups in historical data.
        
        Args:
            symbol: Cryptocurrency symbol
            lookback_days: Days of history to scan
            
        Returns:
            List of setup dictionaries
        """
        setups = []
        
        # Get historical price data
        end_date = datetime.now() - timedelta(days=1)  # Don't use today's data
        start_date = end_date - timedelta(days=lookback_days)
        
        try:
            logger.info(f"Fetching data for {symbol} from {start_date} to {end_date}")
            
            # Fetch all price data for the period
            result = self.supabase.client.table('price_data')\
                .select('timestamp, price, volume')\
                .eq('symbol', symbol)\
                .gte('timestamp', start_date.isoformat())\
                .lte('timestamp', end_date.isoformat())\
                .order('timestamp')\
                .limit(300000)\
                .execute()
            
            logger.info(f"Fetched {len(result.data) if result.data else 0} records for {symbol}")
            
            # If we hit the limit, we need to paginate or use smaller chunks
            if len(result.data) == 1000:
                logger.info(f"Hit query limit, fetching in chunks for {symbol}")
                all_data = []
                chunk_hours = 12  # Fetch 12 hours at a time (720 records max)
                current_start = start_date
                
                while current_start < end_date:
                    current_end = min(current_start + timedelta(hours=chunk_hours), end_date)
                    
                    chunk_result = self.supabase.client.table('price_data')\
                        .select('timestamp, price, volume')\
                        .eq('symbol', symbol)\
                        .gte('timestamp', current_start.isoformat())\
                        .lt('timestamp', current_end.isoformat())\
                        .order('timestamp')\
                        .limit(1000)\
                        .execute()
                    
                    if chunk_result.data:
                        all_data.extend(chunk_result.data)
                        logger.debug(f"  Chunk {current_start.date()} to {current_end.date()}: {len(chunk_result.data)} records")
                    
                    current_start = current_end
                
                result.data = all_data
                logger.info(f"Total records after chunking: {len(result.data)}")
            
            if not result.data or len(result.data) < 1440:  # Need at least 1 day of data
                logger.warning(f"Insufficient data for {symbol}: only {len(result.data) if result.data else 0} records")
                return setups
            
            df = pd.DataFrame(result.data)
            # Parse timestamps with explicit format to avoid warning
            df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601')
            df = df.set_index('timestamp')
            
            # Scan for setups using rolling window
            window_size = 240  # 4 hours in minutes
            
            i = window_size
            while i < len(df) - 4320:  # Leave 3 days for outcome
                current_idx = i
                current_time = df.index[current_idx]
                current_price = df['price'].iloc[current_idx]
                
                # Calculate 4-hour high
                window_data = df.iloc[max(0, i-window_size):i+1]
                high_4h = window_data['price'].max()
                
                # Calculate drop percentage
                drop_pct = ((current_price - high_4h) / high_4h) * 100
                
                # Check if this is a valid DCA setup
                if drop_pct <= -5.0:  # 5% drop threshold
                    # Calculate additional features
                    rsi = self.calculate_rsi(df['price'].iloc[max(0, i-100):i+1])
                    volume_ratio = window_data['volume'].mean() / df['volume'].iloc[max(0, i-1440):i].mean()
                    
                    setup = {
                        'symbol': symbol,
                        'setup_time': current_time,
                        'setup_price': current_price,
                        'drop_pct': drop_pct,
                        'high_4h': high_4h,
                        'rsi': rsi,
                        'volume_ratio': volume_ratio,
                        'setup_idx': current_idx
                    }
                    
                    setups.append(setup)
                    
                    # Skip ahead to avoid overlapping setups
                    i += 60  # Skip 1 hour
                else:
                    i += 1  # Move to next minute
            
            logger.info(f"Found {len(setups)} historical setups for {symbol}")
            
        except Exception as e:
            logger.error(f"Error finding setups for {symbol}: {e}")
        
        return setups
    
    def simulate_dca_outcome(self, setup: Dict, symbol: str) -> Dict:
        """
        Simulate what would have happened with a DCA entry.
        
        Args:
            setup: Setup dictionary
            symbol: Symbol being traded
            
        Returns:
            Dictionary with outcome details
        """
        outcome = {
            'label': 'UNKNOWN',
            'pnl_pct': 0,
            'max_drawdown': 0,
            'time_to_exit': 0,
            'exit_reason': 'none'
        }
        
        try:
            # Get price data after setup
            start_time = setup['setup_time']
            end_time = start_time + timedelta(hours=72)  # Max hold time
            
            result = self.supabase.client.table('price_data')\
                .select('timestamp, price')\
                .eq('symbol', symbol)\
                .gte('timestamp', start_time.isoformat())\
                .lte('timestamp', end_time.isoformat())\
                .order('timestamp')\
                .execute()
            
            if not result.data or len(result.data) < 60:
                return outcome
            
            df = pd.DataFrame(result.data)
            df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601')
            
            # Simulate more realistic DCA grid
            # Start grid ABOVE current price since we're catching a falling knife
            # This simulates placing limit orders when we detect the drop
            entry_prices = []
            setup_price = setup['setup_price']
            
            # Place grid starting from current price going down
            # More aggressive spacing: 2% between levels
            for i in range(5):
                grid_price = setup_price * (1 - 0.02 * i)  # 0%, -2%, -4%, -6%, -8%
                # Check if price hit this level AFTER setup
                prices_after_setup = df['price'].values
                for price in prices_after_setup:
                    if price <= grid_price and grid_price not in entry_prices:
                        entry_prices.append(grid_price)
                        break
            
            if not entry_prices:
                # No entries triggered
                outcome['label'] = 'SKIP'
                return outcome
            
            # Calculate average entry
            avg_entry = np.mean(entry_prices)
            
            # Define exit levels
            take_profit = avg_entry * 1.10  # 10% profit from average entry
            # Stop loss should be below the lowest grid level
            lowest_grid = setup_price * 0.92  # 8% below setup price
            stop_loss = lowest_grid * 0.97  # 3% below lowest grid (total -11% from setup)
            
            # Check outcome
            max_price = df['price'].max()
            min_price = df['price'].min()
            
            # Calculate max drawdown from average entry
            max_drawdown = ((min_price - avg_entry) / avg_entry) * 100
            outcome['max_drawdown'] = max_drawdown
            
            # Determine exit
            for idx, row in df.iterrows():
                price = row['price']
                time_elapsed = (row['timestamp'] - start_time).total_seconds() / 3600
                
                if price >= take_profit:
                    outcome['label'] = 'WIN'
                    outcome['pnl_pct'] = 10.0
                    outcome['time_to_exit'] = time_elapsed
                    outcome['exit_reason'] = 'take_profit'
                    break
                elif price <= stop_loss:
                    outcome['label'] = 'LOSS'
                    outcome['pnl_pct'] = -8.0
                    outcome['time_to_exit'] = time_elapsed
                    outcome['exit_reason'] = 'stop_loss'
                    break
            
            # If no exit triggered, check final price
            if outcome['label'] == 'UNKNOWN':
                final_price = df['price'].iloc[-1]
                final_pnl = ((final_price - avg_entry) / avg_entry) * 100
                
                if final_pnl > 2:
                    outcome['label'] = 'WIN'
                    outcome['pnl_pct'] = final_pnl
                elif final_pnl < -2:
                    outcome['label'] = 'LOSS'
                    outcome['pnl_pct'] = final_pnl
                else:
                    outcome['label'] = 'BREAKEVEN'
                    outcome['pnl_pct'] = final_pnl
                
                outcome['time_to_exit'] = 72
                outcome['exit_reason'] = 'time_exit'
            
        except Exception as e:
            logger.error(f"Error simulating outcome: {e}")
        
        return outcome
    
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI."""
        if len(prices) < period:
            return 50.0
            
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        if loss.iloc[-1] == 0:
            return 100.0
        
        rs = gain.iloc[-1] / loss.iloc[-1]
        rsi = 100 - (100 / (1 + rs))
        
        return rsi if not pd.isna(rsi) else 50.0
    
    def save_labels(self, df: pd.DataFrame, filename: str = 'dca_training_labels.csv'):
        """Save labeled data to CSV."""
        output_path = Path('data') / filename
        output_path.parent.mkdir(exist_ok=True)
        
        df.to_csv(output_path, index=False)
        logger.info(f"Saved {len(df)} labeled setups to {output_path}")
        
        # Also save summary statistics
        if len(df) > 0:
            summary = {
                'total_setups': len(df),
                'wins': (df['label'] == 'WIN').sum(),
                'losses': (df['label'] == 'LOSS').sum(),
                'breakeven': (df['label'] == 'BREAKEVEN').sum(),
                'skipped': (df['label'] == 'SKIP').sum(),
                'win_rate': (df['label'] == 'WIN').mean(),
                'avg_win_pnl': df[df['label'] == 'WIN']['pnl_pct'].mean() if any(df['label'] == 'WIN') else 0,
                'avg_loss_pnl': df[df['label'] == 'LOSS']['pnl_pct'].mean() if any(df['label'] == 'LOSS') else 0,
                'avg_time_to_exit': df['time_to_exit'].mean()
            }
            
            print("\n" + "=" * 60)
            print("SUMMARY STATISTICS")
            print("=" * 60)
            for key, value in summary.items():
                if 'rate' in key or 'pnl' in key:
                    print(f"{key:20}: {value:.2%}" if 'rate' in key else f"{key:20}: {value:.2f}%")
                else:
                    print(f"{key:20}: {value:.1f}")


def main():
    """Generate DCA training labels."""
    print("=" * 80)
    print("DCA TRAINING LABEL GENERATOR")
    print("=" * 80)
    
    # Initialize
    supabase = SupabaseClient()
    generator = DCALabelGenerator(supabase)
    
    # Process just BTC for testing
    symbols = ['BTC']  # Test with BTC first
    # symbols = ['BTC', 'ETH', 'SOL', 'ADA', 'DOT', 'AVAX', 'LINK', 'UNI', 'ATOM', 'NEAR']
    
    print(f"\nProcessing {len(symbols)} symbols...")
    print(f"Lookback period: 180 days")
    print("-" * 40)
    
    # Generate labels
    df = generator.generate_labels(symbols, lookback_days=180)
    
    # Save results
    if len(df) > 0:
        generator.save_labels(df)
        
        # Save to database for later use
        print("\nSaving setups to database...")
        saved_count = 0
        for _, row in df.iterrows():
            if row['label'] in ['WIN', 'LOSS']:
                setup_data = {
                    'strategy_name': 'DCA',
                    'symbol': row['symbol'],
                    'detected_at': row['setup_time'].isoformat(),
                    'setup_price': float(row['setup_price']),
                    'setup_data': {
                        'drop_pct': float(row['drop_pct']),
                        'rsi': float(row['rsi']),
                        'volume_ratio': float(row['volume_ratio']),
                        'high_4h': float(row['high_4h'])
                    },
                    'outcome': row['label'],
                    'pnl': float(row['pnl_pct'])
                }
                
                try:
                    result = supabase.client.table('strategy_setups').insert(setup_data).execute()
                    if result.data:
                        saved_count += 1
                except Exception as e:
                    logger.error(f"Error saving setup: {e}")
        
        print(f"Saved {saved_count} setups to database")
    else:
        print("No setups found!")
    
    print("\n" + "=" * 80)
    print("LABEL GENERATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
