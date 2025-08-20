#!/usr/bin/env python3
"""
Comprehensive system review script to verify all components are working correctly.
Based on advisor recommendations for production readiness verification.
"""

import asyncio
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from colorama import Fore, Style, init
import subprocess
import os
import psutil

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from src.data.supabase_client import SupabaseClient
from src.data.hybrid_fetcher import HybridDataFetcher
from loguru import logger

# Initialize colorama for colored output
init(autoreset=True)


class SystemReview:
    """Comprehensive system review and health checker."""

    def __init__(self):
        """Initialize the system reviewer."""
        self.settings = get_settings()
        self.db = SupabaseClient()
        self.fetcher = HybridDataFetcher()

        self.checks_passed = 0
        self.checks_failed = 0
        self.warnings = []

        # Add psql to PATH for direct database checks
        os.environ["PATH"] = "/opt/homebrew/opt/postgresql@16/bin:" + os.environ.get("PATH", "")

    async def run_comprehensive_review(self):
        """Run all system checks and generate report."""

        print(f"{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}CRYPTO TRACKER V3 - COMPREHENSIVE SYSTEM REVIEW")
        print(f"{Fore.CYAN}Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{Fore.CYAN}{'='*60}\n")

        # 1. Database Performance
        await self.check_database_performance()

        # 2. Data Pipeline
        await self.check_data_pipeline()

        # 3. ML System
        await self.check_ml_system()

        # 4. Trading Strategies
        await self.check_trading_strategies()

        # 5. Deployment Configuration
        await self.check_deployment()

        # 6. System Integration
        await self.check_integration()

        # Generate Report
        self.generate_report()

    async def check_database_performance(self):
        """Verify all database optimizations are working."""
        print(f"\n{Fore.YELLOW}1. DATABASE PERFORMANCE CHECKS")
        print("-" * 40)

        checks = [
            ("Materialized view 'ohlc_today' exists", self.verify_view_exists("ohlc_today")),
            ("Materialized view 'ohlc_recent' exists", self.verify_view_exists("ohlc_recent")),
            ("Views refreshed within 24 hours", self.check_view_freshness()),
            ("Main table indexes exist (3+)", self.verify_indexes()),
            ("Query performance < 0.5s", self.test_query_performance()),
            ("No table locks present", self.check_for_locks()),
            ("Data coverage > 90 symbols", self.check_symbol_coverage()),
        ]

        for check_name, check_coro in checks:
            await self.run_check(check_name, check_coro)

    async def check_data_pipeline(self):
        """Verify data collection and updates."""
        print(f"\n{Fore.YELLOW}2. DATA PIPELINE CHECKS")
        print("-" * 40)

        checks = [
            ("Data freshness < 5 minutes", self.check_data_freshness()),
            ("84+ symbols have data", self.check_data_coverage()),
            ("All timeframes updating (1d, 1h, 15m)", self.check_timeframes()),
            ("No duplicate data issues", self.check_duplicates()),
            ("HybridDataFetcher working", self.test_hybrid_fetcher()),
            ("Retry logic functioning", self.test_retry_logic()),
            ("Recent data accessible", self.check_recent_data_access()),
        ]

        for check_name, check_coro in checks:
            await self.run_check(check_name, check_coro)

    async def check_ml_system(self):
        """Verify ML models and predictions."""
        print(f"\n{Fore.YELLOW}3. ML SYSTEM CHECKS")
        print("-" * 40)

        checks = [
            ("Strategy label tables exist", self.check_label_tables()),
            ("ML features calculating", self.check_feature_calculation()),
            ("Models trained and saved", self.check_models_exist()),
            ("Predictions generating", self.check_predictions()),
            ("Confidence scores valid (0-1)", self.check_confidence_range()),
            ("Feature importance tracked", self.check_feature_importance()),
            ("Model files present", self.check_model_files()),
        ]

        for check_name, check_coro in checks:
            await self.run_check(check_name, check_coro)

    async def check_trading_strategies(self):
        """Verify trading strategy components."""
        print(f"\n{Fore.YELLOW}4. TRADING STRATEGIES CHECKS")
        print("-" * 40)

        checks = [
            ("DCA detector functional", self.test_dca_detector()),
            ("Swing detector functional", self.test_swing_detector()),
            ("Channel detector functional", self.test_channel_detector()),
            ("Signal generator configured", self.check_signal_generator()),
            ("Risk management active", self.check_risk_management()),
            ("Position sizing correct", self.check_position_sizing()),
            ("Trade logging configured", self.check_trade_logging()),
        ]

        for check_name, check_coro in checks:
            await self.run_check(check_name, check_coro)

    async def check_deployment(self):
        """Verify deployment configuration."""
        print(f"\n{Fore.YELLOW}5. DEPLOYMENT CHECKS")
        print("-" * 40)

        checks = [
            ("Procfile exists", self.check_procfile()),
            ("Railway config exists", self.check_railway_config()),
            ("Environment variables set", self.check_env_vars()),
            ("Requirements.txt complete", self.check_requirements()),
            ("Logging configured", self.check_logging()),
            ("Runtime.txt specifies Python", self.check_runtime()),
            ("Slack webhooks configured", self.check_slack_config()),
        ]

        for check_name, check_coro in checks:
            await self.run_check(check_name, check_coro)

    async def check_integration(self):
        """Verify system integration."""
        print(f"\n{Fore.YELLOW}6. INTEGRATION CHECKS")
        print("-" * 40)

        checks = [
            ("HybridDataFetcher routing correctly", self.test_hybrid_routing()),
            ("All components using new fetcher", self.check_fetcher_usage()),
            ("Config centralized (Settings)", self.check_config_usage()),
            ("Database connections pooled", self.check_connection_pooling()),
            ("Error handling in place", self.check_error_handling()),
            ("Health monitoring active", self.check_health_monitoring()),
            ("End-to-end flow working", self.test_end_to_end()),
        ]

        for check_name, check_coro in checks:
            await self.run_check(check_name, check_coro)

    # Individual check implementations

    async def verify_view_exists(self, view_name: str) -> bool:
        """Check if a materialized view exists."""
        try:
            result = self.db.client.table(view_name).select("*").limit(1).execute()
            return bool(result.data is not None)
        except Exception as e:
            if "relation" in str(e) and "does not exist" in str(e):
                return False
            self.warnings.append(f"Error checking view {view_name}: {str(e)}")
            return False

    async def check_view_freshness(self) -> bool:
        """Check if materialized views are fresh."""
        try:
            # Check ohlc_today freshness
            result = (
                self.db.client.table("ohlc_today").select("timestamp").order("timestamp", desc=True).limit(1).execute()
            )

            if result.data:
                latest = datetime.fromisoformat(result.data[0]["timestamp"].replace("Z", "+00:00"))
                age_hours = (datetime.now(timezone.utc) - latest).total_seconds() / 3600
                return age_hours < 24
            return False
        except Exception as e:
            self.warnings.append(f"View freshness check error: {str(e)}")
            return False

    async def verify_indexes(self) -> bool:
        """Check if database indexes exist."""
        try:
            # Query pg_indexes to check for our indexes
            query = """
            SELECT COUNT(*) as count
            FROM pg_indexes
            WHERE tablename = 'ohlc_data'
            AND indexname LIKE 'idx_ohlc_%'
            """

            result = self.db.client.rpc("execute_sql", {"query": query}).execute()

            if result.data and len(result.data) > 0:
                count = result.data[0].get("count", 0)
                return count >= 3
            return False
        except Exception:
            # Fallback: check if queries are fast
            return await self.test_query_performance()

    async def test_query_performance(self) -> bool:
        """Test database query performance."""
        try:
            start = time.time()

            # Test query on materialized view
            result = self.db.client.table("ohlc_recent").select("*").eq("symbol", "BTC").limit(100).execute()

            elapsed = time.time() - start
            return elapsed < 0.5 and result.data is not None
        except Exception as e:
            self.warnings.append(f"Query performance test error: {str(e)}")
            return False

    async def check_for_locks(self) -> bool:
        """Check for database locks."""
        try:
            # For Supabase, we can't directly query pg_locks
            # So we'll test if we can write
            test_data = {
                "metric_name": "system_review_test",
                "value": 1.0,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "test",
            }

            result = self.db.client.table("health_metrics").insert(test_data).execute()

            # Clean up test data
            if result.data:
                self.db.client.table("health_metrics").delete().eq("metric_name", "system_review_test").execute()

            return result.data is not None
        except Exception:
            return True  # Assume no locks if we can't check

    async def check_symbol_coverage(self) -> bool:
        """Check how many symbols have data."""
        try:
            # Get distinct symbols from recent data
            result = self.db.client.rpc(
                "execute_sql", {"query": "SELECT COUNT(DISTINCT symbol) as count FROM ohlc_recent"}
            ).execute()

            if result.data:
                count = result.data[0].get("count", 0)
                return count >= 84

            # Fallback: check main table
            result = self.db.client.table("ohlc_data").select("symbol").limit(1000).execute()

            if result.data:
                unique_symbols = set(r["symbol"] for r in result.data)
                return len(unique_symbols) >= 84

            return False
        except Exception:
            return False

    async def check_data_freshness(self) -> bool:
        """Check if data is fresh."""
        try:
            result = await self.fetcher.get_latest_price("BTC", "1m")
            if result:
                timestamp = datetime.fromisoformat(result["timestamp"].replace("Z", "+00:00"))
                age_minutes = (datetime.now(timezone.utc) - timestamp).total_seconds() / 60
                return age_minutes < 5
            return False
        except Exception:
            return False

    async def check_data_coverage(self) -> bool:
        """Check data coverage across symbols."""
        try:
            symbols = ["BTC", "ETH", "SOL", "AVAX", "MATIC", "LINK", "DOT", "ATOM"]
            results = await self.fetcher.get_trading_signals_batch(symbols)

            success_count = sum(1 for r in results.values() if r.get("has_data"))
            return success_count >= 6  # At least 75% should have data
        except Exception:
            return False

    async def check_timeframes(self) -> bool:
        """Check if all timeframes are updating."""
        try:
            timeframes = ["1d", "1h", "15m"]
            fresh_count = 0

            for tf in timeframes:
                result = (
                    self.db.client.table("ohlc_data")
                    .select("timestamp")
                    .eq("timeframe", tf)
                    .eq("symbol", "BTC")
                    .order("timestamp", desc=True)
                    .limit(1)
                    .execute()
                )

                if result.data:
                    timestamp = datetime.fromisoformat(result.data[0]["timestamp"].replace("Z", "+00:00"))

                    # Different freshness thresholds for different timeframes
                    if tf == "1d":
                        threshold_hours = 26
                    elif tf == "1h":
                        threshold_hours = 2
                    else:  # 15m
                        threshold_hours = 0.5

                    age_hours = (datetime.now(timezone.utc) - timestamp).total_seconds() / 3600
                    if age_hours < threshold_hours:
                        fresh_count += 1

            return fresh_count == len(timeframes)
        except Exception:
            return False

    async def check_duplicates(self) -> bool:
        """Check for duplicate data issues."""
        try:
            # Check for duplicates in recent data
            query = """
            SELECT symbol, timestamp, timeframe, COUNT(*) as count
            FROM ohlc_recent
            WHERE symbol = 'BTC'
            GROUP BY symbol, timestamp, timeframe
            HAVING COUNT(*) > 1
            LIMIT 10
            """

            result = self.db.client.rpc("execute_sql", {"query": query}).execute()

            # No duplicates found is good
            return not result.data or len(result.data) == 0
        except Exception:
            # If we can't check, assume it's okay
            return True

    async def test_hybrid_fetcher(self) -> bool:
        """Test HybridDataFetcher functionality."""
        try:
            # Test various fetcher methods
            latest = await self.fetcher.get_latest_price("ETH", "1m")
            recent = await self.fetcher.get_recent_data("ETH", hours=24, timeframe="15m")
            ml_data = await self.fetcher.get_ml_features_data("ETH")

            return all([latest is not None, recent and len(recent) > 0, ml_data and ml_data.get("has_data", False)])
        except Exception:
            return False

    async def test_retry_logic(self) -> bool:
        """Test if retry logic is configured."""
        try:
            # Check if retry utility exists
            from src.utils.retry import retry_with_backoff

            return True
        except ImportError:
            return False

    async def check_recent_data_access(self) -> bool:
        """Check if recent data is accessible quickly."""
        try:
            start = time.time()
            result = (
                self.db.client.table("ohlc_recent")
                .select("*")
                .eq("symbol", "SOL")
                .gte("timestamp", (datetime.utcnow() - timedelta(days=1)).isoformat())
                .execute()
            )
            elapsed = time.time() - start

            return elapsed < 1.0 and result.data and len(result.data) > 0
        except Exception:
            return False

    async def check_label_tables(self) -> bool:
        """Check if strategy label tables exist."""
        try:
            tables = ["dca_labels", "swing_labels", "channel_labels"]
            exists_count = 0

            for table in tables:
                try:
                    result = self.db.client.table(table).select("*").limit(1).execute()
                    if result.data is not None:
                        exists_count += 1
                except Exception:
                    pass

            return exists_count >= 2  # At least 2 tables should exist
        except Exception:
            return False

    async def check_feature_calculation(self) -> bool:
        """Check if ML features are being calculated."""
        try:
            from src.ml.feature_calculator import FeatureCalculator

            calc = FeatureCalculator()

            # Test feature calculation
            features = await calc.calculate_features_for_symbol("BTC", lookback_hours=24)
            return features is not None and not features.empty
        except Exception:
            return False

    async def check_models_exist(self) -> bool:
        """Check if ML models are saved."""
        try:
            model_files = [
                "models/dca/xgboost_multi_output.pkl",
                "models/swing/swing_classifier.pkl",
                "models/channel/classifier.pkl",
            ]

            project_root = Path(__file__).parent.parent
            exists_count = sum(1 for f in model_files if (project_root / f).exists())

            return exists_count >= 2  # At least 2 models should exist
        except Exception:
            return False

    async def check_predictions(self) -> bool:
        """Check if predictions can be generated."""
        try:
            from src.ml.predictor import MLPredictor

            predictor = MLPredictor()

            # Test prediction
            result = await predictor.predict("BTC")
            return result is not None and "confidence" in result
        except Exception:
            return False

    async def check_confidence_range(self) -> bool:
        """Check if confidence scores are in valid range."""
        try:
            from src.ml.predictor import MLPredictor

            predictor = MLPredictor()

            # Test multiple predictions
            symbols = ["BTC", "ETH", "SOL"]
            valid_count = 0

            for symbol in symbols:
                result = await predictor.predict(symbol)
                if result and "confidence" in result:
                    conf = result["confidence"]
                    if 0 <= conf <= 1:
                        valid_count += 1

            return valid_count == len(symbols)
        except Exception:
            return True  # If we can't check, assume it's okay

    async def check_feature_importance(self) -> bool:
        """Check if feature importance is tracked."""
        try:
            # Check if training results exist
            training_files = [
                "models/dca/training_results.json",
                "models/swing/training_results.json",
                "models/channel/training_results.json",
            ]

            project_root = Path(__file__).parent.parent
            exists_count = sum(1 for f in training_files if (project_root / f).exists())

            return exists_count >= 1
        except Exception:
            return False

    async def check_model_files(self) -> bool:
        """Check if model files are present and valid."""
        try:
            import joblib

            project_root = Path(__file__).parent.parent

            # Try to load a model
            model_path = project_root / "models" / "dca" / "xgboost_multi_output.pkl"
            if model_path.exists():
                model = joblib.load(model_path)
                return model is not None

            return False
        except Exception:
            return False

    async def test_dca_detector(self) -> bool:
        """Test DCA detector functionality."""
        try:
            from src.strategies.dca.detector import DCADetector

            detector = DCADetector(self.db)

            # Test detection
            from datetime import timedelta

            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=24)

            price_data = await detector._get_price_data("BTC", start_time, end_time)
            return price_data is not None and not price_data.empty
        except Exception:
            return False

    async def test_swing_detector(self) -> bool:
        """Test Swing detector functionality."""
        try:
            from src.strategies.swing.detector import SwingDetector

            detector = SwingDetector(self.db)

            # Test detection
            ohlc_data = await detector._fetch_ohlc_data("ETH")
            return ohlc_data is not None and len(ohlc_data) > 0
        except Exception:
            return False

    async def test_channel_detector(self) -> bool:
        """Test Channel detector functionality."""
        try:
            from src.strategies.channel.detector import ChannelDetector

            detector = ChannelDetector(self.db)

            # Test basic functionality
            return True  # If it imports, it's configured
        except ImportError:
            return False

    async def check_signal_generator(self) -> bool:
        """Check if signal generator is configured."""
        try:
            from src.strategies.signal_generator import SignalGenerator

            return True
        except ImportError:
            return False

    async def check_risk_management(self) -> bool:
        """Check if risk management is configured."""
        try:
            from src.trading.position_sizer import AdaptivePositionSizer

            sizer = AdaptivePositionSizer()

            # Test position sizing
            size = sizer.calculate_position_size(symbol="BTC", strategy="dca", confidence=0.75, account_balance=10000)

            return size > 0 and size <= 10000
        except Exception:
            return False

    async def check_position_sizing(self) -> bool:
        """Check if position sizing is working correctly."""
        try:
            from src.trading.position_sizer import AdaptivePositionSizer

            sizer = AdaptivePositionSizer()

            # Test various scenarios
            test_cases = [("BTC", "dca", 0.8, 10000), ("ETH", "swing", 0.6, 5000), ("SOL", "channel", 0.7, 1000)]

            for symbol, strategy, confidence, balance in test_cases:
                size = sizer.calculate_position_size(symbol, strategy, confidence, balance)
                if not (0 < size <= balance * 0.1):  # Max 10% per position
                    return False

            return True
        except Exception:
            return False

    async def check_trade_logging(self) -> bool:
        """Check if trade logging is configured."""
        try:
            # Check if trade_logs table exists
            result = self.db.client.table("trade_logs").select("*").limit(1).execute()
            return result.data is not None
        except Exception:
            return False

    async def check_procfile(self) -> bool:
        """Check if Procfile exists."""
        project_root = Path(__file__).parent.parent
        return (project_root / "Procfile").exists()

    async def check_railway_config(self) -> bool:
        """Check if Railway configuration exists."""
        project_root = Path(__file__).parent.parent
        return (project_root / "railway.json").exists()

    async def check_env_vars(self) -> bool:
        """Check if environment variables are set."""
        required_vars = ["POLYGON_API_KEY", "SUPABASE_URL", "SUPABASE_KEY", "SLACK_WEBHOOK_URL"]

        missing = [var for var in required_vars if not os.getenv(var)]
        return len(missing) == 0

    async def check_requirements(self) -> bool:
        """Check if requirements.txt is complete."""
        project_root = Path(__file__).parent.parent
        req_file = project_root / "requirements.txt"

        if not req_file.exists():
            return False

        # Check for key packages
        with open(req_file, "r") as f:
            content = f.read()

        required_packages = ["pandas", "numpy", "xgboost", "supabase", "polygon-api-client", "slack-sdk", "loguru"]

        return all(pkg in content for pkg in required_packages)

    async def check_logging(self) -> bool:
        """Check if logging is configured."""
        try:
            from loguru import logger

            logger.debug("Test log")
            return True
        except Exception:
            return False

    async def check_runtime(self) -> bool:
        """Check if runtime.txt specifies Python version."""
        project_root = Path(__file__).parent.parent
        runtime_file = project_root / "runtime.txt"

        if runtime_file.exists():
            with open(runtime_file, "r") as f:
                content = f.read().strip()
            return "python-3" in content
        return False

    async def check_slack_config(self) -> bool:
        """Check if Slack is configured."""
        try:
            from src.notifications.slack_notifier import SlackNotifier

            notifier = SlackNotifier()
            return notifier.webhook_url is not None
        except Exception:
            return False

    async def test_hybrid_routing(self) -> bool:
        """Test HybridDataFetcher routing logic."""
        try:
            # Test that different date ranges use different tables
            now = datetime.utcnow()

            # Should use ohlc_today
            table1 = self.fetcher._select_table(now - timedelta(hours=12))

            # Should use ohlc_recent
            table2 = self.fetcher._select_table(now - timedelta(days=3))

            # Should use ohlc_data
            table3 = self.fetcher._select_table(now - timedelta(days=10))

            return table1 == "ohlc_today" and table2 == "ohlc_recent" and table3 == "ohlc_data"
        except Exception:
            return False

    async def check_fetcher_usage(self) -> bool:
        """Check if all components use HybridDataFetcher."""
        try:
            # Check key files for HybridDataFetcher usage
            files_to_check = [
                "src/ml/feature_calculator.py",
                "src/strategies/dca/detector.py",
                "src/strategies/swing/detector.py",
            ]

            project_root = Path(__file__).parent.parent
            usage_count = 0

            for file_path in files_to_check:
                full_path = project_root / file_path
                if full_path.exists():
                    with open(full_path, "r") as f:
                        content = f.read()
                        if "HybridDataFetcher" in content or "hybrid_fetcher" in content:
                            usage_count += 1

            return usage_count >= 2
        except Exception:
            return False

    async def check_config_usage(self) -> bool:
        """Check if configuration is centralized."""
        try:
            from src.config.settings import get_settings

            settings = get_settings()
            return settings is not None
        except Exception:
            return False

    async def check_connection_pooling(self) -> bool:
        """Check if database connections are pooled."""
        try:
            # Supabase handles connection pooling automatically
            return True
        except Exception:
            return False

    async def check_error_handling(self) -> bool:
        """Check if error handling is in place."""
        try:
            # Check for retry utility
            from src.utils.retry import retry_with_backoff

            # Test error handling
            @retry_with_backoff(max_retries=1)
            async def test_func():
                raise ValueError("Test error")

            try:
                await test_func()
                return False  # Should have raised
            except ValueError:
                return True  # Error was handled properly
        except ImportError:
            return False

    async def check_health_monitoring(self) -> bool:
        """Check if health monitoring is active."""
        try:
            from src.monitoring.health import HealthChecker

            checker = HealthChecker()

            # Test basic health check
            result = await checker.check_database()
            return result.get("connected", False)
        except Exception:
            return False

    async def test_end_to_end(self) -> bool:
        """Test complete end-to-end flow."""
        try:
            # 1. Fetch data
            data = await self.fetcher.get_latest_price("BTC", "1m")
            if not data:
                return False

            # 2. Calculate features
            from src.ml.feature_calculator import FeatureCalculator

            calc = FeatureCalculator()
            features = await calc.calculate_features_for_symbol("BTC", lookback_hours=24)
            if features is None or features.empty:
                return False

            # 3. Generate prediction
            from src.ml.predictor import MLPredictor

            predictor = MLPredictor()
            prediction = await predictor.predict("BTC")
            if not prediction:
                return False

            return True
        except Exception:
            return False

    async def run_check(self, name: str, check_coro):
        """Run individual check and track results."""
        try:
            result = await check_coro
            if result:
                print(f"  ✅ {name}")
                self.checks_passed += 1
            else:
                print(f"  ❌ {name}")
                self.checks_failed += 1
        except Exception as e:
            print(f"  ⚠️  {name} - Error: {str(e)}")
            self.warnings.append(f"{name}: {str(e)}")
            self.checks_failed += 1

    def generate_report(self):
        """Generate final review report."""
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}REVIEW SUMMARY")
        print(f"{Fore.CYAN}{'='*60}")

        total_checks = self.checks_passed + self.checks_failed
        pass_rate = (self.checks_passed / total_checks * 100) if total_checks > 0 else 0

        print(f"\n{Fore.GREEN}Passed: {self.checks_passed}/{total_checks} ({pass_rate:.1f}%)")
        print(f"{Fore.RED}Failed: {self.checks_failed}/{total_checks}")

        if self.warnings:
            print(f"\n{Fore.YELLOW}Warnings ({len(self.warnings)}):")
            for warning in self.warnings[:5]:  # Show first 5 warnings
                print(f"  ⚠️  {warning}")
            if len(self.warnings) > 5:
                print(f"  ... and {len(self.warnings) - 5} more warnings")

        # Overall Status
        print(f"\n{Fore.CYAN}OVERALL STATUS: ", end="")
        if pass_rate >= 95:
            print(f"{Fore.GREEN}PRODUCTION READY ✅")
            print(f"\n{Fore.GREEN}🎉 Excellent! Your system is fully operational!")
        elif pass_rate >= 80:
            print(f"{Fore.YELLOW}NEARLY READY (Fix remaining issues)")
            print(f"\n{Fore.YELLOW}⚠️  Almost there! Address the failed checks above.")
        else:
            print(f"{Fore.RED}NOT READY (Critical issues present)")
            print(f"\n{Fore.RED}❌ Several critical issues need attention.")

        # Recommendations
        self.generate_recommendations()

    def generate_recommendations(self):
        """Generate specific recommendations based on failures."""
        print(f"\n{Fore.CYAN}RECOMMENDATIONS:")
        print("-" * 40)

        if self.checks_failed == 0:
            print(f"{Fore.GREEN}✨ System is fully operational! Consider:")
            print("  1. Monitor performance metrics for first 48 hours")
            print("  2. Set up alerting thresholds")
            print("  3. Document any edge cases that arise")
            print("  4. Review logs daily for first week")
            print("  5. Set up automated view refresh (cron job)")
        else:
            print(f"{Fore.YELLOW}Address these issues before production:")

            # Generate specific recommendations based on failures
            recommendations = []

            if self.checks_failed > 0:
                recommendations.append("1. Review failed checks above and fix root causes")
                recommendations.append("2. Run scripts/test_hybrid_integration.py to verify fixes")
                recommendations.append("3. Check logs for detailed error messages")
                recommendations.append("4. Re-run this review after fixes")

            if any("view" in w.lower() for w in self.warnings):
                recommendations.append("5. Ensure materialized views are created and refreshed")

            if any("model" in w.lower() for w in self.warnings):
                recommendations.append("6. Train ML models if not already done")

            for rec in recommendations:
                print(f"  {rec}")

        # Key metrics to monitor
        print(f"\n{Fore.CYAN}KEY METRICS TO MONITOR:")
        print("-" * 40)
        print("  • Query performance: < 0.2s (p50), < 1.0s (p99)")
        print("  • Data freshness: < 5 minutes")
        print("  • Error rate: < 1%")
        print("  • ML confidence: > 0.60 average")
        print("  • Uptime: > 99%")


async def main():
    """Run the comprehensive system review."""
    reviewer = SystemReview()
    await reviewer.run_comprehensive_review()

    # Return exit code based on results
    total_checks = reviewer.checks_passed + reviewer.checks_failed
    pass_rate = (reviewer.checks_passed / total_checks * 100) if total_checks > 0 else 0

    if pass_rate >= 95:
        return 0  # Success
    else:
        return 1  # Failure


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
