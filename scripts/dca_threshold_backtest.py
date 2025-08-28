"""
DCA Threshold Backtest Script
Tests different entry and exit thresholds for DCA strategy over the last 14 days.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
import json
from supabase import create_client, Client
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

class DCABacktester:
    def __init__(self, days_back: int = 14):
        self.days_back = days_back
        self.start_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        self.end_date = datetime.now(timezone.utc)
        self.ohlc_data = {}
        self.results = []
        
    def load_data(self):
        """Load OHLC data for all symbols."""
        print(f"Loading OHLC data for the last {self.days_back} days...")
        
        # Get list of actively traded symbols
        symbols_response = supabase.table('ohlc_data').select('symbol').gte(
            'timestamp', self.start_date.isoformat()
        ).execute()
        
        symbols = list(set([row['symbol'] for row in symbols_response.data]))
        print(f"Found {len(symbols)} symbols with data")
        
        # Load OHLC data for each symbol
        for symbol in symbols[:90]:  # Limit to top 90 symbols as in production
            response = supabase.table('ohlc_data').select('*').eq(
                'symbol', symbol
            ).eq('timeframe', '15m').gte(
                'timestamp', self.start_date.isoformat()
            ).order('timestamp', desc=False).execute()
            
            if response.data:
                df = pd.DataFrame(response.data)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.set_index('timestamp')
                self.ohlc_data[symbol] = df
        
        print(f"Loaded data for {len(self.ohlc_data)} symbols")
    
    def calculate_features(self, symbol: str, timestamp: datetime) -> Dict:
        """Calculate features for a given symbol at a timestamp."""
        if symbol not in self.ohlc_data:
            return None
            
        df = self.ohlc_data[symbol]
        
        # Get data up to this timestamp
        current_data = df[df.index <= timestamp]
        
        if len(current_data) < 20:  # Need enough data for calculations
            return None
            
        features = {}
        
        # Current price
        current_price = current_data.iloc[-1]['close']
        
        # Calculate price drops from various timeframes
        for hours in [1, 2, 4, 8, 12, 24]:
            lookback = current_data.iloc[-hours*4:] if len(current_data) >= hours*4 else current_data
            if len(lookback) > 0:
                high = lookback['high'].max()
                drop_pct = ((current_price - high) / high) * 100
                features[f'drop_{hours}h'] = drop_pct
        
        # Volume metrics
        if 'volume' in current_data.columns:
            recent_volume = current_data.iloc[-4:]['volume'].mean()
            avg_volume = current_data.iloc[-96:]['volume'].mean() if len(current_data) >= 96 else current_data['volume'].mean()
            features['volume_ratio'] = recent_volume / avg_volume if avg_volume > 0 else 1
            features['volume_24h'] = current_data.iloc[-96:]['volume'].sum() if len(current_data) >= 96 else 0
        else:
            features['volume_ratio'] = 1
            features['volume_24h'] = 100000  # Default value
        
        # RSI
        close_prices = current_data['close'].iloc[-14:]
        if len(close_prices) >= 14:
            delta = close_prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            features['rsi'] = 100 - (100 / (1 + rs.iloc[-1]))
        else:
            features['rsi'] = 50
        
        # Volatility
        if len(current_data) >= 20:
            returns = current_data['close'].pct_change().dropna()
            features['volatility'] = returns.std() * np.sqrt(96) * 100  # Daily volatility
        else:
            features['volatility'] = 5
            
        features['current_price'] = current_price
        
        return features
    
    def check_dca_signal(self, features: Dict, drop_threshold: float, volume_threshold: float) -> bool:
        """Check if DCA entry conditions are met."""
        if features is None:
            return False
            
        # Check price drop (use 4h drop as primary)
        drop_4h = features.get('drop_4h', 0)
        if drop_4h >= drop_threshold:  # More negative than threshold
            return False
            
        # Check volume requirement
        volume_ratio = features.get('volume_ratio', 1)
        volume_24h = features.get('volume_24h', 0)
        
        if volume_ratio < volume_threshold or volume_24h < 100000:
            return False
            
        # Check RSI not oversold
        rsi = features.get('rsi', 50)
        if rsi < 20:  # Extremely oversold, might drop more
            return False
            
        return True
    
    def simulate_trade(self, entry_price: float, symbol: str, entry_time: datetime, 
                      take_profit: float, stop_loss: float, market_cap_tier: str) -> Dict:
        """Simulate a trade from entry to exit."""
        df = self.ohlc_data[symbol]
        future_data = df[df.index > entry_time]
        
        if len(future_data) == 0:
            return None
            
        # Track the trade
        highest_price = entry_price
        for idx, row in future_data.iterrows():
            current_price = row['close']
            high_price = row['high']
            low_price = row['low']
            
            # Update highest price for trailing stop
            if high_price > highest_price:
                highest_price = high_price
            
            # Check take profit
            if high_price >= entry_price * (1 + take_profit):
                hold_time = (idx - entry_time).total_seconds() / 3600
                return {
                    'exit_price': entry_price * (1 + take_profit),
                    'exit_reason': 'take_profit',
                    'pnl_pct': take_profit * 100,
                    'hold_time_hours': hold_time,
                    'exit_time': idx
                }
            
            # Check stop loss
            if low_price <= entry_price * (1 - stop_loss):
                hold_time = (idx - entry_time).total_seconds() / 3600
                return {
                    'exit_price': entry_price * (1 - stop_loss),
                    'exit_reason': 'stop_loss',
                    'pnl_pct': -stop_loss * 100,
                    'hold_time_hours': hold_time,
                    'exit_time': idx
                }
            
            # Check trailing stop (simplified - activate after 2% gain)
            if highest_price > entry_price * 1.02:
                trailing_stop_price = highest_price * 0.98  # 2% trailing
                if low_price <= trailing_stop_price:
                    hold_time = (idx - entry_time).total_seconds() / 3600
                    actual_pnl = ((trailing_stop_price - entry_price) / entry_price) * 100
                    return {
                        'exit_price': trailing_stop_price,
                        'exit_reason': 'trailing_stop',
                        'pnl_pct': actual_pnl,
                        'hold_time_hours': hold_time,
                        'exit_time': idx
                    }
            
            # Check timeout (72 hours)
            hold_time = (idx - entry_time).total_seconds() / 3600
            if hold_time >= 72:
                actual_pnl = ((current_price - entry_price) / entry_price) * 100
                return {
                    'exit_price': current_price,
                    'exit_reason': 'timeout',
                    'pnl_pct': actual_pnl,
                    'hold_time_hours': hold_time,
                    'exit_time': idx
                }
        
        # Trade still open at end of backtest
        last_price = future_data.iloc[-1]['close']
        hold_time = (future_data.index[-1] - entry_time).total_seconds() / 3600
        actual_pnl = ((last_price - entry_price) / entry_price) * 100
        return {
            'exit_price': last_price,
            'exit_reason': 'open',
            'pnl_pct': actual_pnl,
            'hold_time_hours': hold_time,
            'exit_time': future_data.index[-1]
        }
    
    def get_market_cap_tier(self, symbol: str) -> str:
        """Get market cap tier for a symbol."""
        # Simplified tier assignment
        large_cap = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA']
        small_cap = ['SHIB', 'DOGE', 'TRX', 'APT']
        memecoins = ['PEPE', 'WIF', 'BONK', 'FLOKI', 'MEME', 'POPCAT', 'MEW', 
                     'TURBO', 'NEIRO', 'PNUT', 'GOAT', 'ACT', 'TRUMP', 
                     'FARTCOIN', 'MOG', 'PONKE', 'TREMP', 'BRETT', 'GIGA', 'HIPPO']
        
        if symbol in large_cap:
            return 'large_cap'
        elif symbol in small_cap:
            return 'small_cap'
        elif symbol in memecoins:
            return 'memecoin'
        else:
            return 'mid_cap'
    
    def run_backtest(self, config: Dict) -> Dict:
        """Run backtest with given configuration."""
        trades = []
        
        # Extract parameters
        drop_threshold = config['drop_threshold']
        volume_threshold = config['volume_threshold']
        exits_by_tier = config['exits_by_tier']
        
        print(f"\nTesting: Drop={drop_threshold}%, Volume={volume_threshold}x")
        
        # Scan through time
        for symbol, df in self.ohlc_data.items():
            # Sample every 4 hours to avoid overlapping trades
            timestamps = df.index[::16]  # Every 4 hours (16 * 15min)
            
            for timestamp in timestamps:
                features = self.calculate_features(symbol, timestamp)
                
                if self.check_dca_signal(features, drop_threshold, volume_threshold):
                    # Found a signal, simulate the trade
                    market_cap_tier = self.get_market_cap_tier(symbol)
                    exit_params = exits_by_tier.get(market_cap_tier, exits_by_tier['mid_cap'])
                    
                    trade_result = self.simulate_trade(
                        features['current_price'],
                        symbol,
                        timestamp,
                        exit_params['take_profit'],
                        exit_params['stop_loss'],
                        market_cap_tier
                    )
                    
                    if trade_result:
                        trades.append({
                            'symbol': symbol,
                            'entry_time': timestamp,
                            'entry_price': features['current_price'],
                            'drop_4h': features.get('drop_4h', 0),
                            'volume_ratio': features.get('volume_ratio', 1),
                            'rsi': features.get('rsi', 50),
                            'market_cap_tier': market_cap_tier,
                            **trade_result
                        })
        
        # Calculate statistics
        if trades:
            df_trades = pd.DataFrame(trades)
            completed = df_trades[df_trades['exit_reason'] != 'open']
            
            if len(completed) > 0:
                win_rate = (completed['pnl_pct'] > 0).mean()
                avg_pnl = completed['pnl_pct'].mean()
                median_pnl = completed['pnl_pct'].median()
                sharpe = completed['pnl_pct'].mean() / completed['pnl_pct'].std() if completed['pnl_pct'].std() > 0 else 0
                max_win = completed['pnl_pct'].max()
                max_loss = completed['pnl_pct'].min()
                avg_hold = completed['hold_time_hours'].mean()
                
                # Exit reason breakdown
                exit_counts = completed['exit_reason'].value_counts().to_dict()
                
                # Tier breakdown
                tier_stats = {}
                for tier in completed['market_cap_tier'].unique():
                    tier_trades = completed[completed['market_cap_tier'] == tier]
                    tier_stats[tier] = {
                        'count': len(tier_trades),
                        'win_rate': (tier_trades['pnl_pct'] > 0).mean(),
                        'avg_pnl': tier_trades['pnl_pct'].mean()
                    }
                
                return {
                    'config': config,
                    'total_signals': len(trades),
                    'completed_trades': len(completed),
                    'open_trades': len(df_trades[df_trades['exit_reason'] == 'open']),
                    'win_rate': win_rate,
                    'avg_pnl': avg_pnl,
                    'median_pnl': median_pnl,
                    'sharpe_ratio': sharpe,
                    'max_win': max_win,
                    'max_loss': max_loss,
                    'avg_hold_hours': avg_hold,
                    'exit_reasons': exit_counts,
                    'tier_performance': tier_stats,
                    'trades': trades  # Store individual trades for analysis
                }
            else:
                return {
                    'config': config,
                    'total_signals': len(trades),
                    'completed_trades': 0,
                    'open_trades': len(trades),
                    'win_rate': 0,
                    'avg_pnl': 0,
                    'median_pnl': 0,
                    'sharpe_ratio': 0,
                    'max_win': 0,
                    'max_loss': 0,
                    'avg_hold_hours': 0,
                    'exit_reasons': {},
                    'tier_performance': {},
                    'trades': trades
                }
        else:
            return {
                'config': config,
                'total_signals': 0,
                'completed_trades': 0,
                'open_trades': 0,
                'win_rate': 0,
                'avg_pnl': 0,
                'median_pnl': 0,
                'sharpe_ratio': 0,
                'max_win': 0,
                'max_loss': 0,
                'avg_hold_hours': 0,
                'exit_reasons': {},
                'tier_performance': {},
                'trades': []
            }
    
    def test_threshold_combinations(self):
        """Test various threshold combinations."""
        # Define test ranges
        drop_thresholds = [-1.5, -2.0, -2.5, -3.0, -3.5, -4.0, -4.5, -5.0]
        volume_thresholds = [0.7, 0.8, 0.85, 0.9, 1.0, 1.1]
        
        # Define exit parameters by tier (testing current config and variations)
        exit_configs = [
            {  # Current config
                'name': 'current',
                'exits_by_tier': {
                    'large_cap': {'take_profit': 0.04, 'stop_loss': 0.06},
                    'mid_cap': {'take_profit': 0.07, 'stop_loss': 0.08},
                    'small_cap': {'take_profit': 0.10, 'stop_loss': 0.11},
                    'memecoin': {'take_profit': 0.12, 'stop_loss': 0.15}
                }
            },
            {  # Tighter exits
                'name': 'tight',
                'exits_by_tier': {
                    'large_cap': {'take_profit': 0.03, 'stop_loss': 0.04},
                    'mid_cap': {'take_profit': 0.05, 'stop_loss': 0.06},
                    'small_cap': {'take_profit': 0.07, 'stop_loss': 0.08},
                    'memecoin': {'take_profit': 0.10, 'stop_loss': 0.12}
                }
            },
            {  # Wider exits
                'name': 'wide',
                'exits_by_tier': {
                    'large_cap': {'take_profit': 0.05, 'stop_loss': 0.08},
                    'mid_cap': {'take_profit': 0.09, 'stop_loss': 0.10},
                    'small_cap': {'take_profit': 0.12, 'stop_loss': 0.15},
                    'memecoin': {'take_profit': 0.15, 'stop_loss': 0.20}
                }
            }
        ]
        
        all_results = []
        
        for exit_config in exit_configs:
            for drop_threshold in drop_thresholds:
                for volume_threshold in volume_thresholds:
                    config = {
                        'drop_threshold': drop_threshold,
                        'volume_threshold': volume_threshold,
                        'exits_by_tier': exit_config['exits_by_tier'],
                        'exit_config_name': exit_config['name']
                    }
                    
                    result = self.run_backtest(config)
                    all_results.append(result)
        
        return all_results
    
    def analyze_results(self, results: List[Dict]):
        """Analyze and rank backtest results."""
        # Filter results with at least 10 completed trades
        valid_results = [r for r in results if r['completed_trades'] >= 10]
        
        if not valid_results:
            print("\nNo configurations produced enough trades for analysis")
            return
        
        # Sort by multiple criteria
        # Primary: Sharpe ratio (risk-adjusted returns)
        # Secondary: Win rate
        # Tertiary: Average P&L
        
        for r in valid_results:
            # Calculate a composite score
            r['score'] = (
                r['sharpe_ratio'] * 0.4 +  # Risk-adjusted returns
                r['win_rate'] * 0.3 +       # Consistency
                (r['avg_pnl'] / 10) * 0.3   # Raw performance
            )
        
        sorted_results = sorted(valid_results, key=lambda x: x['score'], reverse=True)
        
        print("\n" + "="*80)
        print("TOP 10 CONFIGURATIONS BY COMPOSITE SCORE")
        print("="*80)
        
        for i, result in enumerate(sorted_results[:10], 1):
            config = result['config']
            print(f"\n#{i} - Score: {result['score']:.3f}")
            print(f"   Drop Threshold: {config['drop_threshold']}%")
            print(f"   Volume Threshold: {config['volume_threshold']}x")
            print(f"   Exit Config: {config['exit_config_name']}")
            print(f"   Signals: {result['total_signals']}, Completed: {result['completed_trades']}")
            print(f"   Win Rate: {result['win_rate']:.1%}")
            print(f"   Avg P&L: {result['avg_pnl']:.2f}%")
            print(f"   Sharpe: {result['sharpe_ratio']:.2f}")
            print(f"   Avg Hold: {result['avg_hold_hours']:.1f}h")
            
            # Show exit breakdown
            exit_reasons = result['exit_reasons']
            if exit_reasons:
                exit_str = ", ".join([f"{k}: {v}" for k, v in exit_reasons.items()])
                print(f"   Exits: {exit_str}")
        
        # Save detailed results
        df_results = pd.DataFrame([{
            'drop_threshold': r['config']['drop_threshold'],
            'volume_threshold': r['config']['volume_threshold'],
            'exit_config': r['config']['exit_config_name'],
            'total_signals': r['total_signals'],
            'completed_trades': r['completed_trades'],
            'win_rate': r['win_rate'],
            'avg_pnl': r['avg_pnl'],
            'median_pnl': r['median_pnl'],
            'sharpe_ratio': r['sharpe_ratio'],
            'max_win': r['max_win'],
            'max_loss': r['max_loss'],
            'avg_hold_hours': r['avg_hold_hours'],
            'score': r.get('score', 0)
        } for r in valid_results])
        
        df_results.to_csv('data/dca_backtest_results.csv', index=False)
        print(f"\nDetailed results saved to data/dca_backtest_results.csv")
        
        return sorted_results[0] if sorted_results else None

def main():
    print("="*80)
    print("DCA STRATEGY THRESHOLD OPTIMIZATION BACKTEST")
    print(f"Testing Period: Last 14 days")
    print("="*80)
    
    backtester = DCABacktester(days_back=14)
    
    # Load historical data
    backtester.load_data()
    
    # Test various threshold combinations
    print("\nTesting threshold combinations...")
    results = backtester.test_threshold_combinations()
    
    # Analyze and rank results
    best_config = backtester.analyze_results(results)
    
    if best_config:
        print("\n" + "="*80)
        print("RECOMMENDED CONFIGURATION")
        print("="*80)
        config = best_config['config']
        print(f"\nDrop Threshold: {config['drop_threshold']}%")
        print(f"Volume Threshold: {config['volume_threshold']}x")
        print(f"Exit Config: {config['exit_config_name']}")
        print(f"\nExpected Performance:")
        print(f"  Win Rate: {best_config['win_rate']:.1%}")
        print(f"  Avg P&L: {best_config['avg_pnl']:.2f}%")
        print(f"  Sharpe Ratio: {best_config['sharpe_ratio']:.2f}")
        print(f"  Signals per 14 days: {best_config['total_signals']}")
        
        # Compare with current paper trading
        print("\n" + "="*80)
        print("COMPARISON WITH CURRENT PAPER TRADING")
        print("="*80)
        print("\nCurrent Paper Trading (last 14 days):")
        print("  Configuration: Drop=-2.5%, Volume=0.85x")
        print("  Completed Trades: 5")
        print("  Win Rate: 40.0%")
        print("  Avg P&L: 0.07%")
        
        print(f"\nBacktest with current config:")
        # Find result with current config
        current_results = [r for r in results if 
                          r['config']['drop_threshold'] == -2.5 and 
                          r['config']['volume_threshold'] == 0.85 and
                          r['config']['exit_config_name'] == 'current']
        if current_results:
            curr = current_results[0]
            print(f"  Signals Found: {curr['total_signals']}")
            print(f"  Completed Trades: {curr['completed_trades']}")
            print(f"  Win Rate: {curr['win_rate']:.1%}")
            print(f"  Avg P&L: {curr['avg_pnl']:.2f}%")

if __name__ == "__main__":
    main()
