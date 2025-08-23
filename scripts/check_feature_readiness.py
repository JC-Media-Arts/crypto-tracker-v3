#!/usr/bin/env python3
"""
Check if we have enough data to calculate ML features
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta  # noqa: E402
from loguru import logger  # noqa: E402
from src.data.supabase_client import SupabaseClient  # noqa: E402
from src.ml.feature_calculator import FeatureCalculator  # noqa: E402


def main():
    """Check feature calculation readiness"""
    logger.info("Checking ML feature calculation readiness")

    supabase = SupabaseClient()
    calculator = FeatureCalculator()

    # Check data availability for top symbols
    symbols = ["BTC", "ETH", "SOL", "BNB", "XRP"]

    print("\n" + "=" * 60)
    print("ML FEATURE CALCULATION READINESS CHECK")
    print("=" * 60)

    ready_symbols = []

    for symbol in symbols:
        # Get recent data count
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=48)

        price_data = supabase.get_price_data(symbol, start_time, end_time)
        data_count = len(price_data) if price_data else 0

        print(f"\n{symbol}:")
        print(f"  - Data points (last 48h): {data_count}")
        print(f"  - Minimum required: {calculator.min_periods}")

        if data_count >= calculator.min_periods:
            print("  - Status: ✅ READY for feature calculation")
            ready_symbols.append(symbol)

            # Try calculating features for this symbol
            try:
                features_df = calculator.calculate_features_for_symbol(
                    symbol, lookback_hours=24
                )
                if features_df is not None and not features_df.empty:
                    print(
                        f"  - Test calculation: ✅ Success ({len(features_df)} features)"
                    )
                    print(f"  - Latest features: {features_df.columns.tolist()[:5]}...")
                else:
                    print("  - Test calculation: ❌ Failed")
            except Exception as e:
                print(f"  - Test calculation: ❌ Error: {e}")
        else:
            print(
                f"  - Status: ❌ Need {calculator.min_periods - data_count} more data points"
            )

    print("\n" + "=" * 60)
    print(f"SUMMARY: {len(ready_symbols)}/{len(symbols)} symbols ready for ML features")
    print("=" * 60)

    if ready_symbols:
        print(f"\nReady symbols: {', '.join(ready_symbols)}")
        print("\nYou can now run: python scripts/run_feature_calculator.py")
    else:
        print("\nNo symbols have enough data yet. Keep the data collector running!")


if __name__ == "__main__":
    main()
