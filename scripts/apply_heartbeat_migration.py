#!/usr/bin/env python3
"""
Apply the system_heartbeat table migration
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient  # noqa: E402


def apply_migration():
    """Apply the system_heartbeat table migration"""

    # Read the migration file
    migration_path = (
        Path(__file__).parent.parent / "migrations" / "029_create_system_heartbeat.sql"
    )

    if not migration_path.exists():
        print(f"❌ Migration file not found: {migration_path}")
        return False

    with open(migration_path, "r") as f:
        _ = f.read()  # Migration SQL content (for reference)

    print("📋 Applying migration: 029_create_system_heartbeat.sql")
    print("=" * 50)

    # Connect to database
    db = SupabaseClient()

    try:
        # Note: Supabase Python client doesn't support raw SQL execution directly
        # You'll need to run this via Supabase SQL Editor or psql
        print("\n⚠️  The Supabase Python client doesn't support raw SQL execution.")
        print("\nPlease run the migration using one of these methods:\n")

        print("Option 1: Supabase Dashboard")
        print("  1. Go to your Supabase project dashboard")
        print("  2. Navigate to SQL Editor")
        print("  3. Copy and paste the migration SQL")
        print("  4. Click 'Run'\n")

        print("Option 2: Command line (if you have DATABASE_URL)")
        print(f"  psql $DATABASE_URL < {migration_path}\n")

        print("Option 3: Using Supabase CLI")
        print("  supabase db push\n")

        print("The migration SQL has been saved to:")
        print(f"  {migration_path}")

        # Test if table already exists
        print("\n🔍 Checking if table already exists...")
        try:
            db.client.table("system_heartbeat").select("*").limit(1).execute()
            print("✅ Table 'system_heartbeat' already exists!")
            return True
        except Exception as e:
            if "relation" in str(e).lower() and "does not exist" in str(e).lower():
                print(
                    "❌ Table 'system_heartbeat' does not exist yet - migration needed"
                )
            else:
                print(f"⚠️  Could not determine table status: {e}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    apply_migration()
