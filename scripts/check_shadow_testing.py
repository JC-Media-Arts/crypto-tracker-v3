#!/usr/bin/env python3
"""
Check if Shadow Testing is actually working and collecting data.
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.supabase_client import SupabaseClient

def check_shadow_testing():
    """Check Shadow Testing system status."""
    
    # Initialize Supabase
    client = SupabaseClient()
    
    print("\n" + "="*60)
    print("SHADOW TESTING SYSTEM CHECK")
    print("="*60)
    
    # 1. Check shadow_variations table
    print("\n1. SHADOW VARIATIONS (Last 24 hours):")
    print("-" * 40)
    
    try:
        # Get count of shadow variations in last 24 hours
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        
        response = client.client.table('shadow_variations').select('*').gte('created_at', yesterday.isoformat()).execute()
        
        if response.data:
            print(f"✅ Found {len(response.data)} shadow variations in last 24 hours")
            
            # Show sample
            if len(response.data) > 0:
                sample = response.data[0]
                print(f"\nSample variation:")
                print(f"  - Variation: {sample.get('variation_name')}")
                print(f"  - Symbol: {sample.get('symbol')}")
                print(f"  - Decision: {sample.get('decision')}")
                print(f"  - Created: {sample.get('created_at')}")
        else:
            print("❌ No shadow variations found in last 24 hours")
            
    except Exception as e:
        print(f"❌ Error checking shadow_variations: {e}")
        print("   Note: Table might not exist or might be named differently")
    
    # 2. Check shadow_outcomes table
    print("\n2. SHADOW OUTCOMES (Evaluated results):")
    print("-" * 40)
    
    try:
        response = client.client.table('shadow_outcomes').select('*').limit(10).order('evaluated_at', desc=True).execute()
        
        if response.data:
            print(f"✅ Found {len(response.data)} recent shadow outcomes")
            
            # Count by outcome
            outcomes = {}
            for item in response.data:
                outcome = item.get('outcome', 'UNKNOWN')
                outcomes[outcome] = outcomes.get(outcome, 0) + 1
            
            print("\nOutcome distribution:")
            for outcome, count in outcomes.items():
                print(f"  - {outcome}: {count}")
        else:
            print("❌ No shadow outcomes found")
            
    except Exception as e:
        print(f"❌ Error checking shadow_outcomes: {e}")
        print("   Note: Table might not exist or might be named differently")
    
    # 3. Check shadow_performance table
    print("\n3. SHADOW PERFORMANCE (Aggregated metrics):")
    print("-" * 40)
    
    try:
        response = client.client.table('shadow_performance').select('*').limit(10).order('calculated_at', desc=True).execute()
        
        if response.data:
            print(f"✅ Found {len(response.data)} performance records")
            
            # Show latest performance
            if len(response.data) > 0:
                latest = response.data[0]
                print(f"\nLatest performance:")
                print(f"  - Variation: {latest.get('variation_name')}")
                print(f"  - Win Rate: {latest.get('win_rate', 0):.1f}%")
                print(f"  - Timeframe: {latest.get('timeframe')}")
                print(f"  - Calculated: {latest.get('calculated_at')}")
        else:
            print("❌ No shadow performance data found")
            
    except Exception as e:
        print(f"❌ Error checking shadow_performance: {e}")
        print("   Note: Table might not exist or might be named differently")
    
    # 4. Check threshold_adjustments table
    print("\n4. THRESHOLD ADJUSTMENTS (Parameter changes):")
    print("-" * 40)
    
    try:
        response = client.client.table('threshold_adjustments').select('*').limit(5).order('adjusted_at', desc=True).execute()
        
        if response.data:
            print(f"✅ Found {len(response.data)} threshold adjustments")
            
            for adj in response.data[:3]:
                print(f"\n  - Parameter: {adj.get('parameter')}")
                print(f"    Old: {adj.get('old_value')} → New: {adj.get('new_value')}")
                print(f"    Reason: {adj.get('reason')}")
        else:
            print("❌ No threshold adjustments found")
            
    except Exception as e:
        print(f"❌ Error checking threshold_adjustments: {e}")
        print("   Note: Table might not exist or might be named differently")
    
    # 5. Check adaptive_thresholds table
    print("\n5. ADAPTIVE THRESHOLDS (Recommendations):")
    print("-" * 40)
    
    try:
        response = client.client.table('adaptive_thresholds').select('*').limit(10).execute()
        
        if response.data:
            print(f"✅ Found {len(response.data)} adaptive threshold recommendations")
            
            # Show a few examples
            for thresh in response.data[:3]:
                if thresh.get('current_value') != thresh.get('optimal_value'):
                    print(f"\n  - {thresh.get('strategy')} / {thresh.get('parameter')}:")
                    print(f"    Current: {thresh.get('current_value')}")
                    print(f"    Optimal: {thresh.get('optimal_value')}")
                    print(f"    Reason: {thresh.get('adjustment_reason', 'N/A')}")
        else:
            print("❌ No adaptive thresholds found")
            
    except Exception as e:
        print(f"❌ Error checking adaptive_thresholds: {e}")
        print("   Note: Table might not exist or might be named differently")
    
    # 6. Check if shadow testing service is running
    print("\n6. SHADOW TESTING SERVICE STATUS:")
    print("-" * 40)
    
    try:
        # Check system_heartbeat for shadow services
        response = client.client.table('system_heartbeat').select('*').like('service_name', '%shadow%').execute()
        
        if response.data:
            print(f"✅ Found {len(response.data)} shadow-related services")
            for service in response.data:
                last_heartbeat = datetime.fromisoformat(service.get('last_heartbeat').replace('Z', '+00:00'))
                age = datetime.now(timezone.utc) - last_heartbeat
                status = "✅ Running" if age.total_seconds() < 600 else "❌ Stopped"
                print(f"  - {service.get('service_name')}: {status} (last: {age.total_seconds():.0f}s ago)")
        else:
            print("⚠️  No shadow services found in heartbeat table")
            
    except Exception as e:
        print(f"⚠️  Could not check service status: {e}")
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    print("""
If you see mostly ❌ above, Shadow Testing might not be running or configured.
To fix:
1. Check if shadow testing tables exist in Supabase
2. Verify shadow testing service is deployed on Railway
3. Check if ENABLE_SHADOW_TESTING=true in environment
4. Review logs for shadow_scan_monitor.py or run_shadow_services.py
    """)

if __name__ == "__main__":
    load_dotenv()
    check_shadow_testing()
