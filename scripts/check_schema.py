#!/usr/bin/env python3
"""
Check if Supabase schema cache has refreshed and all columns are accessible
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient


def check_schema():
    """Test if we can access all the columns we added"""
    
    print("=" * 60)
    print("🔍 SCHEMA VALIDATION CHECK")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)
    
    supabase = SupabaseClient()
    
    # Test data for insertion
    test_data = {
        "strategy_name": "TEST",
        "symbol": "BTC",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "signal_detected": False,
        "signal_strength": "weak",
        "confidence_score": 0.5,  # New column
        "metadata": {"test": True}  # New column
    }
    
    print("\n1. Testing scan_history table:")
    print("-" * 40)
    
    try:
        # Try to insert with all columns
        result = supabase.client.table("scan_history").insert(test_data).execute()
        print("   ✅ Successfully inserted with all columns!")
        print("   Schema cache appears to be refreshed!")
        
        # Clean up test data
        try:
            supabase.client.table("scan_history") \
                .delete() \
                .eq("strategy_name", "TEST") \
                .eq("metadata", {"test": True}) \
                .execute()
            print("   ✅ Test data cleaned up")
        except:
            pass
            
    except Exception as e:
        if "schema cache" in str(e):
            print("   ❌ Schema cache not refreshed yet")
            print(f"   Error: {str(e)[:100]}")
        elif "column" in str(e) and "does not exist" in str(e):
            print("   ❌ Column still not recognized")
            print(f"   Error: {str(e)[:100]}")
        else:
            print("   ⚠️  Different error:")
            print(f"   {str(e)[:200]}")
    
    # Test shadow_testing_scans
    print("\n2. Testing shadow_testing_scans table:")
    print("-" * 40)
    
    shadow_test_data = {
        "strategy_name": "TEST",
        "symbol": "BTC",
        "timeframe": "15m",
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "signal_detected": False,
        "confidence": 0.5,
        "metadata": {"test": True}
    }
    
    try:
        result = supabase.client.table("shadow_testing_scans").insert(shadow_test_data).execute()
        print("   ✅ Successfully inserted into shadow_testing_scans!")
        
        # Clean up
        try:
            supabase.client.table("shadow_testing_scans") \
                .delete() \
                .eq("strategy_name", "TEST") \
                .execute()
            print("   ✅ Test data cleaned up")
        except:
            pass
            
    except Exception as e:
        if "relation" in str(e) and "does not exist" in str(e):
            print("   ❌ Table doesn't exist")
        else:
            print(f"   ❌ Error: {str(e)[:100]}")
    
    # Test trade_logs columns
    print("\n3. Testing trade_logs columns:")
    print("-" * 40)
    
    try:
        # Try to query the new columns
        result = supabase.client.table("trade_logs") \
            .select("id, pnl, stop_loss_price, take_profit_price") \
            .limit(1) \
            .execute()
        print("   ✅ New columns (pnl, stop_loss_price, etc.) are accessible!")
    except Exception as e:
        if "column" in str(e):
            print("   ❌ Some columns not accessible")
            print(f"   Error: {str(e)[:100]}")
        else:
            print(f"   ⚠️  Error: {str(e)[:100]}")
    
    # Check what's actually in scan_history
    print("\n4. Checking scan_history structure:")
    print("-" * 40)
    
    try:
        # Get a sample record to see structure
        result = supabase.client.table("scan_history") \
            .select("*") \
            .limit(1) \
            .execute()
        
        if result.data and len(result.data) > 0:
            columns = list(result.data[0].keys())
            print(f"   Available columns: {', '.join(columns)}")
            
            # Check for our new columns
            has_confidence = "confidence_score" in columns
            has_metadata = "metadata" in columns
            
            if has_confidence and has_metadata:
                print("   ✅ All new columns are present!")
            else:
                missing = []
                if not has_confidence:
                    missing.append("confidence_score")
                if not has_metadata:
                    missing.append("metadata")
                print(f"   ⚠️  Missing columns: {', '.join(missing)}")
        else:
            print("   No data to check structure")
            
    except Exception as e:
        print(f"   Error checking structure: {str(e)[:100]}")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SCHEMA STATUS SUMMARY")
    print("=" * 60)
    
    print("\nIf you're still seeing schema cache errors:")
    print("1. Go to Supabase Dashboard")
    print("2. Navigate to: Settings → API")
    print("3. Click 'Reload Schema' button")
    print("4. Wait 2-3 minutes")
    print("5. Run this script again")
    
    print("\nAlternatively, the cache usually auto-refreshes within 5-10 minutes.")


if __name__ == "__main__":
    check_schema()
