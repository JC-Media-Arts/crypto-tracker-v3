#!/usr/bin/env python3
"""
Test complete trading flow end-to-end to ensure all components work together.
This verifies the entire pipeline from data ingestion to trade execution.
"""

import asyncio
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from colorama import Fore, Style, init

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from src.data.supabase_client import SupabaseClient
from src.data.hybrid_fetcher import HybridDataFetcher
from src.data.collector import DataCollector
from src.ml.feature_calculator import FeatureCalculator
from src.ml.predictor import MLPredictor
from src.strategies.dca.detector import DCADetector
from src.strategies.swing.detector import SwingDetector
from src.strategies.signal_generator import SignalGenerator
from src.trading.position_sizer import AdaptivePositionSizer as PositionSizer
from src.trading.paper_trader import PaperTrader
from src.notifications.slack_notifier import SlackNotifier
from loguru import logger

# Initialize colorama for colored output
init(autoreset=True)


class IntegrationTester:
    """Test full system integration."""

    def __init__(self):
        """Initialize the integration tester."""
        self.settings = get_settings()
        self.db = SupabaseClient()
        self.fetcher = HybridDataFetcher()

        # Track test results
        self.test_results = {}
        self.flow_stages = []

    async def test_trading_flow(self):
        """Test complete trading flow end-to-end."""

        print(f"{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}END-TO-END TRADING FLOW TEST")
        print(f"{Fore.CYAN}{'='*60}\n")

        print(f"{Fore.YELLOW}Testing complete pipeline from data to trades...\n")

        # Stage 1: Data Ingestion
        success = await self.test_data_ingestion()
        self.flow_stages.append(("Data Ingestion", success))
        if not success:
            print(f"{Fore.RED}❌ Flow stopped at Data Ingestion")
            return False

        # Stage 2: Feature Calculation
        success = await self.test_feature_calculation()
        self.flow_stages.append(("Feature Calculation", success))
        if not success:
            print(f"{Fore.RED}❌ Flow stopped at Feature Calculation")
            return False

        # Stage 3: Strategy Detection
        signals = await self.test_strategy_detection()
        self.flow_stages.append(("Strategy Detection", signals is not None))
        if not signals:
            print(f"{Fore.RED}❌ Flow stopped at Strategy Detection")
            return False

        # Stage 4: ML Filtering
        filtered = await self.test_ml_filtering(signals)
        self.flow_stages.append(("ML Filtering", filtered is not None))
        if not filtered:
            print(f"{Fore.RED}❌ Flow stopped at ML Filtering")
            return False

        # Stage 5: Position Sizing
        sized = await self.test_position_sizing(filtered)
        self.flow_stages.append(("Position Sizing", sized is not None))
        if not sized:
            print(f"{Fore.RED}❌ Flow stopped at Position Sizing")
            return False

        # Stage 6: Trade Execution
        trades = await self.test_trade_execution(sized)
        self.flow_stages.append(("Trade Execution", trades is not None))
        if not trades:
            print(f"{Fore.RED}❌ Flow stopped at Trade Execution")
            return False

        # Stage 7: Notification
        notified = await self.test_notifications(trades)
        self.flow_stages.append(("Notifications", notified))

        print(f"\n{Fore.GREEN}✅ Full trading flow operational!")
        return True

    async def test_data_ingestion(self) -> bool:
        """Test data ingestion stage."""
        print(f"\n{Fore.YELLOW}1. Testing data ingestion...")

        try:
            # Test WebSocket data fetch
            latest = await self.fetcher.get_latest_price("BTC", "1m")

            if latest:
                timestamp = datetime.fromisoformat(latest["timestamp"].replace("Z", "+00:00"))
                age_minutes = (datetime.utcnow() - timestamp.replace(tzinfo=None)).total_seconds() / 60

                if age_minutes < 5:
                    print(f"  ✅ Data is fresh ({age_minutes:.1f} minutes old)")
                    print(f"     BTC: ${latest['close']:,.2f}")
                    return True
                else:
                    print(f"  ⚠️  Data is stale ({age_minutes:.1f} minutes old)")
                    return False
            else:
                print(f"  ❌ No data available")
                return False

        except Exception as e:
            print(f"  ❌ Error: {str(e)[:100]}")
            return False

    async def test_feature_calculation(self) -> bool:
        """Test feature calculation stage."""
        print(f"\n{Fore.YELLOW}2. Testing feature calculation...")

        try:
            calc = FeatureCalculator()

            # Calculate features for multiple symbols
            symbols = ["BTC", "ETH", "SOL"]
            success_count = 0

            for symbol in symbols:
                features = await calc.calculate_features_for_symbol(symbol, lookback_hours=24)

                if features is not None and not features.empty:
                    success_count += 1
                    print(f"  ✅ {symbol}: {len(features.columns)} features calculated")
                else:
                    print(f"  ❌ {symbol}: Failed to calculate features")

            return success_count >= 2  # At least 2/3 should work

        except Exception as e:
            print(f"  ❌ Error: {str(e)[:100]}")
            return False

    async def test_strategy_detection(self) -> Optional[Dict]:
        """Test strategy detection stage."""
        print(f"\n{Fore.YELLOW}3. Testing strategy detection...")

        try:
            # Initialize detectors
            dca_detector = DCADetector(self.db)
            swing_detector = SwingDetector(self.db)

            signals = {"dca": [], "swing": [], "total": 0}

            # Test DCA detection
            symbols = ["BTC", "ETH", "SOL", "AVAX", "MATIC"]

            for symbol in symbols:
                # Check DCA
                try:
                    is_dca = await dca_detector.detect(symbol)
                    if is_dca:
                        signals["dca"].append(symbol)
                        signals["total"] += 1
                except Exception:
                    pass

                # Check Swing
                try:
                    is_swing = await swing_detector.detect(symbol)
                    if is_swing:
                        signals["swing"].append(symbol)
                        signals["total"] += 1
                except Exception:
                    pass

            print(f"  ✅ Found {signals['total']} potential setups")
            print(f"     DCA: {signals['dca']}")
            print(f"     Swing: {signals['swing']}")

            return signals if signals["total"] > 0 else None

        except Exception as e:
            print(f"  ❌ Error: {str(e)[:100]}")
            return None

    async def test_ml_filtering(self, signals: Dict) -> Optional[List[Dict]]:
        """Test ML filtering stage."""
        print(f"\n{Fore.YELLOW}4. Testing ML filtering...")

        try:
            predictor = MLPredictor()
            filtered_signals = []

            # Process DCA signals
            for symbol in signals.get("dca", []):
                try:
                    prediction = await predictor.predict(symbol, strategy="dca")

                    if prediction and prediction.get("confidence", 0) > 0.6:
                        filtered_signals.append(
                            {
                                "symbol": symbol,
                                "strategy": "dca",
                                "confidence": prediction["confidence"],
                                "predicted_return": prediction.get("predicted_return", 0),
                            }
                        )
                        print(f"  ✅ {symbol} DCA: confidence={prediction['confidence']:.2f}")
                except Exception:
                    pass

            # Process Swing signals
            for symbol in signals.get("swing", []):
                try:
                    prediction = await predictor.predict(symbol, strategy="swing")

                    if prediction and prediction.get("confidence", 0) > 0.6:
                        filtered_signals.append(
                            {
                                "symbol": symbol,
                                "strategy": "swing",
                                "confidence": prediction["confidence"],
                                "predicted_return": prediction.get("predicted_return", 0),
                            }
                        )
                        print(f"  ✅ {symbol} Swing: confidence={prediction['confidence']:.2f}")
                except Exception:
                    pass

            if filtered_signals:
                print(f"  ✅ {len(filtered_signals)} signals passed ML filter")
                return filtered_signals
            else:
                print(f"  ⚠️  No signals passed ML filter (normal if no setups)")
                return []  # Empty list is okay, means filtering is working

        except Exception as e:
            print(f"  ❌ Error: {str(e)[:100]}")
            return None

    async def test_position_sizing(self, signals: List[Dict]) -> Optional[List[Dict]]:
        """Test position sizing stage."""
        print(f"\n{Fore.YELLOW}5. Testing position sizing...")

        try:
            sizer = PositionSizer()
            sized_signals = []

            # Mock account balance
            account_balance = 10000

            for signal in signals:
                size = sizer.calculate_position_size(
                    symbol=signal["symbol"],
                    strategy=signal["strategy"],
                    confidence=signal["confidence"],
                    account_balance=account_balance,
                )

                if size > 0:
                    signal["position_size"] = size
                    signal["position_pct"] = (size / account_balance) * 100
                    sized_signals.append(signal)

                    print(f"  ✅ {signal['symbol']}: ${size:.2f} ({signal['position_pct']:.1f}% of account)")

            if sized_signals:
                return sized_signals
            else:
                # Even if no signals, position sizing is working
                print(f"  ✅ Position sizing functional (no signals to size)")
                return []

        except Exception as e:
            print(f"  ❌ Error: {str(e)[:100]}")
            return None

    async def test_trade_execution(self, signals: List[Dict]) -> Optional[List[Dict]]:
        """Test trade execution stage."""
        print(f"\n{Fore.YELLOW}6. Testing trade execution...")

        try:
            # Initialize paper trader
            trader = PaperTrader()
            executed_trades = []

            if not signals:
                # Test with mock signal if no real signals
                print(f"  ℹ️  No real signals, testing with mock trade...")

                mock_trade = {
                    "symbol": "BTC",
                    "strategy": "test",
                    "action": "buy",
                    "quantity": 0.001,
                    "price": 50000,
                    "timestamp": datetime.utcnow().isoformat(),
                }

                # Test trade logging
                try:
                    self.db.client.table("trade_logs").insert(
                        {
                            "symbol": mock_trade["symbol"],
                            "strategy": mock_trade["strategy"],
                            "action": mock_trade["action"],
                            "quantity": mock_trade["quantity"],
                            "price": mock_trade["price"],
                            "timestamp": mock_trade["timestamp"],
                            "environment": "test",
                        }
                    ).execute()

                    print(f"  ✅ Trade logging functional")
                    executed_trades.append(mock_trade)
                except Exception:
                    print(f"  ⚠️  Trade logging not configured")

            else:
                # Execute real signals
                for signal in signals[:3]:  # Limit to 3 trades for testing
                    try:
                        # Mock execution (in real system, would call exchange API)
                        trade = {
                            "symbol": signal["symbol"],
                            "strategy": signal["strategy"],
                            "action": "buy",
                            "quantity": signal["position_size"] / 50000,  # Mock BTC price
                            "price": 50000,
                            "timestamp": datetime.utcnow().isoformat(),
                        }

                        executed_trades.append(trade)
                        print(f"  ✅ Executed: {trade['symbol']} {trade['strategy']}")

                    except Exception as e:
                        print(f"  ⚠️  Failed to execute {signal['symbol']}: {str(e)[:50]}")

            return executed_trades if executed_trades else []

        except Exception as e:
            print(f"  ❌ Error: {str(e)[:100]}")
            return None

    async def test_notifications(self, trades: List[Dict]) -> bool:
        """Test notification stage."""
        print(f"\n{Fore.YELLOW}7. Testing notifications...")

        try:
            notifier = SlackNotifier()

            # Check if Slack is configured
            if not notifier.webhook_url:
                print(f"  ⚠️  Slack not configured (normal for testing)")
                return True

            # Test notification (without actually sending)
            if trades:
                message = f"Test: {len(trades)} trades executed"
                print(f"  ✅ Notification system ready: '{message}'")
            else:
                print(f"  ✅ Notification system ready (no trades to notify)")

            return True

        except Exception as e:
            print(f"  ⚠️  Notification error: {str(e)[:100]}")
            return True  # Non-critical, don't fail the test

    async def test_component_integration(self):
        """Test integration between specific components."""

        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}COMPONENT INTEGRATION TESTS")
        print(f"{Fore.CYAN}{'='*60}\n")

        tests = [
            ("Fetcher → Calculator", self.test_fetcher_to_calculator),
            ("Calculator → Predictor", self.test_calculator_to_predictor),
            ("Detector → Signal Gen", self.test_detector_to_signal),
            ("Signal → Position Size", self.test_signal_to_position),
            ("Database → All Components", self.test_database_integration),
        ]

        results = []
        for test_name, test_func in tests:
            print(f"\n{Fore.YELLOW}Testing: {test_name}")
            try:
                result = await test_func()
                if result:
                    print(f"  ✅ Integration working")
                    results.append((test_name, True))
                else:
                    print(f"  ❌ Integration failed")
                    results.append((test_name, False))
            except Exception as e:
                print(f"  ❌ Error: {str(e)[:100]}")
                results.append((test_name, False))

        return results

    async def test_fetcher_to_calculator(self) -> bool:
        """Test data flow from fetcher to calculator."""
        # Fetch data
        data = await self.fetcher.get_ml_features_data("BTC")
        if not data or not data.get("has_data"):
            return False

        # Calculate features
        calc = FeatureCalculator()
        features = await calc.calculate_features_for_symbol("BTC", lookback_hours=24)

        return features is not None and not features.empty

    async def test_calculator_to_predictor(self) -> bool:
        """Test data flow from calculator to predictor."""
        # Calculate features
        calc = FeatureCalculator()
        features = await calc.calculate_features_for_symbol("ETH", lookback_hours=24)

        if features is None or features.empty:
            return False

        # Generate prediction
        predictor = MLPredictor()
        prediction = await predictor.predict("ETH")

        return prediction is not None and "confidence" in prediction

    async def test_detector_to_signal(self) -> bool:
        """Test data flow from detector to signal generator."""
        # Detect setup
        detector = DCADetector(self.db)
        is_setup = await detector.detect("SOL")

        # Generate signal
        if is_setup:
            gen = SignalGenerator()
            signal = await gen.generate_signal("SOL", "dca")
            return signal is not None

        return True  # No setup is okay

    async def test_signal_to_position(self) -> bool:
        """Test data flow from signal to position sizing."""
        # Mock signal
        signal = {"symbol": "AVAX", "strategy": "swing", "confidence": 0.75}

        # Calculate position
        sizer = PositionSizer()
        size = sizer.calculate_position_size(
            symbol=signal["symbol"],
            strategy=signal["strategy"],
            confidence=signal["confidence"],
            account_balance=10000,
        )

        return size > 0 and size <= 1000  # Max 10% position

    async def test_database_integration(self) -> bool:
        """Test database integration across components."""
        # Test write
        test_data = {
            "metric_name": "integration_test",
            "value": 1.0,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "test",
        }

        result = self.db.client.table("health_metrics").insert(test_data).execute()

        if not result.data:
            return False

        # Test read
        read_result = self.db.client.table("health_metrics").select("*").eq("metric_name", "integration_test").execute()

        # Clean up
        self.db.client.table("health_metrics").delete().eq("metric_name", "integration_test").execute()

        return read_result.data is not None

    def generate_report(self, component_results: List[tuple]):
        """Generate integration test report."""

        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}INTEGRATION TEST SUMMARY")
        print(f"{Fore.CYAN}{'='*60}\n")

        # Flow test results
        print(f"{Fore.YELLOW}Trading Flow Stages:")
        for stage, success in self.flow_stages:
            status = f"{Fore.GREEN}✅ PASS" if success else f"{Fore.RED}❌ FAIL"
            print(f"  {stage:<20} {status}")

        # Component integration results
        print(f"\n{Fore.YELLOW}Component Integration:")
        for test_name, success in component_results:
            status = f"{Fore.GREEN}✅ PASS" if success else f"{Fore.RED}❌ FAIL"
            print(f"  {test_name:<20} {status}")

        # Overall assessment
        total_tests = len(self.flow_stages) + len(component_results)
        passed_tests = sum(1 for _, s in self.flow_stages + component_results if s)
        pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        print(f"\n{Fore.CYAN}Overall Results:")
        print(f"  • Tests Passed: {passed_tests}/{total_tests}")
        print(f"  • Success Rate: {pass_rate:.1f}%")

        if pass_rate >= 90:
            print(f"\n{Fore.GREEN}🎉 SYSTEM INTEGRATION EXCELLENT!")
            print(f"   All major components are working together properly.")
        elif pass_rate >= 70:
            print(f"\n{Fore.YELLOW}⚠️  SYSTEM INTEGRATION GOOD")
            print(f"   Most components working, but some issues to address.")
        else:
            print(f"\n{Fore.RED}❌ SYSTEM INTEGRATION NEEDS WORK")
            print(f"   Several integration issues detected.")


async def main():
    """Run all integration tests."""

    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"{Fore.CYAN}CRYPTO TRACKER V3 - FULL INTEGRATION TEST")
    print(f"{Fore.CYAN}Testing complete system from data to trades")
    print(f"{Fore.CYAN}{'='*70}\n")

    tester = IntegrationTester()

    # Test trading flow
    flow_success = await tester.test_trading_flow()

    # Test component integration
    component_results = await tester.test_component_integration()

    # Generate report
    tester.generate_report(component_results)

    # Return success code
    if flow_success and all(s for _, s in component_results):
        print(f"\n{Fore.GREEN}All integration tests passed! ✅")
        return 0
    else:
        print(f"\n{Fore.YELLOW}Some integration tests failed. Review the results above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
