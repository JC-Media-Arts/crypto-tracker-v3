#!/usr/bin/env python3
"""
Monitor progress of all OHLC data fetching
"""

import os
import sys
from datetime import datetime
from loguru import logger
from collections import defaultdict

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.supabase_client import SupabaseClient


def main():
    s = SupabaseClient()

    print("=" * 80)
    print("OHLC DATA FETCHING PROGRESS MONITOR")
    print("=" * 80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Target symbols
    priority_symbols = [
        "BTC",
        "ETH",
        "SOL",
        "XRP",
        "ADA",
        "AVAX",
        "DOGE",
        "MATIC",
        "LINK",
        "UNI",
    ]

    # Check each timeframe
    timeframes = ["1d", "1h", "15m", "1m"]
    timeframe_stats = {}

    for tf in timeframes:
        # Get symbols with data for this timeframe
        result = (
            s.client.table("ohlc_data")
            .select("symbol")
            .eq("timeframe", tf)
            .limit(50000)
            .execute()
        )

        if result.data:
            symbols = set(r["symbol"] for r in result.data)
            timeframe_stats[tf] = symbols
        else:
            timeframe_stats[tf] = set()

    # Print summary
    print("📊 OVERALL PROGRESS:")
    print("-" * 40)
    for tf in timeframes:
        symbols = timeframe_stats[tf]
        print(f"{tf:4s}: {len(symbols):3d} symbols with data")

    # Check priority symbols
    print("\n🎯 PRIORITY SYMBOLS STATUS:")
    print("-" * 40)
    print("Symbol  | 1d  | 1h  | 15m | 1m |")
    print("--------|-----|-----|-----|-----|")

    for symbol in priority_symbols:
        status = []
        for tf in timeframes:
            if symbol in timeframe_stats[tf]:
                # Get count for this symbol/timeframe
                result = (
                    s.client.table("ohlc_data")
                    .select("timestamp", count="exact")
                    .eq("symbol", symbol)
                    .eq("timeframe", tf)
                    .execute()
                )

                count = result.count if hasattr(result, "count") else 0
                if count > 1000:
                    status.append(" ✓  ")
                elif count > 0:
                    status.append(f"{count:4d}")
                else:
                    status.append(" -  ")
            else:
                status.append(" -  ")

        print(f"{symbol:7s} | {'|'.join(status)}|")

    # Total records
    result = s.client.table("ohlc_data").select("*", count="exact", head=True).execute()
    total = result.count if hasattr(result, "count") else 0

    print("\n📈 DATABASE STATISTICS:")
    print("-" * 40)
    print(f"Total OHLC records: {total:,}")

    # Estimate storage
    bytes_per_record = 100  # Approximate
    gb = (total * bytes_per_record) / (1024**3)
    print(f"Estimated storage: {gb:.2f} GB")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
