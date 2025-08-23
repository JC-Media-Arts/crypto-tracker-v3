#!/usr/bin/env python3
"""
Quick check of scan history data
"""

import sys

sys.path.append(".")

from src.data.supabase_client import SupabaseClient
from datetime import datetime, timedelta


def check_scan_history():
    client = SupabaseClient()

    # Check if scan_history table has any data
    try:
        # Get count of records
        result = (
            client.client.table("scan_history")
            .select("*", count="exact")
            .limit(10)
            .execute()
        )

        count = result.count if hasattr(result, "count") else len(result.data)

        print(f"\n📊 Scan History Status:")
        print(f"Total records in scan_history table: {count}")

        if result.data:
            print(f"\nLatest records:")
            for record in result.data[:5]:
                print(
                    f"  - {record.get('timestamp', 'N/A')}: {record.get('symbol')} / {record.get('strategy_name')} / {record.get('decision')}"
                )
        else:
            print("\n❌ No scan history data found!")
            print("\nPossible issues:")
            print("1. Paper trading system not running with updated code")
            print("2. Scan logger not initialized properly")
            print("3. Database connection issues")

    except Exception as e:
        print(f"\n❌ Error checking scan history: {e}")
        print("\nThe table might not exist or there's a connection issue")


if __name__ == "__main__":
    check_scan_history()
