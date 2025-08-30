#!/usr/bin/env python3
"""
Test Shadow Testing Integration with Freqtrade
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from src.analysis.shadow_evaluator import ShadowEvaluator
from scripts.shadow_scan_monitor import ShadowScanMonitor
from datetime import datetime, timezone, timedelta
import asyncio


async def test_shadow_testing():
    """Test shadow testing components"""
    
    print("\n" + "="*60)
    print("🔬 TESTING SHADOW TESTING INTEGRATION")
    print("="*60)
    
    db = SupabaseClient()
    
    # 1. Check shadow monitor
    print("\n1️⃣ Testing Shadow Monitor...")
    try:
        monitor = ShadowScanMonitor()
        unprocessed = await monitor.get_unprocessed_scans()
        print(f"   ✅ Monitor working")
        print(f"   Unprocessed scans: {len(unprocessed)}")
        
        if unprocessed:
            # Try creating shadows for one scan
            scan = unprocessed[0]
            print(f"   Testing shadow creation for {scan['symbol']}...")
            success = await monitor.create_shadows_for_scan(scan)
            if success:
                print(f"   ✅ Shadow variations created successfully")
            else:
                print(f"   ⚠️ Failed to create shadows")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # 2. Check shadow evaluator
    print("\n2️⃣ Testing Shadow Evaluator...")
    try:
        evaluator = ShadowEvaluator(db.client)
        
        # Get pending shadows
        cutoff_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        result = db.client.table("shadow_variations")\
            .select("*")\
            .eq("would_take_trade", True)\
            .lt("created_at", cutoff_time)\
            .limit(10)\
            .execute()
        
        pending_count = len(result.data) if result.data else 0
        print(f"   ✅ Evaluator accessible")
        print(f"   Pending evaluations: {pending_count}")
        
        if pending_count > 0:
            print(f"   Ready to evaluate shadow trades")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # 3. Check data flow
    print("\n3️⃣ Checking Data Flow...")
    
    # Check scan_history -> shadow_variations
    scan_result = db.client.table("scan_history")\
        .select("scan_id, symbol, timestamp")\
        .order("timestamp", desc=True)\
        .limit(1)\
        .execute()
    
    if scan_result.data:
        scan = scan_result.data[0]
        
        # Check if this scan has shadows
        shadow_result = db.client.table("shadow_variations")\
            .select("*", count="exact")\
            .eq("scan_id", scan['scan_id'])\
            .execute()
        
        shadow_count = shadow_result.count if hasattr(shadow_result, 'count') else 0
        
        print(f"   Latest scan: {scan['symbol']} at {scan['timestamp'][:19]}")
        print(f"   Shadow variations: {shadow_count}")
        
        if shadow_count > 0:
            print(f"   ✅ Scan → Shadow flow working")
        else:
            print(f"   ⚠️ No shadows for latest scan")
    
    # 4. Check statistics
    print("\n4️⃣ Shadow Testing Statistics...")
    
    # Total shadows created
    total_shadows = db.client.table("shadow_variations")\
        .select("*", count="exact")\
        .limit(1)\
        .execute()
    total_count = total_shadows.count if hasattr(total_shadows, 'count') else 0
    
    # Shadows that would take trades
    would_trade = db.client.table("shadow_variations")\
        .select("*", count="exact")\
        .eq("would_take_trade", True)\
        .limit(1)\
        .execute()
    trade_count = would_trade.count if hasattr(would_trade, 'count') else 0
    
    # Evaluated shadows
    outcomes = db.client.table("shadow_outcomes")\
        .select("*", count="exact")\
        .limit(1)\
        .execute()
    outcome_count = outcomes.count if hasattr(outcomes, 'count') else 0
    
    print(f"   Total shadow variations: {total_count:,}")
    print(f"   Would take trade: {trade_count:,}")
    print(f"   Evaluated outcomes: {outcome_count:,}")
    
    if outcome_count == 0 and trade_count > 0:
        print(f"\n   ⚠️ Shadow evaluator needs to run to evaluate {trade_count} pending trades")
    
    print("\n" + "="*60)
    print("📊 SUMMARY")
    print("="*60)
    
    if total_count > 0:
        print("\n✅ Shadow testing is working with Freqtrade scans!")
        print("\n📝 Status:")
        print(f"   • Creating shadow variations: ✅")
        print(f"   • Pending evaluations: {trade_count}")
        print(f"   • Completed evaluations: {outcome_count}")
        
        if outcome_count == 0:
            print("\n💡 To complete the shadow testing loop:")
            print("   1. Run the shadow evaluator service")
            print("   2. It will evaluate pending shadows after 5+ minutes")
            print("   3. Results will appear in shadow_outcomes table")
    else:
        print("\n⚠️ No shadow data yet. Let the system run longer.")


if __name__ == "__main__":
    asyncio.run(test_shadow_testing())
