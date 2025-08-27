#!/usr/bin/env python3
"""
Test script to verify the system heartbeat functionality
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
import time

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from loguru import logger

def test_heartbeat_table():
    """Test that we can write to and read from the heartbeat table"""
    db = SupabaseClient()

    print("\n🔍 Testing System Heartbeat Functionality\n")
    print("=" * 50)

    # 1. Test writing a heartbeat
    print("\n1. Testing heartbeat write...")
    try:
        test_heartbeat = {
            "service_name": "test_service",
            "last_heartbeat": datetime.now(timezone.utc).isoformat(),
            "status": "running",
            "metadata": {
                "test": True,
                "timestamp": datetime.now().isoformat()
            }
        }

        result = db.client.table("system_heartbeat").upsert(
            test_heartbeat,
            on_conflict="service_name"
        ).execute()

        if result.data:
            print("   ✅ Successfully wrote heartbeat to database")
        else:
            print("   ❌ Failed to write heartbeat")

    except Exception as e:
        print(f"   ❌ Error writing heartbeat: {e}")
        return False

    # 2. Test reading heartbeat
    print("\n2. Testing heartbeat read...")
    try:
        result = db.client.table("system_heartbeat").select("*").eq(
            "service_name", "test_service"
        ).single().execute()

        if result.data:
            print(f"   ✅ Successfully read heartbeat:")
            print(f"      Service: {result.data.get('service_name')}")
            print(f"      Status: {result.data.get('status')}")
            print(f"      Last heartbeat: {result.data.get('last_heartbeat')}")
            print(f"      Metadata: {result.data.get('metadata')}")
        else:
            print("   ❌ No heartbeat found")

    except Exception as e:
        print(f"   ❌ Error reading heartbeat: {e}")
        return False

    # 3. Test checking for paper trading engine
    print("\n3. Checking for paper_trading_engine heartbeat...")
    try:
        five_minutes_ago = (
            datetime.now(timezone.utc) - timedelta(minutes=5)
        ).isoformat()

        result = db.client.table("system_heartbeat").select("*").eq(
            "service_name", "paper_trading_engine"
        ).gte("last_heartbeat", five_minutes_ago).single().execute()

        if result.data:
            print(f"   ✅ Paper trading engine is RUNNING")
            metadata = result.data.get("metadata", {})
            print(f"      Last heartbeat: {result.data.get('last_heartbeat')}")
            print(f"      Positions open: {metadata.get('positions_open', 0)}")
            print(f"      Balance: ${metadata.get('balance', 0):.2f}")
            print(f"      Market regime: {metadata.get('market_regime', 'UNKNOWN')}")
            print(f"      Symbols monitored: {metadata.get('symbols_monitored', 0)}")
        else:
            print("   ⚠️  No recent heartbeat from paper trading engine")
            print("      (This is normal if paper trading is not currently running)")

    except Exception as e:
        if "multiple" not in str(e).lower():
            print(f"   ⚠️  Paper trading engine heartbeat not found (not running)")
        else:
            print(f"   ❌ Error checking paper trading: {e}")

    # 4. Clean up test data
    print("\n4. Cleaning up test data...")
    try:
        db.client.table("system_heartbeat").delete().eq(
            "service_name", "test_service"
        ).execute()
        print("   ✅ Test data cleaned up")
    except Exception as e:
        print(f"   ⚠️  Could not clean up test data: {e}")

    print("\n" + "=" * 50)
    print("\n✅ Heartbeat system test complete!")
    print("\nNext steps:")
    print("1. Run the migration to create the table if not exists:")
    print("   psql $DATABASE_URL < migrations/029_create_system_heartbeat.sql")
    print("\n2. Start paper trading to see live heartbeats:")
    print("   python scripts/run_paper_trading_simple.py")
    print("\n3. Check the dashboard to verify status shows correctly:")
    print("   python live_dashboard_v2.py")


if __name__ == "__main__":
    test_heartbeat_table()
