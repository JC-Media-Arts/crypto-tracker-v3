#!/usr/bin/env python3
"""
Freqtrade trades API adapter
Converts Freqtrade database data to match the existing dashboard format
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pandas as pd

sys.path.append(str(Path(__file__).parent / "freqtrade"))
from dashboard_adapter import FreqtradeDashboardAdapter


def get_freqtrade_trades_data(page=1, per_page=100, filter_type='all'):
    """
    Get trades data from Freqtrade database formatted for the dashboard
    
    Returns data in the same format as the original paper_trades API
    """
    # Initialize adapter (will use Supabase in production automatically)
    adapter = FreqtradeDashboardAdapter()
    
    # Get data from Freqtrade
    all_trades_df = adapter.get_all_trades()
    open_positions_df = adapter.get_open_positions()
    stats = adapter.get_performance_stats()
    
    # Initialize return structure
    trades_data = []
    open_trades = []
    
    STARTING_CAPITAL = 10000.0
    
    # Get current prices from Supabase
    from src.data.supabase_client import SupabaseClient
    db = SupabaseClient()
    current_prices = {}
    
    if not open_positions_df.empty:
        for symbol in open_positions_df['symbol'].unique():
            try:
                result = (
                    db.client.table("ohlc_data")
                    .select("close")
                    .eq("symbol", symbol)
                    .order("timestamp", desc=True)
                    .limit(1)
                    .execute()
                )
                if result.data:
                    current_prices[symbol] = float(result.data[0]["close"])
            except:
                current_prices[symbol] = 0
    
    # Format open trades
    if not open_positions_df.empty:
        for _, trade in open_positions_df.iterrows():
            current_price = current_prices.get(trade['symbol'], trade['entry_price'])
            
            # Calculate unrealized P&L
            position_value = trade['amount'] * current_price
            entry_value = trade['amount'] * trade['entry_price']
            unrealized_pnl = position_value - entry_value
            unrealized_pnl_pct = (unrealized_pnl / entry_value) * 100 if entry_value > 0 else 0
            
            # Calculate holding time with proper formatting
            entry_time = trade['entry_time']
            if pd.isna(entry_time):
                hold_time_str = "Unknown"
            else:
                hold_time = datetime.now(timezone.utc) - entry_time
                total_seconds = hold_time.total_seconds()
                
                days = int(total_seconds // 86400)
                hours = int((total_seconds % 86400) // 3600)
                minutes = int((total_seconds % 3600) // 60)
                
                if days > 0:
                    if hours > 0:
                        hold_time_str = f"{days}d {hours}h"
                    else:
                        hold_time_str = f"{days}d"
                elif hours > 0:
                    if minutes > 0:
                        hold_time_str = f"{hours}h {minutes}m"
                    else:
                        hold_time_str = f"{hours}h"
                else:
                    hold_time_str = f"{minutes}m"
            
            # Get tier-specific exit params from config
            from src.config.config_loader import ConfigLoader
            config_loader = ConfigLoader()
            tier = config_loader.get_tier_config(trade['symbol'])  # Get tier name
            exit_params = config_loader.get_exit_params('CHANNEL', trade['symbol'])
            
            # Calculate SL/TP/TS displays like the old dashboard
            sl_display = None
            tp_display = None
            ts_display = None
            
            if trade.get('stop_loss'):
                # Calculate stop loss percentage from price
                sl_price = float(trade['stop_loss'])
                sl_pct = ((sl_price - trade['entry_price']) / trade['entry_price']) * 100
                # Format: "current% / sl%"
                sl_display = f"{unrealized_pnl_pct:.1f}% / {sl_pct:.1f}%"
            
            # Take profit display
            if exit_params and exit_params.get('take_profit'):
                tp_pct = exit_params['take_profit'] * 100
                # Format: "current% / tp%"
                tp_display = f"{unrealized_pnl_pct:.1f}% / {tp_pct:.1f}%"
            
            # Trailing stop display
            if exit_params and exit_params.get('trailing_stop'):
                ts_pct = exit_params['trailing_stop'] * 100
                activation_pct = exit_params.get('trailing_activation', 0.02) * 100
                
                # Check if trailing stop is active
                if unrealized_pnl_pct >= activation_pct:
                    ts_display = f"🟢 Active: {unrealized_pnl_pct:.1f}% / -{ts_pct:.1f}%"
                else:
                    ts_display = f"⚪ Inactive (activates at {activation_pct:.1f}%)"
            
            open_trade = {
                'symbol': trade['symbol'],
                'strategy': trade.get('strategy', 'CHANNEL'),
                'entry_price': float(trade['entry_price']),
                'entry_time': trade['entry_time'].isoformat() if pd.notna(trade['entry_time']) else None,
                'current_price': float(current_price),
                'amount': float(trade['amount']),
                'unrealized_pnl': float(unrealized_pnl),
                'unrealized_pnl_pct': float(unrealized_pnl_pct),
                'hold_time': hold_time_str,
                'dca_status': '-',
                'sl_display': sl_display,
                'tp_display': tp_display,
                'ts_display': ts_display,
                'exit_reason': None
            }
            open_trades.append(open_trade)
    
    # Format closed trades
    closed_trades = all_trades_df[all_trades_df['is_open'] == 0]
    if not closed_trades.empty:
        for _, trade in closed_trades.iterrows():
            if pd.notna(trade['exit_time']):
                # Calculate holding time with proper formatting
                if pd.notna(trade['entry_time']):
                    hold_time = trade['exit_time'] - trade['entry_time']
                    total_seconds = hold_time.total_seconds()
                    
                    days = int(total_seconds // 86400)
                    hours = int((total_seconds % 86400) // 3600)
                    minutes = int((total_seconds % 3600) // 60)
                    
                    if days > 0:
                        if hours > 0:
                            hold_time_str = f"{days}d {hours}h"
                        else:
                            hold_time_str = f"{days}d"
                    elif hours > 0:
                        if minutes > 0:
                            hold_time_str = f"{hours}h {minutes}m"
                        else:
                            hold_time_str = f"{hours}h"
                    else:
                        hold_time_str = f"{minutes}m"
                else:
                    hold_time_str = "Unknown"
                
                closed_trade = {
                    'symbol': trade['symbol'],
                    'strategy': trade.get('strategy', 'CHANNEL'),
                    'entry_price': float(trade['entry_price']),
                    'exit_price': float(trade['exit_price']) if trade['exit_price'] else 0,
                    'entry_time': trade['entry_time'].isoformat() if pd.notna(trade['entry_time']) else None,
                    'exit_time': trade['exit_time'].isoformat() if pd.notna(trade['exit_time']) else None,
                    'pnl': float(trade.get('profit_abs', 0)),
                    'pnl_pct': float(trade.get('profit_pct', 0)) * 100 if trade.get('profit_pct') else 0,
                    'hold_time': hold_time_str,
                    'exit_reason': trade.get('exit_reason', 'manual'),
                    'status': 'closed'
                }
                trades_data.append(closed_trade)
    
    # Apply filter
    if filter_type == 'open':
        trades_to_show = []
    elif filter_type == 'closed':
        trades_to_show = trades_data
        open_trades = []  # Don't show open trades when filter is closed
    else:  # 'all'
        trades_to_show = trades_data
    
    # Pagination
    total_trades = len(trades_to_show) if filter_type == 'closed' else len(open_trades)
    total_pages = max(1, (total_trades + per_page - 1) // per_page)
    
    # Slice for pagination
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    if filter_type == 'open':
        paginated_open = open_trades[start_idx:end_idx]
        paginated_closed = []
    elif filter_type == 'closed':
        paginated_open = []
        paginated_closed = trades_to_show[start_idx:end_idx]
    else:
        paginated_open = open_trades[start_idx:end_idx]
        paginated_closed = trades_to_show[start_idx:end_idx]
    
    # Calculate total unrealized P&L from open positions
    total_unrealized_pnl = sum(trade['unrealized_pnl'] for trade in open_trades)
    
    return {
        'trades': paginated_closed,
        'open_trades': paginated_open,
        'stats': {
            'open_count': stats.get('open_trades', 0),
            'closed_count': stats.get('closed_trades', 0),
            'win_count': int(stats.get('closed_trades', 0) * stats.get('win_rate', 0) / 100) if stats.get('closed_trades', 0) > 0 else 0,
            'loss_count': stats.get('closed_trades', 0) - int(stats.get('closed_trades', 0) * stats.get('win_rate', 0) / 100) if stats.get('closed_trades', 0) > 0 else 0,
            'win_rate': stats.get('win_rate', 0),
            'total_pnl': stats.get('avg_profit_pct', 0),
            'total_pnl_dollar': stats.get('total_profit', 0) + total_unrealized_pnl,  # Include unrealized P&L
            'starting_capital': STARTING_CAPITAL,
        },
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_trades': total_trades,
            'total_pages': total_pages
        }
    }


if __name__ == "__main__":
    # Test the function
    data = get_freqtrade_trades_data()
    print(f"Open trades: {len(data['open_trades'])}")
    print(f"Closed trades: {len(data['trades'])}")
    print(f"Stats: {data['stats']}")
    
    if data['open_trades']:
        print("\nFirst open trade:")
        for key, value in data['open_trades'][0].items():
            print(f"  {key}: {value}")
