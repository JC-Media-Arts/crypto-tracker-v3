"""
Adapter to convert Freqtrade trades table structure to match dashboard expectations
"""

def adapt_freqtrade_trade(trade):
    """
    Convert a Freqtrade trade record to match the dashboard's expected format
    
    Freqtrade trades have:
    - id, pair, is_open, amount, open_rate, close_rate, open_date, close_date, etc.
    
    Dashboard expects:
    - symbol, side, price, created_at, trade_group_id, strategy_name, etc.
    """
    adapted = {
        # Map Freqtrade fields to dashboard fields
        'id': trade.get('id'),
        'trade_id': trade.get('id'),
        'trade_group_id': str(trade.get('id')),  # Use id as group_id for Freqtrade
        'symbol': trade.get('pair', '').split('/')[0] if trade.get('pair') else '',
        'pair': trade.get('pair'),
        'amount': trade.get('amount'),
        'strategy_name': trade.get('strategy', 'SimpleChannelStrategy'),
        'trading_engine': 'freqtrade',
        
        # For open trades, we show them as BUY side with open_rate as price
        # For closed trades, we need both BUY and SELL records
        'is_open': trade.get('is_open', True),
        
        # Timestamps
        'open_date': trade.get('open_date'),
        'close_date': trade.get('close_date'),
        
        # Prices
        'open_rate': trade.get('open_rate'),
        'close_rate': trade.get('close_rate'),
        'stake_amount': trade.get('stake_amount'),
        
        # P&L data
        'close_profit': trade.get('close_profit'),
        'close_profit_abs': trade.get('close_profit_abs'),
        'realized_profit': trade.get('realized_profit'),
        
        # Exit info
        'sell_reason': trade.get('sell_reason'),
        'exit_reason': trade.get('sell_reason'),  # Map sell_reason to exit_reason
        
        # Risk management
        'stop_loss': trade.get('stop_loss_abs'),
        'initial_stop_loss': trade.get('initial_stop_loss_abs'),
        'stop_loss_pct': trade.get('stop_loss_ratio'),
        
        # Additional fields
        'min_rate': trade.get('min_rate'),
        'max_rate': trade.get('max_rate'),
        'fee_open': trade.get('fee_open'),
        'fee_close': trade.get('fee_close'),
    }
    
    # Generate side and price based on trade status
    if trade.get('is_open'):
        adapted['side'] = 'BUY'
        adapted['price'] = trade.get('open_rate')
        adapted['created_at'] = trade.get('open_date')
    else:
        # For closed trades, the dashboard expects separate BUY/SELL records
        # This adapter returns the trade as a SELL record
        adapted['side'] = 'SELL'
        adapted['price'] = trade.get('close_rate')
        adapted['created_at'] = trade.get('close_date')
        adapted['pnl'] = trade.get('close_profit_abs')
    
    return adapted


def create_buy_sell_records(trade):
    """
    For closed trades, create separate BUY and SELL records
    This matches the old paper_trades table structure
    """
    if trade.get('is_open', True):
        # Open trade - return single BUY record
        buy_record = adapt_freqtrade_trade(trade)
        buy_record['side'] = 'BUY'
        buy_record['price'] = trade.get('open_rate')
        buy_record['created_at'] = trade.get('open_date')
        return [buy_record]
    else:
        # Closed trade - return both BUY and SELL records
        trade_id = trade.get('id')
        
        # BUY record
        buy_record = adapt_freqtrade_trade(trade)
        buy_record['id'] = f"{trade_id}_buy"
        buy_record['side'] = 'BUY'
        buy_record['price'] = trade.get('open_rate')
        buy_record['created_at'] = trade.get('open_date')
        buy_record['is_entry'] = True
        
        # SELL record
        sell_record = adapt_freqtrade_trade(trade)
        sell_record['id'] = f"{trade_id}_sell"
        sell_record['side'] = 'SELL'
        sell_record['price'] = trade.get('close_rate')
        sell_record['created_at'] = trade.get('close_date')
        sell_record['pnl'] = trade.get('close_profit_abs')
        sell_record['is_exit'] = True
        
        return [buy_record, sell_record]
