#!/usr/bin/env python3
"""
Check paper trading thresholds to verify unified config usage
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from src.config.config_loader import ConfigLoader


def main():
    # Initialize
    supabase = SupabaseClient()
    config_loader = ConfigLoader()
    
    # Load unified config
    config = config_loader.load()
    
    print("=" * 80)
    print("PAPER TRADING THRESHOLD VERIFICATION")
    print("=" * 80)
    
    # Print expected thresholds from unified config
    print("\nEXPECTED THRESHOLDS FROM UNIFIED CONFIG:")
    print("-" * 40)
    
    for strategy in ["DCA", "SWING", "CHANNEL"]:
        if strategy in config["strategies"]:
            print(f"\n{strategy} Strategy:")
            exits = config["strategies"][strategy].get("exits_by_tier", {})
            for tier, params in exits.items():
                tp = params.get("take_profit", 0) * 100
                sl = params.get("stop_loss", 0) * 100
                print(f"  {tier:10s}: TP={tp:5.1f}%, SL={sl:5.1f}%")
    
    # Get recent trades (last 24 hours)
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
    
    print("\n" + "=" * 80)
    print("RECENT TRADES (LAST 24 HOURS):")
    print("-" * 40)
    
    response = supabase.client.table("paper_trades")\
        .select("*")\
        .gte("created_at", cutoff_time.isoformat())\
        .eq("side", "BUY")\
        .order("created_at", desc=True)\
        .execute()
    
    if response.data:
        print(f"Found {len(response.data)} recent BUY trades")
        for trade in response.data[:10]:  # Show first 10
            symbol = trade["symbol"]
            strategy = trade.get("strategy_name", "UNKNOWN")
            # Calculate percentages from price values
            entry_price = trade.get("price", 0)
            tp_price = trade.get("take_profit", 0)
            sl_price = trade.get("stop_loss", 0)
            
            tp = ((tp_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
            sl = ((entry_price - sl_price) / entry_price * 100) if entry_price > 0 else 0
            created = trade["created_at"]
            
            # Determine market cap tier
            tier = "unknown"
            for t, symbols in config["market_cap_tiers"].items():
                if symbol in symbols:
                    tier = t
                    break
            
            print(f"\n{symbol:6s} ({tier:10s}) - {strategy:8s} - Created: {created}")
            print(f"  Actual: TP={tp:5.1f}%, SL={sl:5.1f}%")
            
            # Compare with expected
            if strategy in config["strategies"]:
                expected_exits = config["strategies"][strategy].get("exits_by_tier", {}).get(tier, {})
                expected_tp = expected_exits.get("take_profit", 0) * 100
                expected_sl = expected_exits.get("stop_loss", 0) * 100
                print(f"  Expected: TP={expected_tp:5.1f}%, SL={expected_sl:5.1f}%")
                
                if abs(tp - expected_tp) > 0.1 or abs(sl - expected_sl) > 0.1:
                    print(f"  ⚠️  MISMATCH DETECTED!")
                else:
                    print(f"  ✓ Matches unified config")
    else:
        print("No recent trades found")
    
    # Get all open positions
    print("\n" + "=" * 80)
    print("CURRENT OPEN POSITIONS:")
    print("-" * 40)
    
    response = supabase.client.table("paper_trades")\
        .select("*")\
        .eq("side", "BUY")\
        .eq("status", "FILLED")\
        .filter("pnl", "is", "null")\
        .order("created_at", desc=True)\
        .execute()
    
    if response.data:
        print(f"Found {len(response.data)} open positions")
        
        # Group by creation date
        old_trades = []
        new_trades = []
        
        for trade in response.data:
            created_dt = datetime.fromisoformat(trade["created_at"].replace('Z', '+00:00'))
            if created_dt < cutoff_time:
                old_trades.append(trade)
            else:
                new_trades.append(trade)
        
        print(f"  - Old trades (before redeployment): {len(old_trades)}")
        print(f"  - New trades (after redeployment): {len(new_trades)}")
        
        # Show sample of trades by strategy
        strategies = {}
        for trade in response.data:
            strategy = trade.get("strategy_name", "UNKNOWN")
            if strategy not in strategies:
                strategies[strategy] = []
            strategies[strategy].append(trade)
        
        for strategy, trades in strategies.items():
            print(f"\n{strategy} positions ({len(trades)} total):")
            for trade in trades[:3]:  # Show first 3 of each
                symbol = trade["symbol"]
                # Calculate percentages from price values
                entry_price = trade.get("price", 0)
                tp_price = trade.get("take_profit", 0)
                sl_price = trade.get("stop_loss", 0)
                
                tp = ((tp_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
                sl = ((entry_price - sl_price) / entry_price * 100) if entry_price > 0 else 0
                created = trade["created_at"]
                
                # Determine tier
                tier = "unknown"
                for t, symbols in config["market_cap_tiers"].items():
                    if symbol in symbols:
                        tier = t
                        break
                
                print(f"  {symbol:6s} ({tier:10s}): TP={tp:5.1f}%, SL={sl:5.1f}% - Created: {created}")


if __name__ == "__main__":
    main()
