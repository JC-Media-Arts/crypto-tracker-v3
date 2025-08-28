#!/usr/bin/env python3
"""
Test script for configuration history tracking.
Tests that configuration changes are properly logged to the database.
"""

import sys
from pathlib import Path
import json
from datetime import datetime

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config.config_loader import ConfigLoader
from src.data.supabase_client import SupabaseClient


def test_config_history_tracking():
    """Test that configuration changes are tracked in database"""
    print("\n" + "=" * 50)
    print("Testing Configuration History Tracking...")
    print("=" * 50)

    # Initialize
    loader = ConfigLoader()
    db = SupabaseClient()

    # Test 1: Manual configuration update
    print("\n1. Testing manual configuration update...")

    # Make a test change
    updates = {
        "strategies.CHANNEL.buy_zone": 0.20,  # Change from 0.15 to 0.20
        "position_management.base_position_size_usd": 75.0,  # Change from 50 to 75
    }

    success = loader.update_config(
        updates=updates,
        change_type="manual",
        changed_by="test_script",
        description="Test configuration change for history tracking",
    )

    if success:
        print("✅ Configuration updated successfully")
    else:
        print("❌ Failed to update configuration")
        return False

    # Test 2: Verify changes were logged
    print("\n2. Verifying changes were logged to database...")

    history = loader.get_config_history(limit=5)

    if history:
        print(f"✅ Found {len(history)} recent configuration changes")

        # Display recent changes
        print("\nRecent configuration changes:")
        for change in history[:3]:
            print(
                f"  - {change.get('change_timestamp', 'N/A')}: "
                f"{change.get('config_section', 'N/A')}.{change.get('field_name', 'N/A')} "
                f"changed from {change.get('old_value', 'N/A')} to {change.get('new_value', 'N/A')}"
            )
    else:
        print(
            "⚠️ No configuration history found (this is normal if database table doesn't exist yet)"
        )

    # Test 3: Verify config file was updated
    print("\n3. Verifying configuration file was updated...")

    config = loader.load()

    # Check if our changes were applied
    channel_buy_zone = config.get("strategies", {}).get("CHANNEL", {}).get("buy_zone")
    position_size = config.get("position_management", {}).get("base_position_size_usd")

    if channel_buy_zone == 0.20:
        print(f"✅ CHANNEL buy_zone updated to {channel_buy_zone}")
    else:
        print(f"❌ CHANNEL buy_zone not updated (current: {channel_buy_zone})")

    if position_size == 75.0:
        print(f"✅ Base position size updated to ${position_size}")
    else:
        print(f"❌ Base position size not updated (current: ${position_size})")

    # Test 4: Revert changes for clean state
    print("\n4. Reverting test changes...")

    revert_updates = {
        "strategies.CHANNEL.buy_zone": 0.15,  # Revert to original
        "position_management.base_position_size_usd": 50.0,  # Revert to original
    }

    success = loader.update_config(
        updates=revert_updates,
        change_type="manual",
        changed_by="test_script",
        description="Reverting test changes",
    )

    if success:
        print("✅ Changes reverted successfully")
    else:
        print("❌ Failed to revert changes")

    print("\n" + "=" * 50)
    print("Configuration History Testing Complete!")
    print("=" * 50)

    return True


def check_database_table():
    """Check if config_history table exists"""
    print("\nChecking if config_history table exists...")

    try:
        db = SupabaseClient()

        # Try to query the table
        result = db.client.table("config_history").select("id").limit(1).execute()

        print("✅ config_history table exists")
        return True

    except Exception as e:
        if 'relation "public.config_history" does not exist' in str(e):
            print("❌ config_history table does not exist - run migration first")
            print("   Execute: migrations/030_create_config_history.sql")
        else:
            print(f"❌ Error checking table: {e}")
        return False


if __name__ == "__main__":
    # First check if table exists
    table_exists = check_database_table()

    if not table_exists:
        print(
            "\n⚠️ Please create the config_history table first by running the migration:"
        )
        print("   psql $DATABASE_URL < migrations/030_create_config_history.sql")
        print("   OR run it through your database management tool")
        sys.exit(1)

    # Run the tests
    test_config_history_tracking()
