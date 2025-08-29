#!/usr/bin/env python3
"""
Close the 50 worst-performing CHANNEL positions to free up trading capacity.
This will allow new trades to open across all strategies.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Tuple
from loguru import logger

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from src.data.hybrid_fetcher import HybridDataFetcher
from dotenv import load_dotenv
from supabase import create_client

# Load environment
load_dotenv()


def get_open_channel_positions() -> List[Dict]:
    """Get all open CHANNEL positions from the database."""
    
    # Initialize Supabase client
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    client = create_client(supabase_url, supabase_key)
    
    # Get all trades
    response = client.table('paper_trades').select('*').execute()
    all_trades = response.data
    
    # Find trade groups with sells (closed positions)
    groups_with_sells = set()
    buy_trades = []
    
    for trade in all_trades:
        if trade['side'] == 'SELL' and trade['trade_group_id']:
            groups_with_sells.add(trade['trade_group_id'])
        elif trade['side'] == 'BUY' and trade['strategy_name'] == 'CHANNEL':
            buy_trades.append(trade)
    
    # Get only open CHANNEL positions
    open_positions = []
    for trade in buy_trades:
        if trade.get('trade_group_id') and trade['trade_group_id'] not in groups_with_sells:
            open_positions.append(trade)
    
    logger.info(f"Found {len(open_positions)} open CHANNEL positions")
    return open_positions


def calculate_position_pnl(positions: List[Dict]) -> List[Tuple[Dict, float, float]]:
    """Calculate P&L for each position using current market prices."""
    
    # Initialize data fetcher
    data_fetcher = HybridDataFetcher()
    
    positions_with_pnl = []
    
    for position in positions:
        try:
            symbol = position['symbol']
            entry_price = float(position['price'])
            
            # Get current price
            data = data_fetcher.get_recent_data(symbol=symbol, timeframe="1m", hours=1)
            if data and len(data) > 0:
                current_price = data[-1]['close']
                
                # Calculate P&L
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
                pnl_usd = (current_price - entry_price) * float(position.get('amount', 0))
                
                positions_with_pnl.append((position, pnl_pct, pnl_usd))
                logger.debug(f"{symbol}: Entry=${entry_price:.4f}, Current=${current_price:.4f}, P&L={pnl_pct:.2f}%")
            else:
                logger.warning(f"Could not get current price for {symbol}")
                # Add with 0 P&L if we can't get price
                positions_with_pnl.append((position, 0.0, 0.0))
                
        except Exception as e:
            logger.error(f"Error calculating P&L for position {position.get('symbol', 'UNKNOWN')}: {e}")
            positions_with_pnl.append((position, 0.0, 0.0))
    
    return positions_with_pnl


def close_positions(positions_to_close: List[Tuple[Dict, float, float]], count: int = 50):
    """Close the specified positions by creating SELL orders."""
    
    # Initialize Supabase client
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    client = create_client(supabase_url, supabase_key)
    
    # Initialize data fetcher for current prices
    data_fetcher = HybridDataFetcher()
    
    closed_count = 0
    total_pnl = 0.0
    
    for position, pnl_pct, pnl_usd in positions_to_close[:count]:
        try:
            symbol = position['symbol']
            trade_group_id = position['trade_group_id']
            
            # Get current price for the SELL order
            data = data_fetcher.get_recent_data(symbol=symbol, timeframe="1m", hours=1)
            if not data or len(data) == 0:
                logger.warning(f"Skipping {symbol} - no price data available")
                continue
                
            current_price = data[-1]['close']
            
            # Create SELL trade record
            sell_trade = {
                'symbol': symbol,
                'side': 'SELL',
                'price': current_price,
                'amount': position['amount'],
                'strategy_name': 'CHANNEL',
                'trade_group_id': trade_group_id,
                'exit_reason': 'POSITION_CLEANUP',
                'pnl': pnl_usd,
                'pnl_pct': pnl_pct,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'trading_engine': 'cleanup_script'
            }
            
            # Insert the SELL trade
            response = client.table('paper_trades').insert(sell_trade).execute()
            
            if response.data:
                closed_count += 1
                total_pnl += pnl_usd
                logger.info(f"✅ Closed {symbol} - P&L: {pnl_pct:.2f}% (${pnl_usd:.2f})")
            else:
                logger.error(f"Failed to close {symbol}")
                
        except Exception as e:
            logger.error(f"Error closing position {position.get('symbol', 'UNKNOWN')}: {e}")
    
    return closed_count, total_pnl


def main():
    """Main execution function."""
    
    logger.info("=" * 60)
    logger.info("CLOSING 50 WORST-PERFORMING CHANNEL POSITIONS")
    logger.info("=" * 60)
    
    # Step 1: Get all open CHANNEL positions
    open_positions = get_open_channel_positions()
    
    if len(open_positions) == 0:
        logger.info("No open CHANNEL positions found")
        return
    
    # Step 2: Calculate P&L for each position
    logger.info("Calculating P&L for all positions...")
    positions_with_pnl = calculate_position_pnl(open_positions)
    
    # Step 3: Sort by P&L (worst first)
    positions_with_pnl.sort(key=lambda x: x[1])  # Sort by pnl_pct
    
    # Show summary of positions to close
    logger.info("\n" + "=" * 60)
    logger.info("POSITIONS TO CLOSE (50 worst performers):")
    logger.info("=" * 60)
    
    total_expected_pnl = 0.0
    for i, (position, pnl_pct, pnl_usd) in enumerate(positions_with_pnl[:50]):
        total_expected_pnl += pnl_usd
        if i < 10:  # Show first 10 for brevity
            logger.info(f"{i+1:3}. {position['symbol']:8} P&L: {pnl_pct:7.2f}% (${pnl_usd:7.2f})")
    
    if len(positions_with_pnl) > 10:
        logger.info("     ... (40 more positions)")
    
    logger.info(f"\nTotal expected P&L from closing: ${total_expected_pnl:.2f}")
    
    # Step 4: Close the positions
    logger.info("\n" + "=" * 60)
    logger.info("CLOSING POSITIONS...")
    logger.info("=" * 60)
    
    closed_count, actual_pnl = close_positions(positions_with_pnl, count=50)
    
    # Step 5: Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Positions closed: {closed_count} / 50")
    logger.info(f"Total P&L realized: ${actual_pnl:.2f}")
    logger.info(f"Remaining CHANNEL positions: {len(open_positions) - closed_count}")
    logger.info("\n✅ Cleanup complete! New trades can now open.")
    

if __name__ == "__main__":
    main()