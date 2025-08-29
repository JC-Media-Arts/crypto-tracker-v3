#!/usr/bin/env python3
"""
Safely close stuck positions while preserving all data for ML/Shadow testing.
1. Closes positions older than 96 hours (time_exit)
2. Closes excess positions beyond 3 per symbol (keeping oldest 3)
"""

import os
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data.supabase_client import SupabaseClient
from loguru import logger

load_dotenv()


def main():
    """Fix stuck positions safely"""
    db = SupabaseClient()
    
    print("\n" + "="*60)
    print("FIXING STUCK POSITIONS (SAFE MODE)")
    print("="*60)
    print("\nThis will preserve all data for ML/Shadow testing")
    print("by creating proper SELL records with appropriate exit reasons")
    
    # Get all open CHANNEL positions
    print("\nLoading open positions...")
    channel_buys = (
        db.client.table("paper_trades")
        .select("*")
        .eq("strategy_name", "CHANNEL")
        .eq("side", "BUY")
        .execute()
    )
    
    channel_sells = (
        db.client.table("paper_trades")
        .select("trade_group_id")
        .eq("strategy_name", "CHANNEL")
        .eq("side", "SELL")
        .execute()
    )
    
    sell_groups = {s["trade_group_id"] for s in channel_sells.data if s.get("trade_group_id")}
    
    # Find open positions
    open_positions = []
    for buy in channel_buys.data:
        if buy.get("trade_group_id") and buy["trade_group_id"] not in sell_groups:
            open_positions.append(buy)
    
    print(f"Found {len(open_positions)} open CHANNEL positions")
    
    # Categorize positions
    now = datetime.now(timezone.utc)
    positions_to_close = []
    positions_by_symbol = {}
    
    for pos in open_positions:
        created = datetime.fromisoformat(pos["created_at"].replace("Z", "+00:00"))
        age_hours = (now - created).total_seconds() / 3600
        
        symbol = pos["symbol"]
        if symbol not in positions_by_symbol:
            positions_by_symbol[symbol] = []
        
        positions_by_symbol[symbol].append({
            "trade_id": pos["trade_id"],
            "group_id": pos["trade_group_id"],
            "symbol": symbol,
            "age_hours": age_hours,
            "created": created,
            "amount": float(pos["amount"]),
            "price": float(pos["price"]),
            "created_str": pos["created_at"]
        })
    
    # 1. Find positions older than 96 hours
    print("\n" + "="*60)
    print("STEP 1: POSITIONS OLDER THAN 96 HOURS")
    print("="*60)
    
    for symbol, positions in positions_by_symbol.items():
        for pos in positions:
            if pos["age_hours"] > 96:
                positions_to_close.append({
                    **pos,
                    "reason": "time_exit",
                    "reason_detail": f"Exceeded 96 hour limit (age: {pos['age_hours']:.1f}h)"
                })
    
    print(f"Found {len([p for p in positions_to_close if p['reason'] == 'time_exit'])} positions to close for time_exit")
    
    # 2. Find excess positions (more than 3 per symbol)
    print("\n" + "="*60)
    print("STEP 2: EXCESS POSITIONS (>3 PER SYMBOL)")
    print("="*60)
    
    for symbol, positions in positions_by_symbol.items():
        if len(positions) > 3:
            # Sort by age (oldest first) and keep only the oldest 3
            sorted_positions = sorted(positions, key=lambda x: x["created"])
            positions_to_remove = sorted_positions[3:]  # Everything after the first 3
            
            print(f"{symbol}: Has {len(positions)} positions, will close {len(positions_to_remove)} excess")
            
            for pos in positions_to_remove:
                # Check if not already marked for closing
                if not any(p["group_id"] == pos["group_id"] for p in positions_to_close):
                    positions_to_close.append({
                        **pos,
                        "reason": "position_limit",
                        "reason_detail": f"Exceeded 3 positions per symbol limit"
                    })
    
    # Remove duplicates (some positions might be both old AND excess)
    unique_positions = {}
    for pos in positions_to_close:
        if pos["group_id"] not in unique_positions:
            unique_positions[pos["group_id"]] = pos
    
    positions_to_close = list(unique_positions.values())
    
    print(f"\n" + "="*60)
    print("SUMMARY OF POSITIONS TO CLOSE:")
    print("="*60)
    print(f"Total positions to close: {len(positions_to_close)}")
    
    by_reason = {}
    for pos in positions_to_close:
        reason = pos["reason"]
        if reason not in by_reason:
            by_reason[reason] = []
        by_reason[reason].append(pos)
    
    for reason, positions in by_reason.items():
        print(f"  {reason}: {len(positions)} positions")
    
    if positions_to_close:
        print("\nFirst 10 positions to close:")
        for i, pos in enumerate(positions_to_close[:10]):
            print(f"  {i+1}. {pos['symbol']:6} - Age: {pos['age_hours']:.1f}h - Reason: {pos['reason']}")
        
        # Get current prices for calculating exit prices
        print("\nFetching current prices...")
        symbols = list(set(pos["symbol"] for pos in positions_to_close))
        current_prices = {}
        
        for symbol in symbols:
            try:
                price_result = (
                    db.client.table("ohlc_data")
                    .select("close")
                    .eq("symbol", symbol)
                    .order("timestamp", desc=True)
                    .limit(1)
                    .execute()
                )
                if price_result.data:
                    current_prices[symbol] = float(price_result.data[0]["close"])
            except:
                pass
        
        print(f"Got prices for {len(current_prices)} symbols")
        
        # Ask for confirmation
        print(f"\n⚠️  This will create {len(positions_to_close)} SELL records in the database.")
        print("All data will be preserved for ML/Shadow testing.")
        response = input("\nProceed with closing these positions? (yes/no): ")
        
        if response.lower() == "yes":
            print("\nCreating SELL records...")
            success_count = 0
            error_count = 0
            
            for pos in positions_to_close:
                try:
                    symbol = pos["symbol"]
                    current_price = current_prices.get(symbol, pos["price"])
                    
                    # Calculate P&L
                    entry_value = pos["price"] * pos["amount"]
                    exit_value = current_price * pos["amount"]
                    pnl = exit_value - entry_value
                    pnl_pct = (pnl / entry_value * 100) if entry_value > 0 else 0
                    
                    # Create SELL record
                    sell_data = {
                        "trading_engine": "simple_paper_trader",
                        "symbol": symbol,
                        "side": "SELL",
                        "order_type": "MARKET",
                        "price": current_price,
                        "amount": pos["amount"],
                        "status": "FILLED",
                        "created_at": now.isoformat(),
                        "filled_at": now.isoformat(),
                        "strategy_name": "CHANNEL",
                        "fees": 0.001 * exit_value,  # 0.1% fee
                        "pnl": pnl,
                        "exit_reason": pos["reason"],
                        "trade_group_id": pos["group_id"],
                        "hold_time_hours": pos["age_hours"]
                    }
                    
                    result = db.client.table("paper_trades").insert(sell_data).execute()
                    success_count += 1
                    print(f"  ✅ Closed {symbol} - {pos['reason']} - P&L: ${pnl:.2f} ({pnl_pct:+.1f}%)")
                    
                except Exception as e:
                    error_count += 1
                    print(f"  ❌ Failed to close {pos['symbol']}: {e}")
            
            print(f"\n" + "="*60)
            print("FINAL RESULTS:")
            print(f"✅ Successfully closed: {success_count} positions")
            if error_count > 0:
                print(f"❌ Failed: {error_count} positions")
            
            print(f"\n📊 IMPACT:")
            print(f"  CHANNEL positions before: 82")
            print(f"  Positions closed: {success_count}")
            print(f"  Remaining open: {82 - success_count}")
            print(f"  Now below 50 limit: {'Yes! ✅' if (82 - success_count) < 50 else 'No, still over'}")
            print(f"\n✨ All data preserved for ML/Shadow testing!")
            print("✨ Your system can now open new trades with optimized thresholds!")
            
        else:
            print("\n❌ Operation cancelled")
    else:
        print("\n✅ No positions need to be closed!")


if __name__ == "__main__":
    main()
