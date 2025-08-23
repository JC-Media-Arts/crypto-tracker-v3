#!/usr/bin/env python3
"""
Update existing positions in database with stop_loss, take_profit, and trailing_stop_pct
"""

import json
from pathlib import Path
from src.data.supabase_client import SupabaseClient
from loguru import logger

def update_existing_positions():
    """Update existing open positions with risk management fields"""
    
    db = SupabaseClient()
    
    # Load current state to get position details
    state_file = Path("data/paper_trading_state.json")
    if not state_file.exists():
        logger.error("No state file found")
        return
    
    with open(state_file, 'r') as f:
        state = json.load(f)
    
    # Get open positions from state
    positions = state.get("positions", {})
    
    logger.info(f"Found {len(positions)} open positions to update")
    
    for symbol, position in positions.items():
        try:
            # Get the existing record
            existing = db.client.table("paper_trades").select("*").eq("symbol", symbol).eq("side", "BUY").eq("status", "FILLED").execute()
            
            if existing.data:
                trade_id = existing.data[0]["trade_id"]
                
                # Update with risk management fields
                update_data = {
                    "stop_loss": position.get("stop_loss"),
                    "take_profit": position.get("take_profit"),
                    "trailing_stop_pct": position.get("trailing_stop_pct")
                }
                
                result = db.client.table("paper_trades").update(update_data).eq("trade_id", trade_id).execute()
                
                logger.info(f"✅ Updated {symbol}:")
                logger.info(f"   - Stop Loss: ${position.get('stop_loss', 0):.4f}")
                logger.info(f"   - Take Profit: ${position.get('take_profit', 0):.4f}")
                logger.info(f"   - Trailing Stop: {position.get('trailing_stop_pct', 0)*100:.1f}%")
            else:
                logger.warning(f"No database record found for {symbol}")
                
        except Exception as e:
            logger.error(f"Failed to update {symbol}: {e}")
    
    # Verify updates
    logger.info("\n=== Verifying Updates ===")
    
    for symbol in positions.keys():
        result = db.client.table("paper_trades").select("symbol, stop_loss, take_profit, trailing_stop_pct").eq("symbol", symbol).eq("side", "BUY").execute()
        
        if result.data:
            record = result.data[0]
            logger.info(f"{symbol}: SL=${record['stop_loss']}, TP=${record['take_profit']}, Trail={record['trailing_stop_pct']}")

if __name__ == "__main__":
    update_existing_positions()
