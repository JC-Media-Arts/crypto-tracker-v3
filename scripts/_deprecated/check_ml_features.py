#!/usr/bin/env python3
"""
Check ML features in the database
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from loguru import logger
from src.data.supabase_client import SupabaseClient
import pandas as pd


def main():
    """Check ML features status"""
    logger.info("Checking ML features in database")

    supabase = SupabaseClient()

    print("\n" + "=" * 60)
    print("ML FEATURES STATUS")
    print("=" * 60)

    # Get features from last 24 hours
    try:
        # Query the ml_features table
        response = (
            supabase.client.table("ml_features")
            .select(
                "symbol, timestamp, price_change_5m, price_change_1h, rsi_14, volume_ratio"
            )
            .order("timestamp", desc=True)
            .limit(50)
            .execute()
        )

        if response.data:
            features = pd.DataFrame(response.data)

            # Get unique symbols
            symbols = features["symbol"].unique()
            print(f"\nSymbols with features: {', '.join(symbols)}")
            print(f"Total feature records: {len(features)}")

            # Show latest features for each symbol
            print("\nLatest features by symbol:")
            print("-" * 60)

            for symbol in symbols[:5]:  # Show top 5 symbols
                symbol_features = features[features["symbol"] == symbol].iloc[0]
                print(f"\n{symbol}:")
                print(f"  Timestamp: {symbol_features['timestamp']}")
                print(f"  Price change 5m: {symbol_features['price_change_5m']:.4f}%")
                print(f"  Price change 1h: {symbol_features['price_change_1h']:.4f}%")
                print(f"  RSI 14: {symbol_features['rsi_14']:.2f}")
                print(f"  Volume ratio: {symbol_features['volume_ratio']:.4f}")

        else:
            print("\nNo ML features found in database yet.")
            print("Make sure the feature calculator is running.")

    except Exception as e:
        logger.error(f"Error querying features: {e}")
        print(f"\nError: {e}")


if __name__ == "__main__":
    main()
