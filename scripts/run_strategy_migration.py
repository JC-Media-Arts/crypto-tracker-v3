#!/usr/bin/env python3
"""
Run the strategy tables migration.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()

def run_migration():
    """Run the strategy tables migration."""
    
    # Initialize Supabase client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        print("❌ Error: SUPABASE_URL and SUPABASE_KEY must be set in .env file")
        return False
    
    supabase: Client = create_client(url, key)
    
    # Read migration file
    migration_file = Path(__file__).parent.parent / "migrations" / "002_strategy_tables.sql"
    
    if not migration_file.exists():
        print(f"❌ Error: Migration file not found: {migration_file}")
        return False
    
    with open(migration_file, 'r') as f:
        migration_sql = f.read()
    
    try:
        # Execute migration
        print("🚀 Running strategy tables migration...")
        
        # Split by semicolons and execute each statement
        statements = [s.strip() for s in migration_sql.split(';') if s.strip()]
        
        for i, statement in enumerate(statements, 1):
            if statement:
                print(f"  Executing statement {i}/{len(statements)}...")
                # Using RPC call for raw SQL execution
                result = supabase.rpc('exec_sql', {'query': statement + ';'}).execute()
        
        print("✅ Migration completed successfully!")
        
        # Verify tables were created
        print("\n📊 Verifying new tables...")
        
        tables_to_check = [
            'strategy_configs',
            'strategy_setups', 
            'dca_grids',
            'market_regimes'
        ]
        
        for table in tables_to_check:
            try:
                # Try to query each table
                result = supabase.table(table).select("*").limit(1).execute()
                print(f"  ✅ Table '{table}' exists")
            except Exception as e:
                print(f"  ❌ Table '{table}' not found or error: {e}")
        
        # Check if default strategies were inserted
        try:
            strategies = supabase.table('strategy_configs').select("*").execute()
            if strategies.data:
                print(f"\n📋 Found {len(strategies.data)} strategy configurations:")
                for strategy in strategies.data:
                    print(f"  - {strategy['strategy_name']}: {'Active' if strategy['is_active'] else 'Inactive'}")
            else:
                print("\n⚠️  No strategy configurations found")
        except Exception as e:
            print(f"\n❌ Error checking strategy configs: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error running migration: {e}")
        print("\n💡 Note: If you see 'function supabase.exec_sql does not exist', you may need to:")
        print("   1. Run the migration directly in Supabase SQL editor")
        print("   2. Or use the Supabase migrations feature")
        print(f"\n📄 Migration file location: {migration_file}")
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
