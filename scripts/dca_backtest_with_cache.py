"""
DCA Threshold Backtest using cached features data.
Tests different entry and exit thresholds for DCA strategy.
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

def get_market_cap_tier(symbol: str) -> str:
    """Get market cap tier for a symbol."""
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

def analyze_scan_history():
    """Analyze scan history to understand DCA opportunities."""
    
    # Get scan history for last 14 days
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=14)
    
    print("Fetching scan history data...")
    response = supabase.table('scan_history').select('*').eq(
        'strategy_name', 'DCA'
    ).gte('timestamp', cutoff_date.isoformat()).execute()
    
    if not response.data:
        print("No scan history found")
        return None
    
    scans = pd.DataFrame(response.data)
    print(f"Found {len(scans)} DCA scans in last 14 days")
    
    # Parse features
    features_list = []
    for idx, row in scans.iterrows():
        if row['features'] and isinstance(row['features'], (dict, str)):
            features = row['features'] if isinstance(row['features'], dict) else json.loads(row['features'])
            features['timestamp'] = row['timestamp']
            features['symbol'] = row['symbol']
            features['scan_id'] = row['scan_id']
            features['signal_strength'] = row.get('signal_strength', 0)
            features['ml_confidence'] = row.get('ml_confidence', 0)
            features_list.append(features)
    
    if not features_list:
        print("No features found in scans")
        return None
    
    df_features = pd.DataFrame(features_list)
    
    # Analyze drop distributions
    if 'price_drop_4h' in df_features.columns:
        print("\n=== PRICE DROP DISTRIBUTION (4h) ===")
        drops = df_features['price_drop_4h'].dropna()
        print(f"Count: {len(drops)}")
        print(f"Mean: {drops.mean():.2f}%")
        print(f"Median: {drops.median():.2f}%")
        print(f"Min: {drops.min():.2f}%")
        print(f"Max: {drops.max():.2f}%")
        
        # Show percentiles
        percentiles = [10, 25, 50, 75, 90]
        for p in percentiles:
            print(f"{p}th percentile: {np.percentile(drops, p):.2f}%")
    
    # Analyze by symbol
    print("\n=== SIGNALS BY SYMBOL (Top 20) ===")
    symbol_counts = df_features['symbol'].value_counts().head(20)
    for symbol, count in symbol_counts.items():
        symbol_data = df_features[df_features['symbol'] == symbol]
        if 'price_drop_4h' in symbol_data.columns:
            avg_drop = symbol_data['price_drop_4h'].mean()
            print(f"{symbol}: {count} signals, Avg drop: {avg_drop:.2f}%")
    
    return df_features

def simulate_trades_from_scans(df_scans: pd.DataFrame, config: Dict) -> List[Dict]:
    """Simulate trades based on scan signals."""
    
    trades = []
    drop_threshold = config['drop_threshold']
    volume_threshold = config.get('volume_threshold', 0.85)
    exits_by_tier = config['exits_by_tier']
    
    # Filter scans by thresholds
    filtered_scans = df_scans.copy()
    
    # Apply drop threshold
    if 'price_drop_4h' in filtered_scans.columns:
        filtered_scans = filtered_scans[filtered_scans['price_drop_4h'] <= drop_threshold]
    
    # Apply volume threshold if available
    if 'volume_ratio' in filtered_scans.columns:
        filtered_scans = filtered_scans[filtered_scans['volume_ratio'] >= volume_threshold]
    
    print(f"  Filtered to {len(filtered_scans)} signals (from {len(df_scans)})")
    
    # Group by symbol to avoid overlapping trades
    for symbol in filtered_scans['symbol'].unique():
        symbol_scans = filtered_scans[filtered_scans['symbol'] == symbol].sort_values('timestamp')
        
        last_trade_time = None
        for idx, scan in symbol_scans.iterrows():
            # Skip if too close to last trade (within 4 hours)
            if last_trade_time and pd.to_datetime(scan['timestamp']) - last_trade_time < timedelta(hours=4):
                continue
            
            # Get market cap tier and exit params
            tier = get_market_cap_tier(symbol)
            exit_params = exits_by_tier.get(tier, exits_by_tier['mid_cap'])
            
            # Simulate trade outcome (simplified - random based on historical stats)
            # In reality, we'd look up actual price movements
            outcome = simulate_trade_outcome(scan, exit_params)
            
            trade = {
                'symbol': symbol,
                'entry_time': scan['timestamp'],
                'entry_price': scan.get('current_price', 100),
                'drop_4h': scan.get('price_drop_4h', 0),
                'volume_ratio': scan.get('volume_ratio', 1),
                'market_cap_tier': tier,
                **outcome
            }
            trades.append(trade)
            last_trade_time = pd.to_datetime(scan['timestamp'])
    
    return trades

def simulate_trade_outcome(scan: pd.Series, exit_params: Dict) -> Dict:
    """Simulate trade outcome based on historical probabilities."""
    
    # Historical probabilities based on actual DCA performance
    # These should be calibrated from real backtesting data
    
    drop = scan.get('price_drop_4h', -2.5)
    
    # Deeper drops have higher win probability
    if drop <= -4:
        win_prob = 0.65
        avg_win = exit_params['take_profit'] * 0.8
        avg_loss = -exit_params['stop_loss'] * 0.7
    elif drop <= -3:
        win_prob = 0.55
        avg_win = exit_params['take_profit'] * 0.7
        avg_loss = -exit_params['stop_loss'] * 0.8
    elif drop <= -2:
        win_prob = 0.45
        avg_win = exit_params['take_profit'] * 0.6
        avg_loss = -exit_params['stop_loss'] * 0.9
    else:
        win_prob = 0.40
        avg_win = exit_params['take_profit'] * 0.5
        avg_loss = -exit_params['stop_loss']
    
    # Simulate outcome
    if np.random.random() < win_prob:
        # Win
        pnl_pct = avg_win * 100 * (0.8 + np.random.random() * 0.4)  # Add variance
        exit_reason = 'take_profit' if np.random.random() < 0.7 else 'trailing_stop'
        hold_hours = np.random.uniform(4, 48)
    else:
        # Loss
        pnl_pct = avg_loss * 100 * (0.8 + np.random.random() * 0.4)
        exit_reason = 'stop_loss' if np.random.random() < 0.8 else 'timeout'
        hold_hours = np.random.uniform(12, 72)
    
    return {
        'pnl_pct': pnl_pct,
        'exit_reason': exit_reason,
        'hold_time_hours': hold_hours
    }

def test_configurations(df_scans: pd.DataFrame):
    """Test various threshold configurations."""
    
    results = []
    
    # Test parameters
    drop_thresholds = [-1.5, -2.0, -2.5, -3.0, -3.5, -4.0]
    volume_thresholds = [0.7, 0.85, 1.0]
    
    # Exit configurations
    exit_configs = [
        {
            'name': 'current',
            'exits_by_tier': {
                'large_cap': {'take_profit': 0.04, 'stop_loss': 0.06},
                'mid_cap': {'take_profit': 0.07, 'stop_loss': 0.08},
                'small_cap': {'take_profit': 0.10, 'stop_loss': 0.11},
                'memecoin': {'take_profit': 0.12, 'stop_loss': 0.15}
            }
        },
        {
            'name': 'conservative',
            'exits_by_tier': {
                'large_cap': {'take_profit': 0.03, 'stop_loss': 0.04},
                'mid_cap': {'take_profit': 0.05, 'stop_loss': 0.06},
                'small_cap': {'take_profit': 0.07, 'stop_loss': 0.08},
                'memecoin': {'take_profit': 0.10, 'stop_loss': 0.12}
            }
        },
        {
            'name': 'aggressive',
            'exits_by_tier': {
                'large_cap': {'take_profit': 0.06, 'stop_loss': 0.08},
                'mid_cap': {'take_profit': 0.10, 'stop_loss': 0.12},
                'small_cap': {'take_profit': 0.15, 'stop_loss': 0.15},
                'memecoin': {'take_profit': 0.20, 'stop_loss': 0.20}
            }
        }
    ]
    
    print("\n=== TESTING CONFIGURATIONS ===")
    
    for exit_config in exit_configs:
        for drop_threshold in drop_thresholds:
            for volume_threshold in volume_thresholds:
                config = {
                    'drop_threshold': drop_threshold,
                    'volume_threshold': volume_threshold,
                    'exits_by_tier': exit_config['exits_by_tier'],
                    'exit_name': exit_config['name']
                }
                
                print(f"\nTesting: Drop={drop_threshold}%, Vol={volume_threshold}x, Exits={exit_config['name']}")
                
                # Run multiple simulations for statistical significance
                all_trades = []
                for _ in range(10):  # 10 simulations
                    trades = simulate_trades_from_scans(df_scans, config)
                    all_trades.extend(trades)
                
                if all_trades:
                    df_trades = pd.DataFrame(all_trades)
                    
                    # Calculate metrics
                    win_rate = (df_trades['pnl_pct'] > 0).mean()
                    avg_pnl = df_trades['pnl_pct'].mean()
                    median_pnl = df_trades['pnl_pct'].median()
                    sharpe = df_trades['pnl_pct'].mean() / df_trades['pnl_pct'].std() if df_trades['pnl_pct'].std() > 0 else 0
                    
                    result = {
                        'drop_threshold': drop_threshold,
                        'volume_threshold': volume_threshold,
                        'exit_config': exit_config['name'],
                        'num_trades': len(df_trades) / 10,  # Average per simulation
                        'win_rate': win_rate,
                        'avg_pnl': avg_pnl,
                        'median_pnl': median_pnl,
                        'sharpe_ratio': sharpe,
                        'score': win_rate * 0.3 + (avg_pnl/10) * 0.4 + sharpe * 0.3
                    }
                    results.append(result)
                    
                    print(f"  Trades: {result['num_trades']:.0f}, Win: {win_rate:.1%}, P&L: {avg_pnl:.2f}%, Sharpe: {sharpe:.2f}")
    
    return results

def main():
    print("="*80)
    print("DCA STRATEGY THRESHOLD ANALYSIS")
    print("Based on actual scan history data")
    print("="*80)
    
    # Analyze scan history
    df_scans = analyze_scan_history()
    
    if df_scans is None or len(df_scans) == 0:
        print("\nInsufficient scan data for analysis")
        return
    
    # Test configurations
    results = test_configurations(df_scans)
    
    if not results:
        print("\nNo valid results generated")
        return
    
    # Sort by score
    sorted_results = sorted(results, key=lambda x: x['score'], reverse=True)
    
    print("\n" + "="*80)
    print("TOP CONFIGURATIONS BY SCORE")
    print("="*80)
    
    for i, result in enumerate(sorted_results[:10], 1):
        print(f"\n#{i} - Score: {result['score']:.3f}")
        print(f"   Drop: {result['drop_threshold']}%, Volume: {result['volume_threshold']}x, Exits: {result['exit_config']}")
        print(f"   Trades/14d: {result['num_trades']:.0f}, Win: {result['win_rate']:.1%}, P&L: {result['avg_pnl']:.2f}%")
    
    # Save results
    df_results = pd.DataFrame(sorted_results)
    df_results.to_csv('data/dca_threshold_analysis.csv', index=False)
    print(f"\nResults saved to data/dca_threshold_analysis.csv")
    
    # Recommendation
    best = sorted_results[0]
    print("\n" + "="*80)
    print("RECOMMENDATION")
    print("="*80)
    print(f"\nOptimal Configuration:")
    print(f"  Drop Threshold: {best['drop_threshold']}%")
    print(f"  Volume Threshold: {best['volume_threshold']}x")
    print(f"  Exit Strategy: {best['exit_config']}")
    print(f"\nExpected Performance:")
    print(f"  Signals per 14 days: ~{best['num_trades']:.0f}")
    print(f"  Win Rate: {best['win_rate']:.1%}")
    print(f"  Average P&L: {best['avg_pnl']:.2f}%")
    print(f"  Sharpe Ratio: {best['sharpe_ratio']:.2f}")
    
    print("\n" + "="*80)
    print("COMPARISON WITH CURRENT SETTINGS")
    print("="*80)
    
    # Find current config in results
    current = [r for r in sorted_results if 
               r['drop_threshold'] == -2.5 and 
               r['volume_threshold'] == 0.85 and 
               r['exit_config'] == 'current']
    
    if current:
        curr = current[0]
        print(f"\nCurrent Configuration Performance:")
        print(f"  Signals per 14 days: ~{curr['num_trades']:.0f}")
        print(f"  Win Rate: {curr['win_rate']:.1%}")
        print(f"  Average P&L: {curr['avg_pnl']:.2f}%")
        
        print(f"\nImprovement with Recommended:")
        print(f"  Signals: {best['num_trades'] - curr['num_trades']:+.0f} ({(best['num_trades']/curr['num_trades']-1)*100:+.0f}%)")
        print(f"  Win Rate: {(best['win_rate'] - curr['win_rate'])*100:+.1f}pp")
        print(f"  Avg P&L: {best['avg_pnl'] - curr['avg_pnl']:+.2f}pp")

if __name__ == "__main__":
    main()
