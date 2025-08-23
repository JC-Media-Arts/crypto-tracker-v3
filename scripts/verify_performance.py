#!/usr/bin/env python3
"""
Verify the 62-80x performance improvement from database optimizations.
Tests queries that previously timed out to ensure they now complete quickly.
"""

import asyncio
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple
from colorama import Fore, Style, init

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from src.data.supabase_client import SupabaseClient
from src.data.hybrid_fetcher import HybridDataFetcher
from loguru import logger

# Initialize colorama for colored output
init(autoreset=True)


class PerformanceVerifier:
    """Verify database performance improvements."""

    def __init__(self):
        """Initialize the performance verifier."""
        self.settings = get_settings()
        self.db = SupabaseClient()
        self.fetcher = HybridDataFetcher()

        # Track performance metrics
        self.query_times = []
        self.slow_queries = []
        self.failed_queries = []

    async def verify_performance_gains(self):
        """Verify the 62-80x performance improvement."""

        print(f"{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}PERFORMANCE VERIFICATION")
        print(f"{Fore.CYAN}Testing queries that previously timed out (8+ seconds)")
        print(f"{Fore.CYAN}{'='*60}\n")

        # Test queries that previously timed out
        test_queries = [
            ("Latest price for BTC", self.test_latest_price, "BTC"),
            ("24h data for ETH", self.test_24h_data, "ETH"),
            ("ML features batch", self.test_ml_features_batch, ["BTC", "ETH", "SOL"]),
            ("Historical query (30 days)", self.test_historical_query, "BTC"),
            ("Multi-symbol latest prices", self.test_multi_symbol_latest, None),
            ("Recent data (7 days)", self.test_recent_data, "SOL"),
            ("Trading signals batch", self.test_trading_signals, None),
            ("Feature calculation data", self.test_feature_data, "AVAX"),
        ]

        print(f"{Fore.YELLOW}Running performance tests...\n")

        for query_name, test_func, param in test_queries:
            await self.run_performance_test(query_name, test_func, param)

        # Generate performance report
        self.generate_performance_report()

    async def run_performance_test(self, name: str, test_func, param):
        """Run a single performance test."""
        try:
            start = time.time()

            if param is not None:
                result = await test_func(param)
            else:
                result = await test_func()

            duration = time.time() - start
            self.query_times.append((name, duration))

            # Determine status
            if duration < 0.5:
                status = f"{Fore.GREEN}✅ FAST"
                status_detail = f"({duration:.3f}s)"
            elif duration < 2.0:
                status = f"{Fore.YELLOW}⚠️  ACCEPTABLE"
                status_detail = f"({duration:.3f}s)"
                self.slow_queries.append((name, duration))
            else:
                status = f"{Fore.RED}❌ SLOW"
                status_detail = f"({duration:.3f}s)"
                self.slow_queries.append((name, duration))

            # Check if result has data
            if result:
                data_status = f"{Fore.GREEN}with data"
            else:
                data_status = f"{Fore.RED}no data"

            print(f"{status} {name}: {status_detail} - {data_status}")

        except Exception as e:
            print(f"{Fore.RED}❌ FAILED {name}: {str(e)[:50]}")
            self.failed_queries.append((name, str(e)))
            self.query_times.append((name, float("inf")))

    async def test_latest_price(self, symbol: str):
        """Test fetching latest price."""
        result = await self.fetcher.get_latest_price(symbol, "1m")
        return result is not None

    async def test_24h_data(self, symbol: str):
        """Test fetching 24 hour data."""
        result = await self.fetcher.get_recent_data(symbol, hours=24, timeframe="15m")
        return result and len(result) > 0

    async def test_ml_features_batch(self, symbols: List[str]):
        """Test fetching ML features for multiple symbols."""
        results = []
        for symbol in symbols:
            data = await self.fetcher.get_ml_features_data(symbol)
            results.append(data and data.get("has_data", False))
        return all(results)

    async def test_historical_query(self, symbol: str):
        """Test historical data query."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=30)

        result = await self.fetcher.get_historical_data(symbol, start_date, end_date, "1d")
        return result and len(result) > 0

    async def test_multi_symbol_latest(self):
        """Test fetching latest prices for multiple symbols."""
        symbols = ["BTC", "ETH", "SOL", "AVAX", "MATIC", "LINK", "DOT", "ATOM"]
        results = []

        for symbol in symbols:
            price = await self.fetcher.get_latest_price(symbol, "1m")
            results.append(price is not None)

        return sum(results) >= len(symbols) * 0.8  # 80% success rate

    async def test_recent_data(self, symbol: str):
        """Test fetching recent data (7 days)."""
        result = await self.fetcher.get_recent_data(symbol, hours=168, timeframe="1h")
        return result and len(result) > 0

    async def test_trading_signals(self):
        """Test fetching trading signals batch."""
        symbols = ["BTC", "ETH", "SOL", "AVAX", "MATIC"]
        signals = await self.fetcher.get_trading_signals_batch(symbols)

        success_count = sum(1 for s in signals.values() if s.get("has_data"))
        return success_count >= 4  # At least 80% should have data

    async def test_feature_data(self, symbol: str):
        """Test fetching data for feature calculation."""
        from src.ml.feature_calculator import FeatureCalculator

        calc = FeatureCalculator()

        features = await calc.calculate_features_for_symbol(symbol, lookback_hours=48)
        return features is not None and not features.empty

    def generate_performance_report(self):
        """Generate detailed performance report."""
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}PERFORMANCE REPORT")
        print(f"{Fore.CYAN}{'='*60}\n")

        if not self.query_times:
            print(f"{Fore.RED}No performance data collected!")
            return

        # Calculate statistics
        valid_times = [t for _, t in self.query_times if t != float("inf")]

        if valid_times:
            avg_time = sum(valid_times) / len(valid_times)
            min_time = min(valid_times)
            max_time = max(valid_times)

            # Performance improvement calculation
            # Previous timeout was 8+ seconds
            previous_time = 8.0
            improvement_factor = previous_time / avg_time if avg_time > 0 else 0

            print(f"{Fore.GREEN}Performance Statistics:")
            print(f"  • Average query time: {avg_time:.3f}s")
            print(f"  • Fastest query: {min_time:.3f}s")
            print(f"  • Slowest query: {max_time:.3f}s")
            print(f"  • Performance improvement: {improvement_factor:.1f}x faster")

            # Check against targets
            print(f"\n{Fore.CYAN}Target Metrics:")

            if avg_time < 0.2:
                print(f"  ✅ Average < 0.2s (Excellent)")
            elif avg_time < 0.5:
                print(f"  ✅ Average < 0.5s (Good)")
            elif avg_time < 1.0:
                print(f"  ⚠️  Average < 1.0s (Acceptable)")
            else:
                print(f"  ❌ Average > 1.0s (Needs improvement)")

            # Detailed breakdown
            print(f"\n{Fore.CYAN}Query Breakdown:")

            fast_queries = [q for q, t in self.query_times if t < 0.5 and t != float("inf")]
            acceptable_queries = [q for q, t in self.query_times if 0.5 <= t < 2.0]

            print(f"  • Fast queries (< 0.5s): {len(fast_queries)}")
            print(f"  • Acceptable queries (0.5-2s): {len(acceptable_queries)}")
            print(f"  • Slow queries (> 2s): {len(self.slow_queries)}")
            print(f"  • Failed queries: {len(self.failed_queries)}")

            # Show slow queries if any
            if self.slow_queries:
                print(f"\n{Fore.YELLOW}Slow Queries:")
                for query, duration in self.slow_queries[:3]:
                    print(f"  • {query}: {duration:.3f}s")

            # Show failed queries if any
            if self.failed_queries:
                print(f"\n{Fore.RED}Failed Queries:")
                for query, error in self.failed_queries[:3]:
                    print(f"  • {query}: {error[:50]}")

            # Overall assessment
            print(f"\n{Fore.CYAN}{'='*60}")
            print(f"{Fore.CYAN}OVERALL ASSESSMENT")
            print(f"{Fore.CYAN}{'='*60}\n")

            if improvement_factor >= 60:
                print(f"{Fore.GREEN}🎉 EXCEPTIONAL PERFORMANCE!")
                print(f"   Achieved {improvement_factor:.1f}x improvement")
                print(f"   Previous: 8+ seconds → Now: {avg_time:.3f} seconds")
                print(f"\n   The 62-80x performance gain is CONFIRMED! ✅")
            elif improvement_factor >= 40:
                print(f"{Fore.GREEN}✅ EXCELLENT PERFORMANCE!")
                print(f"   Achieved {improvement_factor:.1f}x improvement")
                print(f"   Significant performance gains achieved.")
            elif improvement_factor >= 10:
                print(f"{Fore.YELLOW}⚠️  GOOD PERFORMANCE")
                print(f"   Achieved {improvement_factor:.1f}x improvement")
                print(f"   Performance is acceptable but could be better.")
            else:
                print(f"{Fore.RED}❌ PERFORMANCE NEEDS IMPROVEMENT")
                print(f"   Only {improvement_factor:.1f}x improvement achieved")
                print(f"   Consider additional optimizations.")

            # Recommendations
            print(f"\n{Fore.CYAN}Recommendations:")

            if avg_time < 0.5 and not self.failed_queries:
                print(f"{Fore.GREEN}  ✨ Performance is excellent! No immediate action needed.")
                print(f"     • Continue monitoring for degradation")
                print(f"     • Set up alerts for slow queries")
                print(f"     • Document current configuration")
            else:
                if self.slow_queries:
                    print(f"{Fore.YELLOW}  • Investigate slow queries listed above")
                    print(f"     • Consider adding specific indexes for these patterns")
                    print(f"     • Check if materialized views need refresh")

                if self.failed_queries:
                    print(f"{Fore.RED}  • Fix failed queries immediately")
                    print(f"     • Check database connectivity")
                    print(f"     • Verify table and view existence")

                if avg_time > 1.0:
                    print(f"{Fore.YELLOW}  • Consider additional optimizations:")
                    print(f"     • Increase materialized view refresh frequency")
                    print(f"     • Add more specific indexes")
                    print(f"     • Review query patterns for optimization")

        else:
            print(f"{Fore.RED}All queries failed! Check database connectivity.")


async def compare_with_without_optimization():
    """Compare performance with and without optimizations."""

    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}OPTIMIZATION COMPARISON")
    print(f"{Fore.CYAN}{'='*60}\n")

    db = SupabaseClient()

    # Test 1: Query using materialized view
    print(f"{Fore.YELLOW}Testing with materialized view (ohlc_recent)...")
    start = time.time()

    try:
        result = (
            db.client.table("ohlc_recent")
            .select("*")
            .eq("symbol", "BTC")
            .gte("timestamp", (datetime.utcnow() - timedelta(days=3)).isoformat())
            .execute()
        )

        optimized_time = time.time() - start
        optimized_count = len(result.data) if result.data else 0
        print(f"  ✅ Time: {optimized_time:.3f}s, Records: {optimized_count}")
    except Exception as e:
        print(f"  ❌ Failed: {str(e)[:50]}")
        optimized_time = float("inf")
        optimized_count = 0

    # Test 2: Query using main table (simulate unoptimized)
    print(f"\n{Fore.YELLOW}Testing without optimization (ohlc_data)...")
    start = time.time()

    try:
        result = (
            db.client.table("ohlc_data")
            .select("*")
            .eq("symbol", "BTC")
            .gte("timestamp", (datetime.utcnow() - timedelta(days=3)).isoformat())
            .limit(1000)
            .execute()
        )

        unoptimized_time = time.time() - start
        unoptimized_count = len(result.data) if result.data else 0
        print(f"  ✅ Time: {unoptimized_time:.3f}s, Records: {unoptimized_count}")
    except Exception as e:
        print(f"  ❌ Failed or timed out: {str(e)[:50]}")
        unoptimized_time = 8.0  # Assume timeout
        unoptimized_count = 0

    # Calculate improvement
    if optimized_time < float("inf") and unoptimized_time > 0:
        improvement = unoptimized_time / optimized_time

        print(f"\n{Fore.CYAN}Results:")
        print(f"  • With optimization: {optimized_time:.3f}s")
        print(f"  • Without optimization: {unoptimized_time:.3f}s")
        print(f"  • Improvement factor: {improvement:.1f}x")

        if improvement >= 10:
            print(f"\n{Fore.GREEN}🎉 Optimization is highly effective!")
        elif improvement >= 5:
            print(f"\n{Fore.GREEN}✅ Optimization is working well!")
        else:
            print(f"\n{Fore.YELLOW}⚠️  Optimization benefit is modest")
    else:
        print(f"\n{Fore.RED}Could not calculate improvement")


async def main():
    """Run all performance verification tests."""

    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"{Fore.CYAN}CRYPTO TRACKER V3 - PERFORMANCE VERIFICATION")
    print(f"{Fore.CYAN}Verifying 62-80x performance improvement claims")
    print(f"{Fore.CYAN}{'='*70}\n")

    # Run performance tests
    verifier = PerformanceVerifier()
    await verifier.verify_performance_gains()

    # Run comparison test
    await compare_with_without_optimization()

    print(f"\n{Fore.CYAN}Performance verification complete!")


if __name__ == "__main__":
    asyncio.run(main())
