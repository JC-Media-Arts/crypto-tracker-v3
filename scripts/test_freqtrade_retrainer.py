#!/usr/bin/env python3
"""
Test the updated SimpleRetrainer with Freqtrade data
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from src.ml.simple_retrainer import SimpleRetrainer
from loguru import logger


def test_retrainer():
    """Test the Freqtrade-updated retrainer"""
    
    print("\n" + "="*60)
    print("🧪 TESTING FREQTRADE ML RETRAINER")
    print("="*60)
    
    # Initialize components
    supabase = SupabaseClient()
    retrainer = SimpleRetrainer(supabase.client)
    
    # Check if Freqtrade database exists
    if not retrainer.freqtrade_db.exists():
        print(f"\n❌ Freqtrade database not found at: {retrainer.freqtrade_db}")
        print("   Freqtrade needs to run and generate trades first")
        return
    
    print(f"\n✅ Freqtrade database found: {retrainer.freqtrade_db}")
    
    # Test 1: Check if we should retrain
    print("\n📊 Test 1: Check retrain status")
    print("-" * 40)
    
    should_retrain, count = retrainer.should_retrain("CHANNEL")
    print(f"Strategy: CHANNEL")
    print(f"New trades available: {count}")
    print(f"Minimum required: {retrainer.min_new_samples}")
    print(f"Should retrain: {'✅ Yes' if should_retrain else '❌ No'}")
    
    # Test 2: Load training data
    print("\n📊 Test 2: Load training data")
    print("-" * 40)
    
    training_data = retrainer._get_all_training_data("CHANNEL")
    
    if training_data.empty:
        print("❌ No training data available")
    else:
        print(f"✅ Loaded {len(training_data)} trades")
        
        # Show sample of data
        print("\nSample trade data:")
        sample = training_data.head(3)
        for idx, row in sample.iterrows():
            print(f"\n  Trade {idx + 1}:")
            print(f"    Symbol: {row['symbol']}")
            print(f"    Entry: {row['entry_time']}")
            print(f"    Profit: {row['profit_pct']:.2%}")
            print(f"    Outcome: {row['outcome_label']}")
            print(f"    Features: {len(row.get('features', {})) if row.get('features') else 0} features")
    
    # Test 3: Check scan_history
    print("\n📊 Test 3: Check scan_history data")
    print("-" * 40)
    
    result = supabase.client.table("scan_history").select("*", count="exact").limit(1).execute()
    scan_count = result.count if hasattr(result, 'count') else 0
    
    print(f"Total scans in database: {scan_count:,}")
    
    if scan_count > 0:
        # Get a recent scan to show available features
        recent = supabase.client.table("scan_history").select("*").order("timestamp", desc=True).limit(1).execute()
        if recent.data:
            scan = recent.data[0]
            print(f"\nAvailable features in scan_history:")
            feature_keys = [k for k in scan.keys() if k not in ['id', 'timestamp', 'created_at', 'symbol', 'strategy_name']]
            for i in range(0, len(feature_keys), 3):
                batch = feature_keys[i:i+3]
                print(f"  {', '.join(batch)}")
    
    # Test 4: Attempt retraining if enough data
    if should_retrain:
        print("\n📊 Test 4: Attempt retraining")
        print("-" * 40)
        
        response = input("Do you want to attempt retraining? (yes/no): ")
        if response.lower() == 'yes':
            result = retrainer.retrain("CHANNEL")
            print(f"\nRetraining result: {result}")
    else:
        print("\n⏳ Not enough data for retraining yet")
        print(f"   Need {retrainer.min_new_samples - count} more trades")
    
    print("\n" + "="*60)
    print("✅ Test complete!")


if __name__ == "__main__":
    test_retrainer()
