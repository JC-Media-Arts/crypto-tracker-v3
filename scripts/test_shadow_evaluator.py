#!/usr/bin/env python3
"""
Test script to manually run shadow evaluation
Helps debug why evaluations aren't happening
"""

import asyncio
from datetime import datetime, timedelta
from src.data.supabase_client import SupabaseClient
from src.analysis.shadow_evaluator import ShadowEvaluator
from loguru import logger

async def test_evaluation():
    """Test shadow evaluation with detailed logging"""
    
    print("=" * 60)
    print("SHADOW EVALUATOR TEST")
    print("=" * 60)
    
    client = SupabaseClient()
    evaluator = ShadowEvaluator(client)
    
    # First, check what shadows are waiting
    print("\n1. CHECKING PENDING SHADOWS:")
    print("-" * 40)
    
    cutoff = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
    waiting = client.client.table("shadow_variations").select("*").eq("would_take_trade", True).lt("created_at", cutoff).limit(10).execute()
    
    if not waiting.data:
        print("   No shadows ready for evaluation")
        return
    
    print(f"   Found {len(waiting.data)} shadows ready for evaluation")
    
    # Show details of first shadow
    shadow = waiting.data[0]
    print(f"\n   Testing with Shadow ID: {shadow['shadow_id']}")
    print(f"   Scan ID: {shadow['scan_id']}")
    print(f"   Created: {shadow['created_at'][:19]}")
    print(f"   Variation: {shadow['variation_name']}")
    
    # Get scan details
    scan_result = client.client.table("scan_history").select("*").eq("scan_id", shadow["scan_id"]).execute()
    
    if scan_result.data:
        scan = scan_result.data[0]
        print(f"   Symbol: {scan.get('symbol')}")
        print(f"   Strategy: {scan.get('strategy_name')}")
        print(f"   Entry Price: {scan.get('entry_price')}")
    
    # Now try to evaluate
    print("\n2. ATTEMPTING EVALUATION:")
    print("-" * 40)
    
    try:
        # Run the evaluator
        outcomes = await evaluator.evaluate_pending_shadows()
        
        print(f"\n   Evaluation complete!")
        print(f"   Evaluated: {len(outcomes)} shadows")
        
        # Check if any outcomes were created
        outcomes = client.client.table("shadow_outcomes").select("*").order("evaluated_at", desc=True).limit(5).execute()
        
        if outcomes.data:
            print(f"\n3. OUTCOMES CREATED:")
            print("-" * 40)
            for outcome in outcomes.data:
                print(f"   Shadow {outcome['shadow_id']}: {outcome['outcome_status']}")
                print(f"     P&L: {outcome.get('pnl_percentage', 0):.2f}%")
                print(f"     Exit: {outcome.get('exit_trigger')}")
        else:
            print("\n   ⚠️  No outcomes created - check logs for errors")
            
    except Exception as e:
        print(f"\n   ❌ ERROR during evaluation: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    print("Starting Shadow Evaluator Test...")
    asyncio.run(test_evaluation())
