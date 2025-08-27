#!/usr/bin/env python3
"""
Backfill Features for Existing Scan History
Adds missing feature data to historical trades for complete ML training dataset
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from loguru import logger
import pandas as pd

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient  # noqa: E402
from src.data.hybrid_fetcher import HybridDataFetcher  # noqa: E402
from src.strategies.regime_detector import RegimeDetector  # noqa: E402


class FeatureBackfiller:
    """Backfills missing features for historical scan_history entries."""

    def __init__(self):
        self.db = SupabaseClient()
        self.data_fetcher = HybridDataFetcher()
        self.regime_detector = RegimeDetector()
        logger.add(
            "logs/feature_backfill.log",
            rotation="50 MB",
            retention="7 days",
            level="DEBUG",
        )

    def _calculate_features(self, symbol: str, market_data: List) -> Dict:
        """Calculate features from OHLC data (matching run_paper_trading_simple.py)."""
        if not market_data or len(market_data) < 20:
            return {
                "price_drop": 0,
                "rsi": 50,
                "volume_ratio": 1,
                "distance_from_support": 0,
                "btc_correlation": 0,
                "market_regime": 1,
            }

        try:
            # Convert to DataFrame for easier calculation
            df = pd.DataFrame(market_data)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp")

            # Current price
            current_price = float(df.iloc[-1]["close"])

            # Price drop percentage (from recent high)
            high_24h = df["high"].max()
            price_drop = ((high_24h - current_price) / high_24h) * 100 if high_24h > 0 else 0

            # RSI calculation
            rsi = self._calculate_rsi(df["close"].values)

            # Volume ratio (current vs average)
            avg_volume = df["volume"].mean()
            current_volume = float(df.iloc[-1]["volume"])
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

            # Distance from support (simplified - use recent low)
            support = df["low"].min()
            distance_from_support = ((current_price - support) / support) * 100 if support > 0 else 0

            # Market regime (would need actual BTC data for correlation)
            market_regime = 1  # Default to NORMAL

            return {
                "price_drop": round(price_drop, 2),
                "rsi": round(rsi, 2),
                "volume_ratio": round(volume_ratio, 2),
                "distance_from_support": round(distance_from_support, 2),
                "btc_correlation": 0,  # Would need BTC data
                "market_regime": market_regime,
            }

        except Exception as e:
            logger.error(f"Error calculating features for {symbol}: {e}")
            return {
                "price_drop": 0,
                "rsi": 50,
                "volume_ratio": 1,
                "distance_from_support": 0,
                "btc_correlation": 0,
                "market_regime": 1,
            }

    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI from price series."""
        if len(prices) < period + 1:
            return 50.0

        deltas = [prices[i + 1] - prices[i] for i in range(len(prices) - 1)]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    async def find_scans_without_features(self) -> List[Dict]:
        """Find scan_history entries that lack feature data."""
        try:
            # Query scans where features is null or empty
            result = (
                self.db.client.table("scan_history")
                .select("*")
                .or_("features.is.null,features.eq.{}")
                .order("timestamp", desc=True)
                .limit(1000)
                .execute()
            )

            if result.data:
                logger.info(f"Found {len(result.data)} scans without features")
                return result.data
            else:
                logger.info("No scans found without features")
                return []

        except Exception as e:
            logger.error(f"Error finding scans without features: {e}")
            return []

    async def backfill_features_for_scan(self, scan: Dict) -> bool:
        """Backfill features for a single scan entry."""
        try:
            symbol = scan["symbol"]
            timestamp = datetime.fromisoformat(scan["timestamp"].replace("+00:00", "+00:00"))

            # Get market data around the time of the scan
            end_time = timestamp
            start_time = timestamp - timedelta(hours=24)

            # Fetch OHLC data
            market_data = await self.data_fetcher.fetch_ohlc_range(
                symbol, start_time, end_time, interval="15min"
            )

            if not market_data:
                logger.warning(f"No market data found for {symbol} at {timestamp}")
                return False

            # Calculate features
            features = self._calculate_features(symbol, market_data)

            # Update the scan entry with features
            update_result = (
                self.db.client.table("scan_history")
                .update({"features": features})
                .eq("scan_id", scan["scan_id"])
                .execute()
            )

            if update_result.data:
                logger.debug(f"Updated features for {symbol} scan at {timestamp}")
                return True
            else:
                logger.error(f"Failed to update scan {scan['scan_id']}")
                return False

        except Exception as e:
            logger.error(f"Error backfilling features for scan {scan.get('scan_id')}: {e}")
            return False

    async def backfill_all_missing_features(self, batch_size: int = 10):
        """Backfill features for all scans that lack them."""
        logger.info("Starting feature backfill process...")

        # Find scans without features
        scans = await self.find_scans_without_features()

        if not scans:
            logger.info("No scans need feature backfill")
            return

        # Process in batches
        total = len(scans)
        successful = 0
        failed = 0

        for i in range(0, total, batch_size):
            batch = scans[i : i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} ({i+1}-{min(i+batch_size, total)} of {total})")

            # Process batch concurrently
            tasks = [self.backfill_features_for_scan(scan) for scan in batch]
            results = await asyncio.gather(*tasks)

            # Count results
            batch_success = sum(1 for r in results if r)
            batch_failed = len(results) - batch_success
            successful += batch_success
            failed += batch_failed

            logger.info(
                f"Batch complete: {batch_success} successful, {batch_failed} failed"
            )

            # Rate limiting
            await asyncio.sleep(2)

        # Final report
        logger.info(
            f"Backfill complete: {successful} successful, {failed} failed out of {total} total"
        )

    async def verify_feature_completeness(self):
        """Verify how many scans have complete feature data."""
        try:
            # Count total scans
            total_result = (
                self.db.client.table("scan_history").select("scan_id", count="exact").execute()
            )
            total_count = total_result.count if total_result else 0

            # Count scans with features
            with_features_result = (
                self.db.client.table("scan_history")
                .select("scan_id", count="exact")
                .not_.is_("features", "null")
                .not_.eq("features", {})
                .execute()
            )
            with_features = with_features_result.count if with_features_result else 0

            # Count by strategy
            strategies = ["DCA", "SWING", "CHANNEL"]
            strategy_counts = {}

            for strategy in strategies:
                result = (
                    self.db.client.table("scan_history")
                    .select("scan_id", count="exact")
                    .eq("strategy_name", strategy)
                    .not_.is_("features", "null")
                    .execute()
                )
                strategy_counts[strategy] = result.count if result else 0

            # Report
            logger.info("=" * 50)
            logger.info("FEATURE COMPLETENESS REPORT")
            logger.info("=" * 50)
            logger.info(f"Total scans: {total_count:,}")
            logger.info(f"With features: {with_features:,} ({(with_features/total_count*100):.1f}%)")
            logger.info(f"Missing features: {total_count - with_features:,}")
            logger.info("")
            logger.info("By Strategy (with features):")
            for strategy, count in strategy_counts.items():
                logger.info(f"  {strategy}: {count:,}")
            logger.info("=" * 50)

            return {
                "total": total_count,
                "with_features": with_features,
                "missing_features": total_count - with_features,
                "by_strategy": strategy_counts,
            }

        except Exception as e:
            logger.error(f"Error verifying feature completeness: {e}")
            return None


async def main():
    """Main entry point."""
    backfiller = FeatureBackfiller()

    # First check current status
    logger.info("Checking current feature completeness...")
    initial_status = await backfiller.verify_feature_completeness()

    if initial_status and initial_status["missing_features"] > 0:
        # Perform backfill
        logger.info(f"\nStarting backfill for {initial_status['missing_features']} scans...")
        await backfiller.backfill_all_missing_features()

        # Verify results
        logger.info("\nVerifying final status...")
        final_status = await backfiller.verify_feature_completeness()

        if final_status:
            improved = initial_status["missing_features"] - final_status["missing_features"]
            logger.info(f"\n✅ Backfilled {improved} scans with features")
    else:
        logger.info("✅ All scans already have features!")


if __name__ == "__main__":
    asyncio.run(main())
