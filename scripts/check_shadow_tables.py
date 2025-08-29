#!/usr/bin/env python3
"""
Check if Shadow Testing tables exist and their structure.
"""

import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.supabase_client import SupabaseClient

def check_shadow_tables():
    """Check if shadow testing tables exist."""
    
    # Initialize Supabase
    client = SupabaseClient()
    
    print("\n" + "="*60)
    print("SHADOW TESTING TABLE CHECK")
    print("="*60)
    
    # Tables to check
    tables = [
        'shadow_variations',
        'shadow_outcomes', 
        'shadow_performance',
        'threshold_adjustments',
        'shadow_configuration',
        'adaptive_thresholds',
        'learning_history'
    ]
    
    # Views to check
    views = [
        'champion_vs_challengers',
        'shadow_consensus',
        'ml_training_feedback_shadow'
    ]
    
    print("\n1. CHECKING TABLES:")
    print("-" * 40)
    
    for table_name in tables:
        try:
            # Try to query the table
            response = client.client.table(table_name).select('*').limit(1).execute()
            print(f"✅ {table_name}: EXISTS")
        except Exception as e:
            error_msg = str(e)
            if 'not find the table' in error_msg or 'does not exist' in error_msg:
                print(f"❌ {table_name}: DOES NOT EXIST")
            else:
                print(f"⚠️  {table_name}: ERROR - {error_msg[:50]}")
    
    print("\n2. CHECKING VIEWS:")
    print("-" * 40)
    
    for view_name in views:
        try:
            # Try to query the view
            response = client.client.table(view_name).select('*').limit(1).execute()
            print(f"✅ {view_name}: EXISTS")
        except Exception as e:
            error_msg = str(e)
            if 'not find the table' in error_msg or 'does not exist' in error_msg:
                print(f"❌ {view_name}: DOES NOT EXIST")
            else:
                print(f"⚠️  {view_name}: ERROR - {error_msg[:50]}")
    
    # Check if migration was recorded
    print("\n3. CHECKING MIGRATION HISTORY:")
    print("-" * 40)
    
    try:
        response = client.client.table('schema_migrations').select('*').like('migration', '%shadow%').execute()
        if response.data:
            print(f"✅ Found {len(response.data)} shadow-related migrations")
            for migration in response.data:
                print(f"   - {migration.get('migration')}: {migration.get('executed_at')}")
        else:
            print("❌ No shadow-related migrations found in history")
    except Exception as e:
        print(f"⚠️  Could not check migration history: {e}")
        print("   Note: schema_migrations table might not exist")
    
    print("\n" + "="*60)
    print("RECOMMENDATION")
    print("="*60)
    
    print("""
If tables are missing, you need to run the migration:
1. Go to Supabase SQL Editor
2. Run the migration file: migrations/006_create_shadow_testing.sql
3. Verify all tables and views are created

If tables exist but are empty:
1. Check if shadow testing service is running
2. Verify ENABLE_SHADOW_TESTING=true in environment
3. Check logs for shadow_logger.py errors
    """)

if __name__ == "__main__":
    load_dotenv()
    check_shadow_tables()
