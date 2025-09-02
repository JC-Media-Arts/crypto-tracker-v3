#!/usr/bin/env python3
"""
Run migration 048 to rename Freqtrade's trades table to paper_trades
"""

import os
import sys
from pathlib import Path
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def run_migration():
    """Run the migration to rename trades table to paper_trades"""
    
    # Initialize Supabase client
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Error: SUPABASE_URL and SUPABASE_KEY must be set")
        sys.exit(1)
    
    supabase = create_client(supabase_url, supabase_key)
    
    # Read the migration file
    migration_file = Path(__file__).parent.parent / "migrations" / "048_rename_trades_to_paper_trades.sql"
    
    if not migration_file.exists():
        print(f"❌ Error: Migration file not found: {migration_file}")
        sys.exit(1)
    
    with open(migration_file, 'r') as f:
        migration_sql = f.read()
    
    print("🚀 Running migration 048: Rename trades table to paper_trades")
    print("=" * 60)
    
    try:
        # Execute the migration
        # Note: Supabase doesn't support running raw SQL through the Python client
        # You'll need to run this in the Supabase SQL editor
        print("⚠️  IMPORTANT: This migration needs to be run in the Supabase SQL editor")
        print("📋 Copy the following SQL and run it in your Supabase dashboard:\n")
        print(migration_sql)
        print("\n" + "=" * 60)
        print("📌 Steps to run:")
        print("1. Go to your Supabase dashboard")
        print("2. Navigate to the SQL editor")
        print("3. Paste the SQL above")
        print("4. Click 'Run'")
        print("5. Check for any errors in the output")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_migration()
