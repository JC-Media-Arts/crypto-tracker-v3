#!/usr/bin/env python3
"""
Test the complete Shadow Testing system to verify it's working end-to-end.
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.supabase_client import SupabaseClient

def test_shadow_system():
    """Test complete Shadow Testing system."""
    
    # Initialize Supabase
    client = SupabaseClient()
    
    print("\n" + "="*60)
    print("COMPLETE SHADOW TESTING SYSTEM CHECK")
    print("="*60)
    
    # 1. Check if scans are being created
    print("\n1. RECENT SCANS (Paper Trading Output):")
    print("-" * 40)
    
    try:
        recent_scans = client.client.table("scan_history").select(
            "scan_id, symbol, strategy, created_at, signal_strength"
        ).gte(
            "created_at", 
            (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        ).limit(5).execute()
        
        if recent_scans.data:
            print(f"✅ Found {len(recent_scans.data)} recent scans")
            for scan in recent_scans.data[:3]:
                print(f"  - {scan['symbol']} ({scan['strategy']}) - Signal: {scan['signal_strength']:.2f}")
        else:
            print("❌ No recent scans found")
    except Exception as e:
        print(f"❌ Error checking scans: {e}")
    
    # 2. Check shadow variations being created
    print("\n2. SHADOW VARIATIONS (R&D Analysis):")
    print("-" * 40)
    
    try:
        recent_shadows = client.client.table("shadow_variations").select(
            "shadow_id, scan_id, variation_type, variation_name, created_at"
        ).gte(
            "created_at",
            (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        ).limit(10).execute()
        
        if recent_shadows.data:
            print(f"✅ Found {len(recent_shadows.data)} shadow variations")
            
            # Count by variation type
            variation_types = {}
            for shadow in recent_shadows.data:
                vtype = shadow['variation_type']
                variation_types[vtype] = variation_types.get(vtype, 0) + 1
            
            print("  Variation types created:")
            for vtype, count in variation_types.items():
                print(f"    - {vtype}: {count}")
        else:
            print("❌ No shadow variations created yet")
    except Exception as e:
        print(f"❌ Error checking shadows: {e}")
    
    # 3. Check shadow outcomes evaluation
    print("\n3. SHADOW OUTCOMES (Performance Tracking):")
    print("-" * 40)
    
    try:
        shadow_outcomes = client.client.table("shadow_outcomes").select(
            "outcome_id, shadow_id, outcome, actual_pnl_pct, evaluated_at"
        ).limit(10).execute()
        
        if shadow_outcomes.data:
            print(f"✅ Found {len(shadow_outcomes.data)} evaluated outcomes")
            
            # Count outcomes
            outcome_counts = {}
            for outcome in shadow_outcomes.data:
                status = outcome['outcome']
                outcome_counts[status] = outcome_counts.get(status, 0) + 1
            
            print("  Outcome distribution:")
            for status, count in outcome_counts.items():
                print(f"    - {status}: {count}")
        else:
            print("❌ No outcomes evaluated yet (this is normal early on)")
    except Exception as e:
        print(f"❌ Error checking outcomes: {e}")
    
    # 4. Check shadow performance aggregation
    print("\n4. SHADOW PERFORMANCE (Aggregated Results):")
    print("-" * 40)
    
    try:
        performance = client.client.table("shadow_performance").select(
            "variation_name, win_rate, avg_pnl, total_trades, last_updated"
        ).limit(8).execute()
        
        if performance.data:
            print(f"✅ Found performance data for {len(performance.data)} variations")
            for perf in performance.data[:5]:
                if perf['total_trades'] > 0:
                    print(f"  - {perf['variation_name']}: Win Rate {perf['win_rate']:.1%}, "
                          f"Avg P&L {perf['avg_pnl']:.2%} ({perf['total_trades']} trades)")
        else:
            print("❌ No performance data aggregated yet")
    except Exception as e:
        print(f"❌ Error checking performance: {e}")
    
    # 5. Check threshold adjustments recommendations
    print("\n5. THRESHOLD ADJUSTMENTS (Recommendations):")
    print("-" * 40)
    
    try:
        adjustments = client.client.table("threshold_adjustments").select(
            "adjustment_id, strategy_name, parameter_name, current_value, recommended_value, confidence, reason"
        ).gte(
            "created_at",
            (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        ).limit(5).execute()
        
        if adjustments.data:
            print(f"✅ Found {len(adjustments.data)} recommendations")
            for adj in adjustments.data:
                if adj['parameter_name']:
                    print(f"  - {adj['strategy_name']}: {adj['parameter_name']}")
                    print(f"    Current: {adj['current_value']}, Recommended: {adj['recommended_value']}")
                    print(f"    Confidence: {adj['confidence']:.1%}, Reason: {adj['reason']}")
        else:
            print("❌ No threshold recommendations yet (needs more data)")
    except Exception as e:
        print(f"❌ Error checking adjustments: {e}")
    
    # 6. Check system services
    print("\n6. SYSTEM SERVICES STATUS:")
    print("-" * 40)
    
    try:
        heartbeats = client.client.table("system_heartbeat").select(
            "service_name, status, last_heartbeat"
        ).in_(
            "service_name", 
            ["shadow_monitor", "shadow_evaluator", "shadow_analyzer"]
        ).execute()
        
        if heartbeats.data:
            for service in heartbeats.data:
                last_beat = datetime.fromisoformat(service['last_heartbeat'].replace('Z', '+00:00'))
                age = (datetime.now(timezone.utc) - last_beat).total_seconds()
                
                if age < 120:  # Active if heartbeat within 2 minutes
                    print(f"  ✅ {service['service_name']}: {service['status']} (active)")
                else:
                    print(f"  ⚠️ {service['service_name']}: Last seen {age/60:.0f} min ago")
        else:
            print("  ❌ No shadow services reporting")
    except Exception as e:
        print(f"❌ Error checking services: {e}")
    
    # Summary
    print("\n" + "="*60)
    print("SHADOW TESTING PIPELINE STATUS:")
    print("-" * 60)
    print("1. Paper Trading → scan_history: Creating scans")
    print("2. Shadow Monitor → shadow_variations: Creating variations") 
    print("3. Shadow Evaluator → shadow_outcomes: Evaluating results")
    print("4. Shadow Analyzer → shadow_performance: Aggregating performance")
    print("5. Threshold Manager → threshold_adjustments: Making recommendations")
    print("="*60)

if __name__ == "__main__":
    load_dotenv()
    test_shadow_system()
