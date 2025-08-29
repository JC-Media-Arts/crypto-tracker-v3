#!/usr/bin/env python3
"""
Dashboard Adapter for Freqtrade
Reads from Freqtrade's SQLite database and provides data for the custom dashboard
"""

import os
import sqlite3
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
from pathlib import Path


class FreqtradeDashboardAdapter:
    """
    Adapter to read Freqtrade's database and provide data for custom dashboard
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the dashboard adapter
        
        Args:
            db_path: Path to Freqtrade's SQLite database
                    Defaults to ./tradesv3.dryrun.sqlite
        """
        if db_path is None:
            # Default path for dry-run database
            self.db_path = Path(__file__).parent / "tradesv3.dryrun.sqlite"
        else:
            self.db_path = Path(db_path)
            
        if not self.db_path.exists():
            raise FileNotFoundError(f"Freqtrade database not found at {self.db_path}")
            
        print(f"✅ Connected to Freqtrade database: {self.db_path}")
        
    def get_connection(self):
        """Get a connection to the SQLite database"""
        return sqlite3.connect(self.db_path, timeout=10.0)
        
    def get_all_trades(self) -> pd.DataFrame:
        """
        Get all trades from Freqtrade database
        
        Returns:
            DataFrame with trade data
        """
        query = """
        SELECT 
            id,
            pair as symbol,
            is_open,
            fee_open,
            fee_close,
            open_rate as entry_price,
            close_rate as exit_price,
            stake_amount,
            amount,
            open_date as entry_time,
            close_date as exit_time,
            close_profit as profit_pct,
            close_profit_abs as profit_abs,
            exit_reason,
            strategy,
            enter_tag,
            stop_loss,
            initial_stop_loss,
            max_rate,
            min_rate
        FROM trades
        ORDER BY id DESC
        """
        
        with self.get_connection() as conn:
            df = pd.read_sql_query(query, conn)
            
        # Clean up symbol names (remove /USDT)
        df['symbol'] = df['symbol'].str.replace('/USDT', '')
        
        # Convert timestamps (make timezone-aware)
        df['entry_time'] = pd.to_datetime(df['entry_time'], utc=True)
        df['exit_time'] = pd.to_datetime(df['exit_time'], utc=True)
        
        return df
        
    def get_open_positions(self) -> pd.DataFrame:
        """
        Get currently open positions
        
        Returns:
            DataFrame with open positions
        """
        query = """
        SELECT 
            id,
            pair as symbol,
            open_rate as entry_price,
            stake_amount,
            amount,
            open_date as entry_time,
            stop_loss,
            initial_stop_loss,
            max_rate,
            min_rate,
            strategy,
            enter_tag
        FROM trades
        WHERE is_open = 1
        ORDER BY open_date DESC
        """
        
        with self.get_connection() as conn:
            df = pd.read_sql_query(query, conn)
            
        if not df.empty:
            df['symbol'] = df['symbol'].str.replace('/USDT', '')
            df['entry_time'] = pd.to_datetime(df['entry_time'], utc=True)
            
            # Calculate current P&L (would need current prices)
            # For now, just show entry data
            df['holding_time'] = datetime.now(timezone.utc) - df['entry_time']
            df['holding_hours'] = df['holding_time'].dt.total_seconds() / 3600
            
        return df
        
    def get_closed_positions(self, days: int = 7) -> pd.DataFrame:
        """
        Get closed positions from last N days
        
        Args:
            days: Number of days to look back
            
        Returns:
            DataFrame with closed positions
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        query = """
        SELECT 
            id,
            pair as symbol,
            open_rate as entry_price,
            close_rate as exit_price,
            stake_amount,
            amount,
            open_date as entry_time,
            close_date as exit_time,
            close_profit as profit_pct,
            close_profit_abs as profit_abs,
            exit_reason,
            strategy,
            enter_tag
        FROM trades
        WHERE is_open = 0
        AND close_date >= ?
        ORDER BY close_date DESC
        """
        
        with self.get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=[cutoff_date])
            
        if not df.empty:
            df['symbol'] = df['symbol'].str.replace('/USDT', '')
            df['entry_time'] = pd.to_datetime(df['entry_time'], utc=True)
            df['exit_time'] = pd.to_datetime(df['exit_time'], utc=True)
            
            # Calculate holding time
            df['holding_time'] = df['exit_time'] - df['entry_time']
            df['holding_hours'] = df['holding_time'].dt.total_seconds() / 3600
            
        return df
        
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Calculate performance statistics
        
        Returns:
            Dictionary with performance metrics
        """
        stats = {}
        
        # Get all trades
        all_trades = self.get_all_trades()
        
        if all_trades.empty:
            return {
                'total_trades': 0,
                'open_trades': 0,
                'closed_trades': 0,
                'win_rate': 0,
                'total_profit': 0,
                'avg_profit': 0,
                'best_trade': 0,
                'worst_trade': 0
            }
            
        # Basic counts
        stats['total_trades'] = len(all_trades)
        stats['open_trades'] = len(all_trades[all_trades['is_open'] == 1])
        stats['closed_trades'] = len(all_trades[all_trades['is_open'] == 0])
        
        # Closed trade statistics
        closed = all_trades[all_trades['is_open'] == 0]
        
        if not closed.empty:
            # Win rate
            winning_trades = closed[closed['profit_pct'] > 0]
            stats['win_rate'] = len(winning_trades) / len(closed) * 100
            
            # Profit statistics
            stats['total_profit'] = closed['profit_abs'].sum()
            stats['avg_profit'] = closed['profit_abs'].mean()
            stats['avg_profit_pct'] = closed['profit_pct'].mean() * 100
            
            # Best and worst trades
            stats['best_trade'] = closed['profit_pct'].max() * 100
            stats['worst_trade'] = closed['profit_pct'].min() * 100
            
            # Average holding time
            closed_with_times = closed.dropna(subset=['entry_time', 'exit_time'])
            if not closed_with_times.empty:
                holding_times = closed_with_times['exit_time'] - closed_with_times['entry_time']
                avg_holding = holding_times.mean()
                stats['avg_holding_hours'] = avg_holding.total_seconds() / 3600
        else:
            stats['win_rate'] = 0
            stats['total_profit'] = 0
            stats['avg_profit'] = 0
            stats['avg_profit_pct'] = 0
            stats['best_trade'] = 0
            stats['worst_trade'] = 0
            stats['avg_holding_hours'] = 0
            
        return stats
        
    def get_strategy_performance(self) -> pd.DataFrame:
        """
        Get performance breakdown by strategy
        
        Returns:
            DataFrame with strategy performance metrics
        """
        query = """
        SELECT 
            strategy,
            COUNT(*) as total_trades,
            SUM(CASE WHEN is_open = 1 THEN 1 ELSE 0 END) as open_trades,
            SUM(CASE WHEN is_open = 0 THEN 1 ELSE 0 END) as closed_trades,
            AVG(CASE WHEN is_open = 0 THEN close_profit ELSE NULL END) * 100 as avg_profit_pct,
            SUM(CASE WHEN is_open = 0 THEN close_profit_abs ELSE 0 END) as total_profit,
            MAX(CASE WHEN is_open = 0 THEN close_profit ELSE NULL END) * 100 as best_trade_pct,
            MIN(CASE WHEN is_open = 0 THEN close_profit ELSE NULL END) * 100 as worst_trade_pct
        FROM trades
        GROUP BY strategy
        """
        
        with self.get_connection() as conn:
            df = pd.read_sql_query(query, conn)
            
        # Calculate win rate for each strategy
        for strategy in df['strategy'].unique():
            query_wins = """
            SELECT 
                COUNT(*) as wins
            FROM trades
            WHERE strategy = ?
            AND is_open = 0
            AND close_profit > 0
            """
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query_wins, [strategy])
                wins = cursor.fetchone()[0]
                
            closed_count = df.loc[df['strategy'] == strategy, 'closed_trades'].values[0]
            if closed_count > 0:
                df.loc[df['strategy'] == strategy, 'win_rate'] = (wins / closed_count) * 100
            else:
                df.loc[df['strategy'] == strategy, 'win_rate'] = 0
                
        return df
        
    def get_daily_performance(self, days: int = 30) -> pd.DataFrame:
        """
        Get daily performance metrics
        
        Args:
            days: Number of days to analyze
            
        Returns:
            DataFrame with daily performance
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        query = """
        SELECT 
            DATE(close_date) as date,
            COUNT(*) as trades_closed,
            SUM(close_profit_abs) as daily_profit,
            AVG(close_profit) * 100 as avg_profit_pct,
            MAX(close_profit) * 100 as best_trade_pct,
            MIN(close_profit) * 100 as worst_trade_pct
        FROM trades
        WHERE is_open = 0
        AND close_date >= ?
        GROUP BY DATE(close_date)
        ORDER BY date DESC
        """
        
        with self.get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=[cutoff_date])
            
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            
            # Calculate cumulative profit
            df = df.sort_values('date')
            df['cumulative_profit'] = df['daily_profit'].cumsum()
            
        return df
        
    def export_for_dashboard(self) -> Dict[str, Any]:
        """
        Export all data in format suitable for dashboard
        
        Returns:
            Dictionary with all dashboard data
        """
        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'performance_stats': self.get_performance_stats(),
            'open_positions': self.get_open_positions().to_dict('records'),
            'recent_closed': self.get_closed_positions(days=7).to_dict('records'),
            'strategy_performance': self.get_strategy_performance().to_dict('records'),
            'daily_performance': self.get_daily_performance(days=30).to_dict('records')
        }


def main():
    """Test the dashboard adapter"""
    adapter = FreqtradeDashboardAdapter()
    
    print("\n📊 Performance Statistics:")
    print("-" * 50)
    stats = adapter.get_performance_stats()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"{key:20}: {value:.2f}")
        else:
            print(f"{key:20}: {value}")
    
    print("\n📈 Open Positions:")
    print("-" * 50)
    open_positions = adapter.get_open_positions()
    if not open_positions.empty:
        print(open_positions[['symbol', 'entry_price', 'stake_amount', 'holding_hours']].to_string())
    else:
        print("No open positions")
    
    print("\n🎯 Strategy Performance:")
    print("-" * 50)
    strategy_perf = adapter.get_strategy_performance()
    if not strategy_perf.empty:
        print(strategy_perf.to_string())
    
    print("\n✅ Dashboard adapter ready!")
    print(f"Database location: {adapter.db_path}")


if __name__ == "__main__":
    main()
