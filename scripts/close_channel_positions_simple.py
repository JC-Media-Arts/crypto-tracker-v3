#!/usr/bin/env python3
"""
Close the 50 worst-performing CHANNEL positions to free up trading capacity.
Simplified version that directly queries current prices from database.
"""

import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Tuple
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
    
    # Get latest prices from last hour
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    
    # Query for latest price per symbol
    response = client.table('ohlc_data').select('symbol, close, timestamp').gte('timestamp', one_hour_ago).execute()
    
    prices = {}
    for row in response.data:
        symbol = row['symbol']
        if symbol not in prices or row['timestamp'] > prices[symbol]['timestamp']:
            prices[symbol] = {'price': row['close'], 'timestamp': row['timestamp']}
    
    # Return just the prices
    return {symbol: data['price'] for symbol, data in prices.items()}


def get_open_channel_positions() -> List[Dict]:
    """Get all open CHANNEL positions from the database."""
    
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


def calculate_position_pnl(positions: List[Dict], current_prices: Dict[str, float]) -> List[Tuple[Dict, float, float]]:
    """Calculate P&L for each position using current market prices."""
    
    positions_with_pnl = []
    
    for position in positions:
        try:
            symbol = position['symbol']
            entry_price = float(position['price'])
            amount = float(position.get('amount', 0))
            
            if symbol in current_prices:
                current_price = current_prices[symbol]
                
                # Calculate P&L
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
                # Assuming amount is in units, not USD
                position_value = entry_price * amount  # Original position value in USD
                current_value = current_price * amount  # Current value in USD
                pnl_usd = current_value - position_value
                
                positions_with_pnl.append((position, pnl_pct, pnl_usd))
                logger.debug(f"{symbol}: Entry=${entry_price:.4f}, Current=${current_price:.4f}, P&L={pnl_pct:.2f}%")
            else:
                logger.warning(f"No current price for {symbol}")
                # Add with 0 P&L if we can't get price
                positions_with_pnl.append((position, 0.0, 0.0))
                
        except Exception as e:
            logger.error(f"Error calculating P&L for position {position.get('symbol', 'UNKNOWN')}: {e}")
            positions_with_pnl.append((position, 0.0, 0.0))
    
    return positions_with_pnl


def close_positions(positions_to_close: List[Tuple[Dict, float, float]], current_prices: Dict[str, float], count: int = 50):
    """Close the specified positions by creating SELL orders."""
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    client = create_client(supabase_url, supabase_key)
    
    closed_count = 0
    total_pnl = 0.0
    
    for position, pnl_pct, pnl_usd in positions_to_close[:count]:
        try:
            symbol = position['symbol']
            trade_group_id = position['trade_group_id']
            
            if symbol not in current_prices:
                logger.warning(f"Skipping {symbol} - no current price available")
                continue
                
            current_price = current_prices[symbol]
            
            # Create SELL trade record
            sell_trade = {
                'symbol': symbol,
                'side': 'SELL',
                'order_type': 'MARKET',  # Required field
                'price': current_price,
                'amount': position['amount'],
                'status': 'FILLED',  # Mark as filled
                'strategy_name': 'CHANNEL',
                'trade_group_id': trade_group_id,
                'exit_reason': 'POSITION_CLEANUP',
                'pnl': pnl_usd,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'filled_at': datetime.now(timezone.utc).isoformat(),
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
    
    # Step 1: Get current prices for all symbols
    logger.info("Fetching current market prices...")
    current_prices = get_current_prices()
    logger.info(f"Got prices for {len(current_prices)} symbols")
    
    # Step 2: Get all open CHANNEL positions
    open_positions = get_open_channel_positions()
    
    if len(open_positions) == 0:
        logger.info("No open CHANNEL positions found")
        return
    
    # Step 3: Calculate P&L for each position
    logger.info("Calculating P&L for all positions...")
    positions_with_pnl = calculate_position_pnl(open_positions, current_prices)
    
    # Step 4: Sort by P&L (worst first)
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
    
    # Step 5: Close the positions
    logger.info("\n" + "=" * 60)
    logger.info("CLOSING POSITIONS...")
    logger.info("=" * 60)
    
    closed_count, actual_pnl = close_positions(positions_with_pnl, current_prices, count=50)
    
    # Step 6: Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Positions closed: {closed_count} / 50")
    logger.info(f"Total P&L realized: ${actual_pnl:.2f}")
    logger.info(f"Remaining CHANNEL positions: {len(open_positions) - closed_count}")
    logger.info("\n✅ Cleanup complete! New trades can now open.")
    

if __name__ == "__main__":
    main()
