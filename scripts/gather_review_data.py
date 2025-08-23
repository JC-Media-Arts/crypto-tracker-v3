#!/usr/bin/env python3
"""
Script to gather comprehensive data for code review
"""
import os
import sys
from datetime import datetime
import json
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from supabase import create_client, Client


def main():
    # Get settings
    settings = get_settings()

    # Create Supabase client
    supabase: Client = create_client(settings.supabase_url, settings.supabase_key)

    print("=" * 80)
    print("DATABASE REVIEW DATA")
    print("=" * 80)
    print()

    # 1. Schema Information
    print("=== 1. DATABASE SCHEMA ===")
    try:
        schema_result = supabase.table("ohlc_data").select("*").limit(1).execute()
        print("\nOHLC_DATA table columns detected from sample:")
        if schema_result.data:
            for key in schema_result.data[0].keys():
                print(f"  - {key}")
    except Exception as e:
        print(f"Error getting schema: {e}")

    # 2. Row counts
    print("\n=== 2. ROW COUNTS ===")
    tables = [
        "ohlc_data",
        "ml_features",
        "strategy_dca_labels",
        "strategy_swing_labels",
        "strategy_channel_labels",
        "scan_history",
        "shadow_testing_scans",
        "shadow_testing_trades",
        "trade_logs",
    ]

    for table in tables:
        try:
            count_result = supabase.table(table).select("*", count="exact").execute()
            print(
                f"{table}: {count_result.count if hasattr(count_result, 'count') else 'Unknown'} rows"
            )
        except Exception as e:
            print(f"{table}: Error - {e}")

    # 3. Data gaps in OHLC
    print("\n=== 3. OHLC DATA COVERAGE ===")
    try:
        # Get unique symbols
        symbols_result = supabase.table("ohlc_data").select("symbol").execute()
        unique_symbols = set(row["symbol"] for row in symbols_result.data)
        print(f"Total unique symbols: {len(unique_symbols)}")

        # Check coverage for each timeframe
        for timeframe in ["1m", "15m", "1h", "4h", "1d"]:
            tf_result = (
                supabase.table("ohlc_data")
                .select("symbol, timestamp")
                .eq("timeframe", timeframe)
                .execute()
            )
            tf_symbols = set(row["symbol"] for row in tf_result.data)
            print(f"\n{timeframe} timeframe:")
            print(f"  Symbols with data: {len(tf_symbols)}")
            if tf_result.data:
                timestamps = [row["timestamp"] for row in tf_result.data]
                print(f"  Earliest: {min(timestamps) if timestamps else 'N/A'}")
                print(f"  Latest: {max(timestamps) if timestamps else 'N/A'}")
                print(f"  Total records: {len(tf_result.data)}")
    except Exception as e:
        print(f"Error checking OHLC coverage: {e}")

    # 4. Recent data freshness
    print("\n=== 4. DATA FRESHNESS (Last 24h) ===")
    try:
        from datetime import datetime, timedelta

        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()

        for timeframe in ["1m", "15m", "1h"]:
            fresh_result = (
                supabase.table("ohlc_data")
                .select("symbol, timestamp")
                .eq("timeframe", timeframe)
                .gte("timestamp", cutoff)
                .execute()
            )

            if fresh_result.data:
                symbols_fresh = set(row["symbol"] for row in fresh_result.data)
                latest = max(row["timestamp"] for row in fresh_result.data)
                print(f"\n{timeframe}: {len(symbols_fresh)} symbols updated")
                print(f"  Latest update: {latest}")
    except Exception as e:
        print(f"Error checking data freshness: {e}")

    # 5. ML Features status
    print("\n=== 5. ML FEATURES STATUS ===")
    try:
        features_result = (
            supabase.table("ml_features").select("symbol, timestamp").execute()
        )
        if features_result.data:
            feature_symbols = set(row["symbol"] for row in features_result.data)
            print(f"Symbols with features: {len(feature_symbols)}")
            timestamps = [row["timestamp"] for row in features_result.data]
            print(f"Latest features: {max(timestamps) if timestamps else 'N/A'}")
            print(f"Total feature records: {len(features_result.data)}")
    except Exception as e:
        print(f"Error checking ML features: {e}")

    # 6. Strategy Labels
    print("\n=== 6. STRATEGY LABELS ===")
    for strategy in ["dca", "swing", "channel"]:
        try:
            table_name = f"strategy_{strategy}_labels"
            labels_result = supabase.table(table_name).select("symbol").execute()
            if labels_result.data:
                label_symbols = set(row["symbol"] for row in labels_result.data)
                print(
                    f"{strategy.upper()}: {len(label_symbols)} symbols, {len(labels_result.data)} total labels"
                )
        except Exception as e:
            print(f"{strategy.upper()}: Error - {e}")

    # 7. Recent Trading Activity
    print("\n=== 7. RECENT TRADING ACTIVITY ===")
    try:
        # Check scan history
        scan_cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        scans_result = (
            supabase.table("scan_history")
            .select("*")
            .gte("timestamp", scan_cutoff)
            .execute()
        )

        if scans_result.data:
            print(f"Scans in last 24h: {len(scans_result.data)}")
            strategies = set(
                row.get("strategy") for row in scans_result.data if row.get("strategy")
            )
            print(f"Active strategies: {', '.join(strategies)}")

            # Count signals
            with_signals = [
                s for s in scans_result.data if s.get("signal_strength", 0) > 0
            ]
            print(f"Scans with signals: {len(with_signals)}")
    except Exception as e:
        print(f"Error checking trading activity: {e}")

    # 8. Shadow Testing Status
    print("\n=== 8. SHADOW TESTING STATUS ===")
    try:
        shadow_scans = supabase.table("shadow_testing_scans").select("*").execute()
        shadow_trades = supabase.table("shadow_testing_trades").select("*").execute()

        print(
            f"Shadow scans recorded: {len(shadow_scans.data) if shadow_scans.data else 0}"
        )
        print(
            f"Shadow trades recorded: {len(shadow_trades.data) if shadow_trades.data else 0}"
        )

        if shadow_trades.data:
            # Get recent trades
            recent_trades = sorted(
                shadow_trades.data, key=lambda x: x.get("entry_time", ""), reverse=True
            )[:5]
            print("\nLast 5 shadow trades:")
            for trade in recent_trades:
                print(
                    f"  {trade.get('symbol')}: {trade.get('strategy')} - Status: {trade.get('status')}"
                )
    except Exception as e:
        print(f"Error checking shadow testing: {e}")

    print("\n" + "=" * 80)
    print("DATABASE REVIEW COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
