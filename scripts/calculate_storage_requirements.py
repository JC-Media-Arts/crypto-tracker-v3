#!/usr/bin/env python3
"""
Calculate storage requirements for historical crypto data in Supabase.
"""

import sys
import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.polygon_client import PolygonWebSocketClient


def calculate_storage():
    """Calculate storage requirements for different scenarios."""

    # Get the list of symbols we're tracking
    polygon_client = PolygonWebSocketClient()
    symbols = polygon_client._get_supported_symbols()
    num_symbols = len(symbols)

    print("=" * 80)
    print("CRYPTO DATA STORAGE REQUIREMENTS CALCULATOR")
    print("=" * 80)
    print(f"\nTracking {num_symbols} cryptocurrency symbols")
    print("-" * 80)

    # Data collection parameters
    # Polygon provides 1-minute bars for historical data
    minutes_per_hour = 60
    hours_per_day = 24
    days_per_year = 365

    # Calculate data points
    data_points_per_day = minutes_per_hour * hours_per_day  # 1,440
    data_points_per_year = data_points_per_day * days_per_year  # 525,600
    data_points_per_2_years = data_points_per_year * 2  # 1,051,200

    print("\n📊 DATA POINTS CALCULATION:")
    print(f"  • Minutes per day: {data_points_per_day:,}")
    print(f"  • Minutes per year: {data_points_per_year:,}")
    print(f"  • Minutes per 2 years: {data_points_per_2_years:,}")

    # PostgreSQL storage size for price_data table
    # Each row contains:
    # - symbol: VARCHAR(20) - ~10 bytes average
    # - timestamp: TIMESTAMPTZ - 8 bytes
    # - price: DECIMAL(20,8) - 9 bytes
    # - volume: DECIMAL(20,8) - 9 bytes (nullable, but usually present)
    # - PostgreSQL overhead: ~24 bytes per row (tuple header)

    bytes_per_row = 10 + 8 + 9 + 9 + 24  # 60 bytes

    # Add index overhead (approximately 20% of data size)
    index_overhead = 0.20

    print("\n💾 STORAGE PER ROW:")
    print(f"  • Data per row: {bytes_per_row} bytes")
    print(f"  • Index overhead: {int(index_overhead * 100)}%")
    print(f"  • Total per row: {int(bytes_per_row * (1 + index_overhead))} bytes")

    # Calculate total storage for different scenarios
    total_bytes_per_row = bytes_per_row * (1 + index_overhead)

    # For all symbols
    print("\n📈 STORAGE FOR ALL SYMBOLS:")
    print(f"\n  1 YEAR of data ({num_symbols} symbols):")
    total_rows_1y = num_symbols * data_points_per_year
    storage_1y_bytes = total_rows_1y * total_bytes_per_row
    storage_1y_gb = storage_1y_bytes / (1024**3)
    print(f"    • Total rows: {total_rows_1y:,}")
    print(f"    • Storage: {storage_1y_gb:.2f} GB")

    print(f"\n  2 YEARS of data ({num_symbols} symbols):")
    total_rows_2y = num_symbols * data_points_per_2_years
    storage_2y_bytes = total_rows_2y * total_bytes_per_row
    storage_2y_gb = storage_2y_bytes / (1024**3)
    print(f"    • Total rows: {total_rows_2y:,}")
    print(f"    • Storage: {storage_2y_gb:.2f} GB")

    # For top 10 symbols only
    top_10_symbols = 10
    print(f"\n📊 STORAGE FOR TOP 10 SYMBOLS ONLY:")
    print(f"\n  1 YEAR of data ({top_10_symbols} symbols):")
    total_rows_top10_1y = top_10_symbols * data_points_per_year
    storage_top10_1y_bytes = total_rows_top10_1y * total_bytes_per_row
    storage_top10_1y_gb = storage_top10_1y_bytes / (1024**3)
    print(f"    • Total rows: {total_rows_top10_1y:,}")
    print(f"    • Storage: {storage_top10_1y_gb:.2f} GB")

    print(f"\n  2 YEARS of data ({top_10_symbols} symbols):")
    total_rows_top10_2y = top_10_symbols * data_points_per_2_years
    storage_top10_2y_bytes = total_rows_top10_2y * total_bytes_per_row
    storage_top10_2y_gb = storage_top10_2y_bytes / (1024**3)
    print(f"    • Total rows: {total_rows_top10_2y:,}")
    print(f"    • Storage: {storage_top10_2y_gb:.2f} GB")

    # ML Features storage (calculated every 5 minutes)
    feature_interval_minutes = 5
    feature_points_per_day = data_points_per_day // feature_interval_minutes  # 288
    feature_points_per_year = feature_points_per_day * days_per_year  # 105,120

    # Each ML feature row is larger (29 technical indicators)
    # Approximately 300 bytes per row with all features
    ml_bytes_per_row = 300 * (1 + index_overhead)

    print("\n🤖 ML FEATURES STORAGE:")
    print(f"  • Feature calculations per day: {feature_points_per_day:,}")
    print(f"  • Feature calculations per year: {feature_points_per_year:,}")

    ml_storage_1y = (
        num_symbols * feature_points_per_year * ml_bytes_per_row / (1024**3)
    )
    ml_storage_2y = (
        num_symbols * feature_points_per_year * 2 * ml_bytes_per_row / (1024**3)
    )

    print(f"\n  1 YEAR of ML features ({num_symbols} symbols): {ml_storage_1y:.2f} GB")
    print(f"  2 YEARS of ML features ({num_symbols} symbols): {ml_storage_2y:.2f} GB")

    # Total storage summary
    print("\n" + "=" * 80)
    print("💰 TOTAL STORAGE SUMMARY:")
    print("=" * 80)

    total_1y = storage_1y_gb + ml_storage_1y
    total_2y = storage_2y_gb + ml_storage_2y

    print(f"\n  1 YEAR TOTAL (all {num_symbols} symbols):")
    print(f"    • Price data: {storage_1y_gb:.2f} GB")
    print(f"    • ML features: {ml_storage_1y:.2f} GB")
    print(f"    • TOTAL: {total_1y:.2f} GB")

    print(f"\n  2 YEARS TOTAL (all {num_symbols} symbols):")
    print(f"    • Price data: {storage_2y_gb:.2f} GB")
    print(f"    • ML features: {ml_storage_2y:.2f} GB")
    print(f"    • TOTAL: {total_2y:.2f} GB")

    print(f"\n  DIFFERENCE:")
    print(f"    • Additional storage for 2nd year: {total_2y - total_1y:.2f} GB")
    print(f"    • Percentage increase: {((total_2y - total_1y) / total_1y * 100):.1f}%")

    # Supabase pricing context
    print("\n" + "=" * 80)
    print("💵 SUPABASE PRICING CONTEXT:")
    print("=" * 80)
    print("\n  Free Tier: 500 MB")
    print("  Pro Tier: 8 GB included, then $0.125/GB/month")
    print("  Team Tier: 100 GB included, then $0.125/GB/month")

    if total_1y > 8:
        extra_1y = total_1y - 8
        cost_1y = extra_1y * 0.125
        print(f"\n  1 YEAR on Pro Tier:")
        print(f"    • Extra storage needed: {extra_1y:.2f} GB")
        print(f"    • Additional monthly cost: ${cost_1y:.2f}")
    else:
        print(f"\n  1 YEAR on Pro Tier: Fits within included 8 GB")

    if total_2y > 8:
        extra_2y = total_2y - 8
        cost_2y = extra_2y * 0.125
        print(f"\n  2 YEARS on Pro Tier:")
        print(f"    • Extra storage needed: {extra_2y:.2f} GB")
        print(f"    • Additional monthly cost: ${cost_2y:.2f}")
    else:
        print(f"\n  2 YEARS on Pro Tier: Fits within included 8 GB")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    calculate_storage()
