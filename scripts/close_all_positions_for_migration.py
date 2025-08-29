#!/usr/bin/env python3
"""
Close ALL open positions to prepare for migration to new position tracking system.
This will realize all P&L and give us a clean slate.
"""

import os
from datetime import datetime, timezone
from typing import List, Dict
from loguru import logger
from dotenv import load_dotenv
from supabase import create_client

# Load environment
load_dotenv()


def get_current_prices() -> Dict[str, float]:
    """Get latest prices for all symbols from OHLC data."""
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    client = create_client(supabase_url, supabase_key)
    
    # Get unique symbols from open positions first
    response = client.table('paper_trades').select('symbol').eq('side', 'BUY').execute()
    symbols = list(set([t['symbol'] for t in response.data]))
    
    prices = {}
    for symbol in symbols:
        # Get latest price from OHLC data
        response = (
            client.table('ohlc_data')
            .select('close')
            .eq('symbol', symbol)
            .order('timestamp', desc=True)
            .limit(1)
            .execute()
        )
        
        if response.data:
            prices[symbol] = float(response.data[0]['close'])
            logger.info(f"Current price for {symbol}: ${prices[symbol]:.4f}")
        else:
            logger.warning(f"No price data for {symbol}")
    
    return prices


def close_all_positions():
    """Close all open positions."""
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    client = create_client(supabase_url, supabase_key)
    
    # Get all open positions
    response = client.table('paper_trades').select('*').eq('side', 'BUY').execute()
    buy_trades = response.data
    
    # Get all SELL trades to find which positions are closed
    response = client.table('paper_trades').select('trade_group_id').eq('side', 'SELL').execute()
    sell_groups = set([t['trade_group_id'] for t in response.data if t['trade_group_id']])
    
    # Find truly open positions
    open_positions = []
    for trade in buy_trades:
        if trade.get('trade_group_id') and trade['trade_group_id'] not in sell_groups:
            open_positions.append(trade)
    
    logger.info(f"Found {len(open_positions)} open positions to close")
    
    if not open_positions:
        logger.info("No open positions to close")
        return
    
    # Get current prices
    prices = get_current_prices()
    
    # Track results
    closed_count = 0
    total_pnl = 0.0
    errors = []
    
    # Close each position
    for position in open_positions:
        symbol = position['symbol']
        trade_group_id = position['trade_group_id']
        
        if symbol not in prices:
            logger.error(f"No price for {symbol}, skipping")
            errors.append(f"No price for {symbol}")
            continue
        
        current_price = prices[symbol]
        entry_price = float(position['price'])
        amount = float(position['amount'])
        
        # Calculate P&L
        pnl_pct = ((current_price - entry_price) / entry_price) * 100
        pnl_usd = (current_price - entry_price) * amount
        
        # Create SELL trade record
        sell_trade = {
            'symbol': symbol,
            'side': 'SELL',
            'order_type': 'MARKET',
            'price': current_price,
            'amount': amount,
            'status': 'FILLED',
            'strategy_name': position['strategy_name'],
            'trade_group_id': trade_group_id,
            'exit_reason': 'MIGRATION_CLEANUP',
            'pnl': pnl_usd,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'trading_engine': 'migration_script'
        }
        
        try:
            response = client.table('paper_trades').insert(sell_trade).execute()
            closed_count += 1
            total_pnl += pnl_usd
            
            logger.info(
                f"Closed {symbol} position: "
                f"Entry ${entry_price:.4f} → Exit ${current_price:.4f} "
                f"P&L: ${pnl_usd:.2f} ({pnl_pct:+.2f}%)"
            )
        except Exception as e:
            logger.error(f"Failed to close {symbol}: {e}")
            errors.append(f"{symbol}: {str(e)}")
    
    # Summary
    logger.info("=" * 60)
    logger.info("MIGRATION CLEANUP SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Positions closed: {closed_count}/{len(open_positions)}")
    logger.info(f"Total P&L realized: ${total_pnl:.2f}")
    
    if errors:
        logger.warning(f"Errors encountered: {len(errors)}")
        for error in errors[:5]:  # Show first 5 errors
            logger.warning(f"  - {error}")
    
    return closed_count, total_pnl, errors


if __name__ == "__main__":
    logger.info("Starting position cleanup for migration...")
    logger.info("This will close ALL open positions to prepare for new tracking system")
    
    closed, pnl, errors = close_all_positions()
    
    if errors:
        logger.warning(f"Completed with {len(errors)} errors")
    else:
        logger.success("All positions closed successfully!")
    
    logger.info(f"Final results: {closed} positions closed, ${pnl:.2f} total P&L")
