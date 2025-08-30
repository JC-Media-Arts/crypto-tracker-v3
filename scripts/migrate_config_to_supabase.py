#!/usr/bin/env python3
"""
Migration script to set up Supabase trading_config table and populate initial data.
Run this once to migrate from file-based to Supabase-based configuration.
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from supabase import create_client
import psycopg2
from psycopg2.extras import Json

# Load environment variables
load_dotenv()


def run_migration():
    """Run the SQL migration to create the trading_config table."""
    print("\n" + "="*60)
    print("Running Database Migration")
    print("="*60)
    
    print("ℹ️  Note: You need to run the SQL migration manually in Supabase")
    print("   1. Go to your Supabase project dashboard")
    print("   2. Navigate to SQL Editor")
    print("   3. Copy and paste the contents of:")
    print(f"      migrations/031_create_trading_config.sql")
    print("   4. Click 'Run' to execute the migration")
    print("\n   OR run this command if you have DATABASE_URL:")
    print("   psql $DATABASE_URL < migrations/031_create_trading_config.sql")
    
    # Check if table exists using Supabase client
    try:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            print("\n⚠️  Cannot verify table creation without Supabase credentials")
            response = input("\nHave you created the table? (y/n): ")
            return response.lower() == 'y'
        
        client = create_client(supabase_url, supabase_key)
        
        # Try to query the table
        response = client.table("trading_config").select("config_key").limit(1).execute()
        print("✅ Table 'trading_config' already exists!")
        return True
        
    except Exception as e:
        if "relation" in str(e) and "does not exist" in str(e):
            print("\n❌ Table 'trading_config' does not exist yet")
            print("   Please create it using the instructions above")
            response = input("\nHave you created the table? (y/n): ")
            return response.lower() == 'y'
        else:
            print(f"⚠️  Could not verify table: {e}")
            response = input("\nDo you want to continue anyway? (y/n): ")
            return response.lower() == 'y'


def populate_initial_config():
    """Populate the trading_config table with current config file."""
    print("\n" + "="*60)
    print("Populating Initial Configuration")
    print("="*60)
    
    # Load current config file
    config_file = Path(__file__).parent.parent / "configs" / "paper_trading_config_unified.json"
    
    if not config_file.exists():
        print(f"❌ Config file not found: {config_file}")
        return False
    
    try:
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        print(f"✅ Loaded config file (version: {config_data.get('version', 'unknown')})")
        
        # Initialize Supabase client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            print("❌ SUPABASE_URL or SUPABASE_KEY not found")
            return False
        
        client = create_client(supabase_url, supabase_key)
        
        # Check if config already exists
        response = client.table("trading_config").select("id").eq("config_key", "active").execute()
        
        if response.data and len(response.data) > 0:
            print("⚠️  Active config already exists, updating...")
            # Update existing
            update_response = client.table("trading_config").update({
                "config_version": config_data.get("version", "1.0.0"),
                "config_data": config_data,
                "updated_by": "migration_script",
                "update_source": "migration",
                "is_valid": True,
                "notes": "Migrated from file-based config"
            }).eq("config_key", "active").execute()
            
            if update_response.data:
                print("✅ Updated existing config in Supabase")
            else:
                print("❌ Failed to update config")
                return False
        else:
            print("Creating new config entry...")
            # Insert new
            insert_response = client.table("trading_config").insert({
                "config_key": "active",
                "config_version": config_data.get("version", "1.0.0"),
                "config_data": config_data,
                "updated_by": "migration_script",
                "update_source": "migration",
                "is_valid": True,
                "environment": "paper",
                "notes": "Initial migration from file-based config"
            }).execute()
            
            if insert_response.data:
                print("✅ Inserted config into Supabase")
            else:
                print("❌ Failed to insert config")
                return False
        
        # Verify
        verify_response = client.table("trading_config").select("config_version, last_updated").eq("config_key", "active").execute()
        
        if verify_response.data and len(verify_response.data) > 0:
            data = verify_response.data[0]
            print(f"✅ Verified config in database:")
            print(f"   Version: {data['config_version']}")
            print(f"   Last Updated: {data['last_updated']}")
            return True
        else:
            print("❌ Could not verify config in database")
            return False
            
    except Exception as e:
        print(f"❌ Failed to populate config: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_access():
    """Test that both ConfigLoader and ConfigBridge can access the config."""
    print("\n" + "="*60)
    print("Testing Config Access")
    print("="*60)
    
    try:
        # Test ConfigLoader
        from src.config.config_loader import ConfigLoader
        loader = ConfigLoader()
        config = loader.load(force_reload=True)
        
        if config:
            print(f"✅ ConfigLoader can access config (version: {config.get('version')})")
        else:
            print("❌ ConfigLoader cannot access config")
            return False
        
        # Test ConfigBridge
        from freqtrade.user_data.config_bridge import ConfigBridge
        bridge = ConfigBridge()
        bridge_config = bridge.get_config()
        
        if bridge_config:
            print(f"✅ ConfigBridge can access config (version: {bridge_config.get('version')})")
        else:
            print("❌ ConfigBridge cannot access config")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Config access test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run the complete migration process."""
    print("\n" + "="*60)
    print("SUPABASE CONFIG MIGRATION")
    print("="*60)
    print("\nThis script will:")
    print("1. Create the trading_config table in Supabase")
    print("2. Populate it with your current config")
    print("3. Verify everything is working")
    
    input("\nPress Enter to continue or Ctrl+C to cancel...")
    
    steps = [
        ("Database Migration", run_migration),
        ("Populate Config", populate_initial_config),
        ("Test Access", test_config_access),
    ]
    
    results = []
    for name, func in steps:
        result = func()
        results.append((name, result))
        if not result:
            print(f"\n⚠️  Stopping due to failure in: {name}")
            break
    
    # Summary
    print("\n" + "="*60)
    print("MIGRATION SUMMARY")
    print("="*60)
    
    all_passed = all(r[1] for r in results)
    
    for name, passed in results:
        status = "✅" if passed else "❌"
        print(f"{status} {name}")
    
    if all_passed:
        print("\n✅ MIGRATION COMPLETED SUCCESSFULLY!")
        print("\nYour configuration is now stored in Supabase.")
        print("The system will:")
        print("- Read from Supabase first (for Railway)")
        print("- Fall back to local file if needed")
        print("- Keep both in sync automatically")
        print("\nNext steps:")
        print("1. Test locally with: python scripts/test_supabase_config.py")
        print("2. Deploy to Railway")
        print("3. Verify Freqtrade service starts and reads config")
    else:
        print("\n❌ MIGRATION INCOMPLETE")
        print("Please fix the issues and run again.")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
