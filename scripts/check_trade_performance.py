#!/usr/bin/env python3
"""Check paper trade performance distribution."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient

db = SupabaseClient()

# Check paper_trades P&L distribution
result = db.client.table("paper_trades").select("pnl_usd,pnl_pct,exit_reason,symbol,strategy").eq("action", "SELL").limit(1000).execute()

if result.data:
    wins = sum(1 for t in result.data if t["pnl_usd"] and t["pnl_usd"] > 0)
    losses = sum(1 for t in result.data if t["pnl_usd"] and t["pnl_usd"] <= 0)
    
    print(f"Analysis of {len(result.data)} closed trades:")
    print(f"  Wins: {wins}")
    print(f"  Losses: {losses}")
    if wins + losses > 0:
        print(f"  Win rate: {wins/(wins+losses)*100:.1f}%")
    
    # Show P&L distribution
    pnl_values = [t["pnl_usd"] for t in result.data if t["pnl_usd"] is not None]
    if pnl_values:
        print(f"\nP&L Distribution:")
        print(f"  Min: ${min(pnl_values):.2f}")
        print(f"  Max: ${max(pnl_values):.2f}")
        print(f"  Avg: ${sum(pnl_values)/len(pnl_values):.2f}")
        
        # Count by exit reason
        exit_reasons = {}
        for t in result.data:
            reason = t.get("exit_reason", "unknown")
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
        
        print(f"\nExit reasons:")
        for reason, count in sorted(exit_reasons.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {reason}: {count}")
        
        # Count by strategy
        strategies = {}
        for t in result.data:
            strat = t.get("strategy", "unknown")
            strategies[strat] = strategies.get(strat, 0) + 1
        
        print(f"\nBy Strategy:")
        for strat, count in sorted(strategies.items(), key=lambda x: x[1], reverse=True):
            print(f"  {strat}: {count}")
            
            # Win rate per strategy
            strat_wins = sum(1 for t in result.data if t.get("strategy") == strat and t.get("pnl_usd", 0) > 0)
            if count > 0:
                print(f"    Win rate: {strat_wins/count*100:.1f}%")
