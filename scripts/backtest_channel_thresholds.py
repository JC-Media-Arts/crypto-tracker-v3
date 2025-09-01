#!/usr/bin/env python3
"""
CHANNEL Strategy Threshold Optimization Backtest
Analyzes 7 days of data to find optimal buy/sell zones for each market cap tier
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from src.config.config_loader import ConfigLoader
from loguru import logger

class ChannelBacktester:
    def __init__(self):
        self.client = SupabaseClient()
        self.config_loader = ConfigLoader()
        self.lookback_days = 7
        self.channel_period = 20  # 20-period channel
        
        # Test ranges
        self.buy_zone_range = np.arange(0.01, 0.11, 0.005)  # 1% to 10% in 0.5% steps
        self.sell_zone_range = np.arange(0.01, 0.11, 0.005)  # 1% to 10% in 0.5% steps
        
        # Market cap tiers and their symbols
        self.tiers = {
            'large_cap': ['BTC', 'ETH', 'SOL', 'BNB', 'XRP'],
            'mid_cap': ['AVAX', 'DOT', 'LINK', 'MATIC', 'UNI', 'NEAR', 'ATOM'],
            'small_cap': ['FTM', 'SAND', 'MANA', 'AAVE', 'CRV', 'SNX', 'LDO'],
            'memecoin': ['DOGE', 'SHIB', 'PEPE', 'FLOKI', 'WIF', 'BONK']
        }
        
    def fetch_ohlc_data(self, symbol: str) -> pd.DataFrame:
        """Fetch 7 days + channel period of OHLC data"""
        try:
            # Need extra days for channel calculation
            start_date = datetime.now(timezone.utc) - timedelta(days=self.lookback_days + self.channel_period)
            
            response = self.client.client.table('ohlc_data').select(
                'timestamp,open,high,low,close,volume'
            ).eq('symbol', symbol).gte('timestamp', start_date.isoformat()).order('timestamp').execute()
            
            if not response.data:
                return pd.DataFrame()
                
            df = pd.DataFrame(response.data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            
            # Convert to 15-minute bars for better signal quality
            df_15m = df.resample('15T').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
            
            return df_15m
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()
    
    def calculate_channel(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate channel indicators"""
        df = df.copy()
        
        # Calculate channel bounds
        df['channel_high'] = df['high'].rolling(window=self.channel_period).max()
        df['channel_low'] = df['low'].rolling(window=self.channel_period).min()
        df['channel_mid'] = (df['channel_high'] + df['channel_low']) / 2
        df['channel_width'] = (df['channel_high'] - df['channel_low']) / df['channel_mid']
        
        # Calculate position in channel (0 = bottom, 1 = top)
        df['channel_position'] = (df['close'] - df['channel_low']) / (df['channel_high'] - df['channel_low'])
        
        # Drop NaN rows from rolling calculations
        df.dropna(inplace=True)
        
        return df
    
    def backtest_thresholds(self, df: pd.DataFrame, buy_zone: float, sell_zone: float) -> Dict:
        """Backtest specific threshold combination"""
        if df.empty or len(df) < 100:  # Need minimum data
            return {'trades': 0, 'win_rate': 0, 'avg_profit': 0, 'total_profit': 0, 'sharpe': 0, 'max_dd': 0}
        
        trades = []
        position = None
        
        for idx, row in df.iterrows():
            # Entry logic
            if position is None:
                # Buy when price is below mid-channel by buy_zone percentage
                buy_threshold = row['channel_mid'] * (1 - buy_zone)
                if row['close'] <= buy_threshold and row['channel_width'] > 0.02:  # Min 2% channel width
                    position = {
                        'entry_time': idx,
                        'entry_price': row['close'],
                        'channel_mid': row['channel_mid']
                    }
            
            # Exit logic
            elif position is not None:
                # Sell when price is above mid-channel by sell_zone percentage
                sell_threshold = position['channel_mid'] * (1 + sell_zone)
                stop_loss = position['entry_price'] * 0.95  # 5% stop loss
                
                if row['close'] >= sell_threshold or row['close'] <= stop_loss:
                    profit = (row['close'] - position['entry_price']) / position['entry_price']
                    trades.append({
                        'entry_time': position['entry_time'],
                        'exit_time': idx,
                        'entry_price': position['entry_price'],
                        'exit_price': row['close'],
                        'profit': profit,
                        'win': profit > 0
                    })
                    position = None
        
        if len(trades) == 0:
            return {'trades': 0, 'win_rate': 0, 'avg_profit': 0, 'total_profit': 0, 'sharpe': 0, 'max_dd': 0}
        
        # Calculate metrics
        trades_df = pd.DataFrame(trades)
        
        metrics = {
            'trades': len(trades),
            'win_rate': trades_df['win'].mean() * 100,
            'avg_profit': trades_df['profit'].mean() * 100,
            'total_profit': trades_df['profit'].sum() * 100,
            'sharpe': self.calculate_sharpe(trades_df['profit']),
            'max_dd': self.calculate_max_drawdown(trades_df['profit'])
        }
        
        return metrics
    
    def calculate_sharpe(self, returns: pd.Series) -> float:
        """Calculate Sharpe ratio"""
        if len(returns) < 2:
            return 0
        return (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
    
    def calculate_max_drawdown(self, returns: pd.Series) -> float:
        """Calculate maximum drawdown"""
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        return drawdown.min() * 100
    
    def optimize_tier(self, tier_name: str, symbols: List[str]) -> Dict:
        """Optimize thresholds for a specific tier"""
        logger.info(f"\nOptimizing {tier_name} tier with symbols: {symbols}")
        
        # Aggregate results across all symbols
        all_results = []
        
        for symbol in symbols:
            logger.info(f"  Fetching data for {symbol}...")
            df = self.fetch_ohlc_data(symbol)
            
            if df.empty:
                logger.warning(f"  No data for {symbol}, skipping")
                continue
                
            df = self.calculate_channel(df)
            
            # Only use last 7 days for backtest
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.lookback_days)
            df = df[df.index >= cutoff_date]
            
            logger.info(f"  Testing {symbol} with {len(df)} data points...")
            
            # Test all combinations
            for buy_zone in self.buy_zone_range:
                for sell_zone in self.sell_zone_range:
                    metrics = self.backtest_thresholds(df, buy_zone, sell_zone)
                    metrics['symbol'] = symbol
                    metrics['buy_zone'] = buy_zone
                    metrics['sell_zone'] = sell_zone
                    all_results.append(metrics)
        
        if not all_results:
            return {}
        
        # Convert to DataFrame for analysis
        results_df = pd.DataFrame(all_results)
        
        # Filter out combinations with too few trades
        min_trades = 3 * len(symbols)  # At least 3 trades per symbol average
        results_df = results_df.groupby(['buy_zone', 'sell_zone']).agg({
            'trades': 'sum',
            'win_rate': 'mean',
            'avg_profit': 'mean',
            'total_profit': 'mean',
            'sharpe': 'mean',
            'max_dd': 'mean'
        }).reset_index()
        
        results_df = results_df[results_df['trades'] >= min_trades]
        
        if results_df.empty:
            logger.warning(f"No valid combinations found for {tier_name}")
            return {}
        
        # Find conservative option (high win rate, low drawdown)
        conservative_score = (
            results_df['win_rate'] * 0.5 +  # 50% weight on win rate
            (100 + results_df['max_dd']) * 0.3 +  # 30% weight on low drawdown (inverted)
            results_df['sharpe'] * 10 * 0.2  # 20% weight on Sharpe ratio
        )
        conservative_idx = conservative_score.idxmax()
        conservative = results_df.iloc[conservative_idx]
        
        # Find aggressive option (high profit, acceptable risk)
        # Filter for minimum 50% win rate for aggressive
        aggressive_df = results_df[results_df['win_rate'] >= 50]
        if not aggressive_df.empty:
            aggressive_score = (
                aggressive_df['avg_profit'] * 0.6 +  # 60% weight on profit
                aggressive_df['win_rate'] * 0.2 +  # 20% weight on win rate
                aggressive_df['sharpe'] * 10 * 0.2  # 20% weight on Sharpe
            )
            aggressive_idx = aggressive_score.idxmax()
            aggressive = aggressive_df.loc[aggressive_idx]
        else:
            # Fall back to best profit if no options with >50% win rate
            aggressive_idx = results_df['avg_profit'].idxmax()
            aggressive = results_df.iloc[aggressive_idx]
        
        return {
            'conservative': {
                'buy_zone': round(conservative['buy_zone'], 3),
                'sell_zone': round(conservative['sell_zone'], 3),
                'win_rate': round(conservative['win_rate'], 1),
                'avg_profit': round(conservative['avg_profit'], 2),
                'trades': int(conservative['trades']),
                'sharpe': round(conservative['sharpe'], 2),
                'max_dd': round(conservative['max_dd'], 2)
            },
            'aggressive': {
                'buy_zone': round(aggressive['buy_zone'], 3),
                'sell_zone': round(aggressive['sell_zone'], 3),
                'win_rate': round(aggressive['win_rate'], 1),
                'avg_profit': round(aggressive['avg_profit'], 2),
                'trades': int(aggressive['trades']),
                'sharpe': round(aggressive['sharpe'], 2),
                'max_dd': round(aggressive['max_dd'], 2)
            }
        }
    
    def run_backtest(self):
        """Run full backtest for all tiers"""
        logger.info("=" * 80)
        logger.info("CHANNEL STRATEGY THRESHOLD OPTIMIZATION - 7 DAY BACKTEST")
        logger.info("=" * 80)
        
        results = {}
        
        for tier_name, symbols in self.tiers.items():
            tier_results = self.optimize_tier(tier_name, symbols)
            if tier_results:
                results[tier_name] = tier_results
        
        # Display results
        self.display_results(results)
        
        return results
    
    def display_results(self, results: Dict):
        """Display results in a formatted table"""
        print("\n" + "=" * 100)
        print("CHANNEL STRATEGY THRESHOLD RECOMMENDATIONS (7-DAY BACKTEST)")
        print("=" * 100)
        
        for tier_name in ['large_cap', 'mid_cap', 'small_cap', 'memecoin']:
            if tier_name not in results:
                continue
                
            tier_data = results[tier_name]
            print(f"\n{tier_name.upper().replace('_', ' ')}:")
            print("-" * 80)
            
            # Conservative
            cons = tier_data['conservative']
            print(f"  CONSERVATIVE:")
            print(f"    Buy Zone:  {cons['buy_zone']:.3f} ({cons['buy_zone']*100:.1f}% below mid-channel)")
            print(f"    Sell Zone: {cons['sell_zone']:.3f} ({cons['sell_zone']*100:.1f}% above mid-channel)")
            print(f"    Performance: {cons['win_rate']:.1f}% win rate, {cons['avg_profit']:.2f}% avg profit/trade")
            print(f"    Risk: {cons['max_dd']:.2f}% max drawdown, {cons['sharpe']:.2f} Sharpe ratio")
            print(f"    Trades: {cons['trades']} in 7 days")
            
            # Aggressive
            agg = tier_data['aggressive']
            print(f"\n  AGGRESSIVE:")
            print(f"    Buy Zone:  {agg['buy_zone']:.3f} ({agg['buy_zone']*100:.1f}% below mid-channel)")
            print(f"    Sell Zone: {agg['sell_zone']:.3f} ({agg['sell_zone']*100:.1f}% above mid-channel)")
            print(f"    Performance: {agg['win_rate']:.1f}% win rate, {agg['avg_profit']:.2f}% avg profit/trade")
            print(f"    Risk: {agg['max_dd']:.2f}% max drawdown, {agg['sharpe']:.2f} Sharpe ratio")
            print(f"    Trades: {agg['trades']} in 7 days")
        
        print("\n" + "=" * 100)
        print("SUMMARY RECOMMENDATIONS FOR ADMIN PANEL:")
        print("=" * 100)
        
        print("\nCONSERVATIVE SETTINGS (High Win Rate, Lower Risk):")
        for tier_name in ['large_cap', 'mid_cap', 'small_cap', 'memecoin']:
            if tier_name in results:
                cons = results[tier_name]['conservative']
                print(f"  {tier_name:12s}: Buy={cons['buy_zone']:.3f}, Sell={cons['sell_zone']:.3f}")
        
        print("\nAGGRESSIVE SETTINGS (Higher Profit, More Risk):")
        for tier_name in ['large_cap', 'mid_cap', 'small_cap', 'memecoin']:
            if tier_name in results:
                agg = results[tier_name]['aggressive']
                print(f"  {tier_name:12s}: Buy={agg['buy_zone']:.3f}, Sell={agg['sell_zone']:.3f}")


if __name__ == "__main__":
    backtester = ChannelBacktester()
    results = backtester.run_backtest()