#!/usr/bin/env python3
"""
Fix SELL trades with NULL trade_group_id by matching them to their corresponding BUY trades.
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data.supabase_client import SupabaseClient
from loguru import logger

load_dotenv()


def main():
    """Fix NULL trade_group_ids in SELL trades"""
    db = SupabaseClient()
    
    print("\n" + "="*60)
    print("FIXING NULL TRADE_GROUP_IDS IN SELL TRADES")
    print("="*60)
    
    # Get all SELLs with NULL trade_group_id
    print("\nFinding SELLs with NULL trade_group_id...")
    null_sells = (
        db.client.table("paper_trades")
        .select("*")
        .eq("side", "SELL")
        .is_("trade_group_id", "null")
        .order("created_at", desc=False)
        .execute()
    ).data
    
    print(f"Found {len(null_sells)} SELL trades with NULL trade_group_id")
    
    if not null_sells:
        print("No NULL trade_group_ids found!")
        return
    
    # Show what we found
    print("\nSELLs to fix:")
    symbols_to_fix = {}
    for sell in null_sells:
        symbol = sell["symbol"]
        if symbol not in symbols_to_fix:
            symbols_to_fix[symbol] = []
        symbols_to_fix[symbol].append(sell)
    
    for symbol, sells in symbols_to_fix.items():
        print(f"  {symbol}: {len(sells)} SELL(s)")
    
    # Get all BUY trades
    print("\nLoading all BUY trades...")
    all_buys = (
        db.client.table("paper_trades")
        .select("*")
        .eq("side", "BUY")
        .order("created_at", desc=False)
        .execute()
    ).data
    
    print(f"Found {len(all_buys)} total BUY trades")
    
    # Get all SELLs with trade_group_id to know which positions are closed
    sells_with_group = (
        db.client.table("paper_trades")
        .select("trade_group_id")
        .eq("side", "SELL")
        .not_.is_("trade_group_id", "null")
        .execute()
    ).data
    
    closed_groups = {s["trade_group_id"] for s in sells_with_group}
    print(f"Found {len(closed_groups)} already closed positions")
    
    # Find open BUY positions (those without matching SELLs)
    open_buys = {}
    for buy in all_buys:
        group_id = buy.get("trade_group_id")
        if group_id and group_id not in closed_groups:
            symbol = buy["symbol"]
            if symbol not in open_buys:
                open_buys[symbol] = []
            open_buys[symbol].append(buy)
    
    print(f"Found open positions for {len(open_buys)} symbols")
    
    # Match NULL SELLs to open BUYs
    matches = []
    unmatched = []
    
    for sell in null_sells:
        sell_symbol = sell["symbol"]
        sell_time = sell["created_at"]
        sell_amount = float(sell.get("amount", 0))
        sell_price = float(sell.get("price", 0))
        
        # Find open BUYs for this symbol
        if sell_symbol in open_buys:
            best_match = None
            best_score = float('inf')
            
            for buy in open_buys[sell_symbol]:
                buy_time = buy["created_at"]
                buy_amount = float(buy.get("amount", 0))
                
                # BUY must be before SELL
                if buy_time < sell_time:
                    # Calculate time difference in hours
                    buy_dt = datetime.fromisoformat(buy_time.replace("Z", "+00:00"))
                    sell_dt = datetime.fromisoformat(sell_time.replace("Z", "+00:00"))
                    time_diff_hours = (sell_dt - buy_dt).total_seconds() / 3600
                    
                    # Amount should match closely (within 5% for rounding)
                    if buy_amount > 0:
                        amount_diff = abs(sell_amount - buy_amount) / buy_amount
                    else:
                        amount_diff = 1.0
                    
                    # Prefer matches with similar amounts and reasonable time gaps
                    # Most positions close within 72 hours
                    if amount_diff < 0.05 and time_diff_hours > 0 and time_diff_hours < 200:
                        score = time_diff_hours + (amount_diff * 1000)
                        if score < best_score:
                            best_match = buy
                            best_score = score
            
            if best_match:
                matches.append({
                    "sell_id": sell["trade_id"],
                    "sell_symbol": sell_symbol,
                    "sell_time": sell_time,
                    "sell_amount": sell_amount,
                    "sell_price": sell_price,
                    "buy_group_id": best_match["trade_group_id"],
                    "buy_time": best_match["created_at"],
                    "buy_amount": float(best_match.get("amount", 0)),
                    "strategy": best_match.get("strategy_name", "UNKNOWN")
                })
                # Remove this BUY from available matches
                open_buys[sell_symbol].remove(best_match)
                if not open_buys[sell_symbol]:
                    del open_buys[sell_symbol]
            else:
                unmatched.append(sell)
        else:
            unmatched.append(sell)
    
    print(f"\n" + "="*60)
    print("MATCHING RESULTS:")
    print(f"✅ Found matches for {len(matches)} SELLs")
    print(f"❌ Could not match {len(unmatched)} SELLs")
    
    if matches:
        print("\nMatches found (first 10):")
        for i, match in enumerate(matches[:10]):
            time_diff = (datetime.fromisoformat(match["sell_time"].replace("Z", "+00:00")) - 
                        datetime.fromisoformat(match["buy_time"].replace("Z", "+00:00")))
            hours = time_diff.total_seconds() / 3600
            print(f"\n  {i+1}. {match['sell_symbol']} ({match['strategy']})")
            print(f"     BUY:  {match['buy_time'][:19]} - Amount: {match['buy_amount']:.4f}")
            print(f"     SELL: {match['sell_time'][:19]} - Amount: {match['sell_amount']:.4f}")
            print(f"     Hold time: {hours:.1f} hours")
            print(f"     Will assign group: {match['buy_group_id']}")
        
        if len(matches) > 10:
            print(f"\n  ... and {len(matches) - 10} more matches")
        
        # Ask for confirmation
        print(f"\n⚠️  This will update {len(matches)} SELL trades in the database.")
        print("This will properly close these positions and free up trading capacity.")
        response = input("\nProceed with fixing? (yes/no): ")
        
        if response.lower() == "yes":
            print("\nUpdating database...")
            success_count = 0
            error_count = 0
            
            for match in matches:
                try:
                    # Update the SELL trade with the matching trade_group_id
                    result = (
                        db.client.table("paper_trades")
                        .update({"trade_group_id": match["buy_group_id"]})
                        .eq("trade_id", match["sell_id"])
                        .execute()
                    )
                    success_count += 1
                    print(f"  ✅ Fixed {match['sell_symbol']} SELL → {match['buy_group_id'][-6:]}")
                except Exception as e:
                    error_count += 1
                    print(f"  ❌ Failed to fix {match['sell_symbol']}: {e}")
            
            print(f"\n" + "="*60)
            print("FINAL RESULTS:")
            print(f"✅ Successfully fixed: {success_count} trades")
            if error_count > 0:
                print(f"❌ Failed: {error_count} trades")
            
            print(f"\n📊 IMPACT:")
            print(f"  NULL trade_group_ids before: 34")
            print(f"  Fixed: {success_count}")
            print(f"  Remaining: {34 - success_count}")
            print(f"  Open positions closed: {success_count}")
            print(f"\n✨ Your trading system should now have more capacity for new trades!")
            
        else:
            print("\n❌ Operation cancelled")
    
    if unmatched:
        print(f"\n⚠️  Could not match {len(unmatched)} SELLs:")
        print("These may be very old trades or have data issues:")
        for sell in unmatched[:5]:
            print(f"  - {sell['symbol']} at {sell['created_at'][:19]}")


if __name__ == "__main__":
    main()
