#!/usr/bin/env python3
"""
Shadow Testing System Integration Test
Validates all components of the shadow testing system
"""

import sys
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List
from loguru import logger
import json
import pandas as pd

sys.path.append(".")

from src.data.supabase_client import SupabaseClient
from src.analysis.shadow_logger import ShadowLogger
from src.analysis.shadow_evaluator import ShadowEvaluator
from src.analysis.shadow_analyzer import ShadowAnalyzer
from src.trading.threshold_manager import ThresholdManager
from src.ml.shadow_enhanced_retrainer import ShadowEnhancedRetrainer
from src.config.shadow_config import ShadowConfig


class ShadowSystemTester:
    """Test harness for shadow testing system"""

    def __init__(self):
        self.supabase = SupabaseClient()
        self.shadow_logger = ShadowLogger(self.supabase.client)
        self.shadow_evaluator = ShadowEvaluator(self.supabase.client)
        self.shadow_analyzer = ShadowAnalyzer(self.supabase.client)
        self.threshold_manager = ThresholdManager(self.supabase.client)
        self.retrainer = ShadowEnhancedRetrainer(self.supabase.client)
        self.test_results = {}

    async def run_all_tests(self):
        """Run comprehensive system tests"""
        logger.info("=" * 60)
        logger.info("SHADOW TESTING SYSTEM - INTEGRATION TEST")
        logger.info("=" * 60)

        # Test 1: Configuration
        await self.test_configuration()

        # Test 2: Shadow Logging
        await self.test_shadow_logging()

        # Test 3: Shadow Evaluation
        await self.test_shadow_evaluation()

        # Test 4: Performance Analysis
        await self.test_performance_analysis()

        # Test 5: Threshold Management
        await self.test_threshold_management()

        # Test 6: ML Integration
        await self.test_ml_integration()

        # Test 7: Database Integrity
        await self.test_database_integrity()

        # Print summary
        self.print_test_summary()

        return self.test_results

    async def test_configuration(self):
        """Test shadow configuration setup"""
        logger.info("\n📋 Testing Configuration...")

        try:
            # Check active variations
            active_variations = ShadowConfig.get_active_variations()
            assert (
                len(active_variations) == 8
            ), f"Expected 8 variations, got {len(active_variations)}"

            # Check database configuration
            result = (
                self.supabase.client.table("shadow_configuration").select("*").execute()
            )

            assert result.data, "No shadow configurations in database"
            assert (
                len(result.data) >= 8
            ), f"Expected at least 8 configurations, got {len(result.data)}"

            # Verify each variation
            for var_name in active_variations:
                var_config = ShadowConfig.VARIATIONS.get(var_name)
                assert var_config, f"Missing configuration for {var_name}"
                assert var_config.type in [
                    "champion",
                    "scenario",
                    "isolated",
                ], f"Invalid type for {var_name}"

            self.test_results["configuration"] = "PASSED ✅"
            logger.info("✅ Configuration test passed")

        except Exception as e:
            self.test_results["configuration"] = f"FAILED ❌: {str(e)}"
            logger.error(f"❌ Configuration test failed: {e}")

    async def test_shadow_logging(self):
        """Test shadow logging functionality"""
        logger.info("\n📝 Testing Shadow Logging...")

        try:
            # Create a mock scan
            mock_scan_id = await self._create_mock_scan()

            # Log shadow decisions
            decisions = await self.shadow_logger.log_shadow_decisions(
                scan_id=mock_scan_id,
                symbol="BTC",
                strategy_name="DCA",
                features={"rsi": 45, "volume": 1000000},
                ml_predictions={
                    "take_profit_pct": 10,
                    "stop_loss_pct": 5,
                    "hold_hours": 24,
                },
                ml_confidence=0.62,
                current_price=50000,
                base_parameters={"min_confidence": 0.60, "position_size": 100},
            )

            assert decisions, "No shadow decisions generated"
            assert (
                len(decisions) >= 5
            ), f"Expected at least 5 decisions, got {len(decisions)}"

            # Verify decisions were logged
            await self.shadow_logger.flush()

            # Check database
            result = (
                self.supabase.client.table("shadow_variations")
                .select("*")
                .eq("scan_id", mock_scan_id)
                .execute()
            )

            assert result.data, "Shadow variations not saved to database"
            assert (
                len(result.data) >= 5
            ), f"Expected at least 5 variations saved, got {len(result.data)}"

            # Check consensus calculation
            consensus = self.shadow_logger.get_shadow_consensus(decisions)
            assert "consensus_score" in consensus, "Missing consensus score"
            assert 0 <= consensus["consensus_score"] <= 1, "Invalid consensus score"

            self.test_results["shadow_logging"] = "PASSED ✅"
            logger.info("✅ Shadow logging test passed")

        except Exception as e:
            self.test_results["shadow_logging"] = f"FAILED ❌: {str(e)}"
            logger.error(f"❌ Shadow logging test failed: {e}")

    async def test_shadow_evaluation(self):
        """Test shadow evaluation with price data"""
        logger.info("\n📊 Testing Shadow Evaluation...")

        try:
            # Get a recent shadow to evaluate
            result = (
                self.supabase.client.table("shadow_variations")
                .select("*")
                .eq("would_take_trade", True)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

            if not result.data:
                logger.warning("No shadow trades to evaluate, creating mock data...")
                await self._create_mock_shadow_trade()

            # Run evaluation
            outcomes = await self.shadow_evaluator.evaluate_pending_shadows()

            logger.info(f"Evaluated {len(outcomes)} shadow trades")

            # Verify outcome structure
            if outcomes:
                outcome = outcomes[0]
                assert hasattr(outcome, "shadow_id"), "Missing shadow_id"
                assert hasattr(outcome, "outcome_status"), "Missing outcome_status"
                assert hasattr(outcome, "pnl_percentage"), "Missing pnl_percentage"
                assert outcome.outcome_status in [
                    "WIN",
                    "LOSS",
                    "TIMEOUT",
                    "PENDING",
                ], "Invalid outcome status"

            self.test_results["shadow_evaluation"] = "PASSED ✅"
            logger.info("✅ Shadow evaluation test passed")

        except Exception as e:
            self.test_results["shadow_evaluation"] = f"FAILED ❌: {str(e)}"
            logger.error(f"❌ Shadow evaluation test failed: {e}")

    async def test_performance_analysis(self):
        """Test performance analysis and recommendations"""
        logger.info("\n📈 Testing Performance Analysis...")

        try:
            # Analyze performance
            performance = await self.shadow_analyzer.analyze_performance()

            # Check structure
            assert "24h" in performance, "Missing 24h timeframe"

            # Get top performers
            top_performers = await self.shadow_analyzer.get_top_performers(
                "7d", top_n=3
            )
            logger.info(f"Found {len(top_performers)} top performers")

            # Generate recommendations
            recommendations = await self.shadow_analyzer.generate_recommendations()
            logger.info(f"Generated {len(recommendations)} recommendations")

            # Verify recommendation structure
            if recommendations:
                rec = recommendations[0]
                assert hasattr(rec, "strategy_name"), "Missing strategy_name"
                assert hasattr(rec, "parameter_name"), "Missing parameter_name"
                assert hasattr(rec, "confidence_level"), "Missing confidence_level"
                assert rec.confidence_level in [
                    "HIGH",
                    "MEDIUM",
                    "LOW",
                ], "Invalid confidence level"

            self.test_results["performance_analysis"] = "PASSED ✅"
            logger.info("✅ Performance analysis test passed")

        except Exception as e:
            self.test_results["performance_analysis"] = f"FAILED ❌: {str(e)}"
            logger.error(f"❌ Performance analysis test failed: {e}")

    async def test_threshold_management(self):
        """Test threshold adjustment with safety controls"""
        logger.info("\n⚙️ Testing Threshold Management...")

        try:
            # Create mock recommendation
            from src.analysis.shadow_analyzer import AdjustmentRecommendation

            mock_rec = AdjustmentRecommendation(
                strategy_name="DCA",
                parameter_name="confidence_threshold",
                current_value=0.60,
                recommended_value=0.58,
                variation_source="TEST_VARIATION",
                confidence_level="MEDIUM",
                evidence_trades=50,
                outperformance=0.05,
                p_value=0.04,
                reason="Test recommendation",
            )

            # Test safety checks (should pass)
            results = await self.threshold_manager.process_recommendations(
                [mock_rec], force=True
            )

            assert results, "No adjustment results returned"
            assert len(results) == 1, f"Expected 1 result, got {len(results)}"

            result = results[0]
            logger.info(f"Adjustment result: {result.success} - {result.reason}")

            # Test rollback conditions
            (
                should_rollback,
                reason,
            ) = await self.threshold_manager._check_rollback_conditions(0)
            logger.info(f"Rollback check: {should_rollback} - {reason}")

            self.test_results["threshold_management"] = "PASSED ✅"
            logger.info("✅ Threshold management test passed")

        except Exception as e:
            self.test_results["threshold_management"] = f"FAILED ❌: {str(e)}"
            logger.error(f"❌ Threshold management test failed: {e}")

    async def test_ml_integration(self):
        """Test ML retrainer with shadow data"""
        logger.info("\n🤖 Testing ML Integration...")

        try:
            # Check if we can retrain
            for strategy in ["DCA", "SWING", "CHANNEL"]:
                should_retrain, stats = self.retrainer.should_retrain(strategy)

                logger.info(f"{strategy} Strategy:")
                logger.info(f"  Real trades: {stats.get('real_trades', 0)}")
                logger.info(f"  Shadow trades: {stats.get('shadow_trades', 0)}")
                logger.info(
                    f"  Effective samples: {stats.get('effective_samples', 0):.1f}"
                )
                logger.info(f"  Can retrain: {should_retrain}")

                # Verify calculation
                if stats:
                    assert "real_trades" in stats, "Missing real_trades"
                    assert "shadow_trades" in stats, "Missing shadow_trades"
                    assert "effective_samples" in stats, "Missing effective_samples"
                    assert stats["effective_samples"] >= 0, "Invalid effective samples"

            self.test_results["ml_integration"] = "PASSED ✅"
            logger.info("✅ ML integration test passed")

        except Exception as e:
            self.test_results["ml_integration"] = f"FAILED ❌: {str(e)}"
            logger.error(f"❌ ML integration test failed: {e}")

    async def test_database_integrity(self):
        """Test database views and functions"""
        logger.info("\n🗄️ Testing Database Integrity...")

        try:
            # Test views
            views_to_test = [
                "champion_vs_challengers",
                "shadow_consensus",
                "ml_training_with_shadows",
                "adjustment_impact",
            ]

            for view_name in views_to_test:
                result = (
                    self.supabase.client.table(view_name).select("*").limit(1).execute()
                )
                logger.info(f"  View {view_name}: ✓")

            # Test functions
            result = self.supabase.client.rpc(
                "get_shadows_ready_for_evaluation"
            ).execute()
            logger.info(f"  Function get_shadows_ready_for_evaluation: ✓")

            # Test shadow weight calculation (if we have outcomes)
            outcome_result = (
                self.supabase.client.table("shadow_outcomes")
                .select("outcome_id")
                .limit(1)
                .execute()
            )

            if outcome_result.data:
                outcome_id = outcome_result.data[0]["outcome_id"]
                weight_result = self.supabase.client.rpc(
                    "calculate_shadow_weight", {"shadow_outcome_id": outcome_id}
                ).execute()
                logger.info(f"  Function calculate_shadow_weight: ✓")

            self.test_results["database_integrity"] = "PASSED ✅"
            logger.info("✅ Database integrity test passed")

        except Exception as e:
            self.test_results["database_integrity"] = f"FAILED ❌: {str(e)}"
            logger.error(f"❌ Database integrity test failed: {e}")

    async def _create_mock_scan(self) -> int:
        """Create a mock scan for testing"""
        scan_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": "BTC",
            "strategy_name": "DCA",
            "decision": "TEST",
            "reason": "test_scan",
            "features": json.dumps({"rsi": 45, "volume": 1000000}),
            "ml_confidence": 0.62,
            "ml_predictions": json.dumps({"take_profit_pct": 10, "stop_loss_pct": 5}),
            "market_regime": "NEUTRAL",
            "btc_price": 50000,
        }

        result = self.supabase.client.table("scan_history").insert(scan_data).execute()
        if result.data:
            return result.data[0]["scan_id"]
        return 0

    async def _create_mock_shadow_trade(self):
        """Create a mock shadow trade for testing"""
        # First create a scan
        scan_id = await self._create_mock_scan()

        # Create shadow variation
        shadow_data = {
            "scan_id": scan_id,
            "variation_name": "TEST_VARIATION",
            "variation_type": "scenario",
            "confidence_threshold": 0.60,
            "would_take_trade": True,
            "shadow_confidence": 0.65,
            "shadow_position_size": 100,
            "shadow_entry_price": 50000,
            "shadow_take_profit": 10,
            "shadow_stop_loss": 5,
            "shadow_hold_hours": 24,
        }

        self.supabase.client.table("shadow_variations").insert(shadow_data).execute()

    def print_test_summary(self):
        """Print test results summary"""
        logger.info("\n" + "=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)

        all_passed = True
        for test_name, result in self.test_results.items():
            logger.info(f"{test_name:.<30} {result}")
            if "FAILED" in result:
                all_passed = False

        logger.info("=" * 60)
        if all_passed:
            logger.info("🎉 ALL TESTS PASSED!")
        else:
            logger.warning("⚠️ SOME TESTS FAILED - Review logs above")
        logger.info("=" * 60)


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Test Shadow Testing System")
    parser.add_argument("--quick", action="store_true", help="Run quick tests only")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    tester = ShadowSystemTester()

    if args.quick:
        # Run only configuration and logging tests
        await tester.test_configuration()
        await tester.test_shadow_logging()
    else:
        # Run all tests
        await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
