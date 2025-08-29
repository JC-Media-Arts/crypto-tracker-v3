#!/usr/bin/env python3
"""
Fix orphaned SELL trades by matching them to their corresponding BUY trades.
This will properly close positions that are stuck open due to missing trade_group_id.
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data.supabase_client import SupabaseClient
from loguru import logger

load_dotenv()


def main():
    """Fix orphaned SELL trades"""
    db = SupabaseClient()
    
    print("\n" + "="*60)
    print("FIXING ORPHANED SELL TRADES")
    print("="*60)
    
    # Get all CHANNEL trades
    print("\nLoading CHANNEL trades...")
    channel_buys = (
        db.client.table("paper_trades")
        .select("*")
        .eq("strategy_name", "CHANNEL")
        .eq("side", "BUY")
        .order("created_at", desc=False)
        .execute()
    ).data
    
    channel_sells = (
        db.client.table("paper_trades")
        .select("*")
        .eq("strategy_name", "CHANNEL")
        .eq("side", "SELL")
        .order("created_at", desc=False)
        .execute()
    ).data
    
    print(f"Found {len(channel_buys)} BUY trades")
    print(f"Found {len(channel_sells)} SELL trades")
    
    # Find orphaned SELLs (no trade_group_id)
    orphaned_sells = [s for s in channel_sells if not s.get("trade_group_id")]
    print(f"\nFound {len(orphaned_sells)} orphaned SELL trades to fix")
    
    if not orphaned_sells:
        print("No orphaned SELLs found!")
        return
    
    # Group BUYs by trade_group_id
    buy_groups = {}
    for buy in channel_buys:
        group_id = buy.get("trade_group_id")
        if group_id:
            if group_id not in buy_groups:
                buy_groups[group_id] = []
            buy_groups[group_id].append(buy)
    
    # Find SELLs that already have group_id
    sells_with_group = set()
    for sell in channel_sells:
        if sell.get("trade_group_id"):
            sells_with_group.add(sell["trade_group_id"])
    
    # Find open positions (BUYs without matching SELLs)
    open_positions = {}
    for group_id, buys in buy_groups.items():
        if group_id not in sells_with_group:
            # Use the earliest BUY for matching
            earliest_buy = min(buys, key=lambda x: x["created_at"])
            symbol = earliest_buy["symbol"]
            if symbol not in open_positions:
                open_positions[symbol] = []
            open_positions[symbol].append({
                "group_id": group_id,
                "buy_time": earliest_buy["created_at"],
                "buy_price": earliest_buy["price"],
                "amount": sum(float(b["amount"]) for b in buys),
                "trade_id": earliest_buy["trade_id"]
            })
    
    print(f"\nFound {sum(len(v) for v in open_positions.values())} open positions to match")
    
    # Match orphaned SELLs to open positions
    matches = []
    unmatched_sells = []
    
    for sell in orphaned_sells:
        sell_symbol = sell["symbol"]
        sell_time = sell["created_at"]
        sell_amount = float(sell["amount"])
        
        # Find matching open position for this symbol
        if sell_symbol in open_positions:
            # Find the best match based on timing and amount
            best_match = None
            best_score = float('inf')
            
            for pos in open_positions[sell_symbol]:
                # Position must have opened before the sell
                if pos["buy_time"] < sell_time:
                    # Calculate time difference in hours
                    buy_dt = datetime.fromisoformat(pos["buy_time"].replace("Z", "+00:00"))
                    sell_dt = datetime.fromisoformat(sell_time.replace("Z", "+00:00"))
                    time_diff = (sell_dt - buy_dt).total_seconds() / 3600
                    
                    # Amount should be close (within 1% due to rounding)
                    amount_diff = abs(sell_amount - pos["amount"]) / pos["amount"] if pos["amount"] > 0 else 1
                    
                    # Score based on time (prefer older positions) and amount match
                    score = time_diff * 0.1 + amount_diff * 100
                    
                    if score < best_score and amount_diff < 0.01:  # Amount must match within 1%
                        best_match = pos
                        best_score = score
            
            if best_match:
                matches.append({
                    "sell_id": sell["trade_id"],
                    "group_id": best_match["group_id"],
                    "symbol": sell_symbol,
                    "sell_time": sell_time,
                    "buy_time": best_match["buy_time"]
                })
                # Remove this position from available matches
                open_positions[sell_symbol].remove(best_match)
                if not open_positions[sell_symbol]:
                    del open_positions[sell_symbol]
            else:
                unmatched_sells.append(sell)
        else:
            unmatched_sells.append(sell)
    
    print(f"\n✅ Found {len(matches)} matches")
    print(f"❌ Could not match {len(unmatched_sells)} SELLs")
    
    if matches:
        print("\nFirst 10 matches to be fixed:")
        for i, match in enumerate(matches[:10]):
            print(f"  {i+1}. {match['symbol']}: SELL {match['sell_time'][:19]} → Group {match['group_id'][-6:]}")
        
        # Ask for confirmation
        print(f"\n⚠️  This will update {len(matches)} SELL trades in the database.")
        response = input("Proceed with fixing? (yes/no): ")
        
        if response.lower() == "yes":
            print("\nUpdating database...")
            success_count = 0
            error_count = 0
            
            for match in matches:
                try:
                    # Update the SELL trade with the matching trade_group_id
                    result = (
                        db.client.table("paper_trades")
                        .update({"trade_group_id": match["group_id"]})
                        .eq("trade_id", match["sell_id"])
                        .execute()
                    )
                    success_count += 1
                    print(f"  ✅ Fixed {match['symbol']} SELL → {match['group_id'][-6:]}")
                except Exception as e:
                    error_count += 1
                    print(f"  ❌ Failed to fix {match['symbol']}: {e}")
            
            print(f"\n" + "="*60)
            print("RESULTS:")
            print(f"✅ Successfully fixed: {success_count} trades")
            if error_count > 0:
                print(f"❌ Failed: {error_count} trades")
            
            # Show impact
            remaining_open = sum(len(v) for v in open_positions.values())
            print(f"\n📊 IMPACT:")
            print(f"  Open CHANNEL positions before: 87")
            print(f"  Positions closed by this fix: {success_count}")
            print(f"  Estimated remaining open: {87 - success_count}")
            print(f"  Trading capacity freed up: {success_count} slots")
            
        else:
            print("\n❌ Operation cancelled")
    
    if unmatched_sells:
        print(f"\n⚠️  {len(unmatched_sells)} SELLs could not be matched:")
        print("These may be from different strategies or have data issues")
        for sell in unmatched_sells[:5]:
            print(f"  - {sell['symbol']} at {sell['created_at'][:19]}")


if __name__ == "__main__":
    main()
