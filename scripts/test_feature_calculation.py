#!/usr/bin/env python3
"""
Test ML Feature Calculation with reduced data requirements
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta

from loguru import logger
from src.data.supabase_client import SupabaseClient
from src.ml.feature_calculator import FeatureCalculator


def main():
    """Test feature calculation with available data"""
    logger.info("Testing ML feature calculation")

    supabase = SupabaseClient()
    calculator = FeatureCalculator()

    # Temporarily reduce minimum periods for testing
    calculator.min_periods = 20

    # Test with BTC which has the most data
    symbol = "BTC"

    print("\n" + "=" * 60)
    print("ML FEATURE CALCULATION TEST")
    print("=" * 60)

    # Get all available data
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=7)  # Look back 7 days

    price_data = supabase.get_price_data(symbol, start_time, end_time)
    data_count = len(price_data) if price_data else 0

    print(f"\nSymbol: {symbol}")
    print(f"Data points available: {data_count}")
    print(f"Minimum required (reduced for testing): {calculator.min_periods}")

    if data_count >= calculator.min_periods:
        try:
            # Calculate features
            features_df = calculator.calculate_features_for_symbol(
                symbol, lookback_hours=168
            )  # 7 days

            if features_df is not None and not features_df.empty:
                print("\n✅ Feature calculation successful!")
                print(f"Number of feature records: {len(features_df)}")
                print("\nFeatures calculated:")
                for col in features_df.columns:
                    if col != "symbol":
                        print(f"  - {col}")

                # Show sample of recent features
                print("\nSample of most recent features:")
                recent = features_df.tail(1).iloc[0]
                for col in [
                    "price_change_5m",
                    "price_change_1h",
                    "rsi_14",
                    "volume_ratio",
                ]:
                    if col in recent:
                        print(f"  - {col}: {recent[col]:.4f}")

                # Test saving features
                print("\nTesting save to database...")
                recent_features = features_df.tail(5)
                success = calculator.save_features(recent_features)
                if success:
                    print("✅ Features saved successfully!")
                else:
                    print("❌ Failed to save features")

            else:
                print("❌ Feature calculation returned no data")

        except Exception as e:
            print(f"❌ Error during feature calculation: {e}")
            import traceback

            traceback.print_exc()
    else:
        print(
            f"\n❌ Not enough data. Need at least {calculator.min_periods - data_count} more data points"
        )
        print("Keep the data collector running and try again later.")


if __name__ == "__main__":
    main()
