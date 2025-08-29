#!/usr/bin/env python3
"""
Check Shadow Testing data in database with correct column names.
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.supabase_client import SupabaseClient

def check_shadow_data():
    """Check Shadow Testing data."""
    
    # Initialize Supabase
    client = SupabaseClient()
    
    print("\n" + "="*60)
    print("SHADOW TESTING DATA CHECK")
    print("="*60)
    
    # 1. Check shadow variations
    print("\n1. SHADOW VARIATIONS (Last 10):")
    print("-" * 40)
    
    try:
        shadows = client.client.table("shadow_variations").select(
            "shadow_id, scan_id, variation_name, variation_type, would_take_trade, created_at"
        ).order("shadow_id", desc=True).limit(10).execute()
        
        if shadows.data:
            print(f"✅ Found {len(shadows.data)} recent shadow variations")
            
            # Count by type
            type_counts = {}
            trade_counts = {"would_trade": 0, "would_not_trade": 0}
            
            for shadow in shadows.data:
                vtype = shadow['variation_type']
                type_counts[vtype] = type_counts.get(vtype, 0) + 1
                
                if shadow['would_take_trade']:
                    trade_counts["would_trade"] += 1
                else:
                    trade_counts["would_not_trade"] += 1
            
            print(f"\nVariation types:")
            for vtype, count in type_counts.items():
                print(f"  - {vtype}: {count}")
            
            print(f"\nTrade decisions:")
            print(f"  - Would trade: {trade_counts['would_trade']}")
            print(f"  - Would NOT trade: {trade_counts['would_not_trade']}")
            
            print(f"\nLatest variations:")
            for shadow in shadows.data[:5]:
                print(f"  Shadow #{shadow['shadow_id']}: {shadow['variation_name']} "
                      f"({'TRADE' if shadow['would_take_trade'] else 'NO TRADE'})")
        else:
            print("❌ No shadow variations found")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # 2. Count total shadows created
    print("\n2. TOTAL SHADOW VARIATIONS:")
    print("-" * 40)
    
    try:
        # Count total
        total_count = client.client.table("shadow_variations").select(
            "shadow_id", count="exact"
        ).execute()
        
        print(f"✅ Total shadow variations created: {total_count.count}")
        
        # Count by variation name
        variation_counts = client.client.table("shadow_variations").select(
            "variation_name"
        ).execute()
        
        if variation_counts.data:
            name_counts = {}
            for v in variation_counts.data:
                name = v['variation_name']
                name_counts[name] = name_counts.get(name, 0) + 1
            
            print("\nBreakdown by variation name:")
            for name, count in sorted(name_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"  - {name}: {count}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # 3. Check shadow outcomes
    print("\n3. SHADOW OUTCOMES:")
    print("-" * 40)
    
    try:
        outcomes = client.client.table("shadow_outcomes").select(
            "outcome_id, shadow_id, outcome_status, actual_pnl_pct"
        ).limit(10).execute()
        
        if outcomes.data:
            print(f"✅ Found {len(outcomes.data)} shadow outcomes")
            for outcome in outcomes.data[:5]:
                print(f"  Outcome #{outcome['outcome_id']}: {outcome['outcome_status']} "
                      f"(P&L: {outcome['actual_pnl_pct']:.2%} if taken)")
        else:
            print("❌ No outcomes evaluated yet (normal for new shadows)")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # 4. Check scan history
    print("\n4. SCAN HISTORY (Recent):")
    print("-" * 40)
    
    try:
        scans = client.client.table("scan_history").select(
            "scan_id, symbol, strategy_name, signal_strength, created_at"
        ).order("scan_id", desc=True).limit(5).execute()
        
        if scans.data:
            print(f"✅ Found recent scans")
            for scan in scans.data:
                print(f"  Scan #{scan['scan_id']}: {scan['symbol']} ({scan['strategy_name']}) "
                      f"Signal: {scan['signal_strength']:.2f}")
        else:
            print("❌ No recent scans")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    load_dotenv()
    check_shadow_data()
