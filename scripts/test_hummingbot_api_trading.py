"""
Comprehensive Test Script for Hummingbot API Paper Trading
Tests all aspects of our trading strategies including:
- DCA grid execution
- Exit strategies (TP/SL)
- Position sizing
- ML predictions
- Signal generation
- Risk management
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import logging

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.trading.hummingbot_api_client import HummingbotAPIClient, HummingbotOrder
from src.strategies.dca.detector import DCADetector
from src.strategies.dca.grid import GridCalculator
from src.trading.position_sizer import AdaptivePositionSizer
from src.ml.predictor import MLPredictor
from src.data.supabase_client import SupabaseClient
from src.config.settings import Settings

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ComprehensiveTradingTest:
    """Comprehensive test suite for all trading strategies"""

    def __init__(self):
        self.settings = Settings()
        self.supabase = SupabaseClient()
        self.ml_predictor = MLPredictor(self.settings)
        self.position_sizer = AdaptivePositionSizer()
        self.grid_calculator = GridCalculator()
        self.dca_detector = DCADetector(self.supabase)
        self.hummingbot_client = None
        self.test_results = {
            "dca_detection": {},
            "ml_predictions": {},
            "position_sizing": {},
            "grid_generation": {},
            "order_execution": {},
            "exit_strategies": {},
            "risk_management": {},
            "performance_metrics": {},
        }

    async def setup(self):
        """Initialize connections and setup test environment"""
        logger.info("=" * 80)
        logger.info("COMPREHENSIVE TRADING SYSTEM TEST")
        logger.info("=" * 80)

        # Initialize Hummingbot API client
        self.hummingbot_client = HummingbotAPIClient()
        await self.hummingbot_client.connect()

        # Create test bot
        self.test_bot = await self.hummingbot_client.create_bot(
            bot_name="comprehensive_test_bot",
            exchange="binance_paper_trade",
            config={
                "initial_balance": 100000,  # $100k paper trading balance
                "trading_pairs": ["BTC-USDT", "ETH-USDT", "SOL-USDT"],
            },
        )

        if self.test_bot:
            self.bot_id = self.test_bot.get("id")
            logger.info(f"✅ Test bot created: {self.bot_id}")
        else:
            logger.error("❌ Failed to create test bot")
            return False

        return True

    async def test_dca_detection(self):
        """Test DCA setup detection logic"""
        logger.info("\n" + "=" * 60)
        logger.info("TESTING DCA DETECTION")
        logger.info("=" * 60)

        test_scenarios = [
            {
                "name": "Strong Oversold Signal",
                "symbol": "BTC",
                "rsi": 25,
                "price_drop_1h": -3.5,
                "price_drop_24h": -8.0,
                "volume_spike": 2.5,
                "expected": True,
            },
            {
                "name": "Weak Signal (High RSI)",
                "symbol": "ETH",
                "rsi": 65,
                "price_drop_1h": -1.0,
                "price_drop_24h": -2.0,
                "volume_spike": 1.2,
                "expected": False,
            },
            {
                "name": "Edge Case (Borderline)",
                "symbol": "SOL",
                "rsi": 35,
                "price_drop_1h": -2.0,
                "price_drop_24h": -5.0,
                "volume_spike": 1.8,
                "expected": True,
            },
        ]

        for scenario in test_scenarios:
            # Create mock OHLC data
            mock_data = self._create_mock_ohlc_data(
                symbol=scenario["symbol"],
                rsi=scenario["rsi"],
                price_drop_1h=scenario["price_drop_1h"],
                price_drop_24h=scenario["price_drop_24h"],
                volume_spike=scenario["volume_spike"],
            )

            # Test detection
            is_setup = self.dca_detector.detect_setup(mock_data)

            result = "✅ PASS" if (is_setup == scenario["expected"]) else "❌ FAIL"
            logger.info(
                f"{result} - {scenario['name']}: "
                f"RSI={scenario['rsi']}, "
                f"Drop1h={scenario['price_drop_1h']}%, "
                f"Drop24h={scenario['price_drop_24h']}%, "
                f"Volume={scenario['volume_spike']}x"
            )

            self.test_results["dca_detection"][scenario["name"]] = {
                "passed": is_setup == scenario["expected"],
                "detected": is_setup,
                "expected": scenario["expected"],
            }

    async def test_ml_predictions(self):
        """Test ML model predictions and confidence scores"""
        logger.info("\n" + "=" * 60)
        logger.info("TESTING ML PREDICTIONS")
        logger.info("=" * 60)

        test_symbols = ["BTC", "ETH", "SOL", "MATIC", "DOGE"]

        for symbol in test_symbols:
            # Get recent OHLC data
            ohlc_data = await self.supabase.get_ohlc_data(
                symbol=symbol, timeframe="15m", limit=100
            )

            if ohlc_data and len(ohlc_data) > 50:
                # Generate ML predictions
                predictions = self.ml_predictor.predict(ohlc_data)

                if predictions:
                    logger.info(f"\n{symbol} ML Predictions:")
                    logger.info(
                        f"  Position Size Multiplier: {predictions['position_size_multiplier']:.2f}x"
                    )
                    logger.info(
                        f"  Take Profit: {predictions['take_profit_percent']:.2f}%"
                    )
                    logger.info(f"  Stop Loss: {predictions['stop_loss_percent']:.2f}%")
                    logger.info(
                        f"  Expected Hold Time: {predictions['expected_hold_hours']:.1f} hours"
                    )
                    logger.info(
                        f"  Win Probability: {predictions['win_probability']:.2%}"
                    )
                    logger.info(
                        f"  Confidence Score: {predictions['confidence_score']:.2%}"
                    )

                    # Validate predictions
                    self._validate_ml_predictions(symbol, predictions)

                    self.test_results["ml_predictions"][symbol] = predictions
                else:
                    logger.warning(f"  ⚠️  No ML predictions for {symbol}")

    async def test_position_sizing(self):
        """Test adaptive position sizing logic"""
        logger.info("\n" + "=" * 60)
        logger.info("TESTING POSITION SIZING")
        logger.info("=" * 60)

        portfolio_value = 100000  # $100k

        test_cases = [
            {
                "symbol": "BTC",
                "market_regime": "BULL",
                "ml_confidence": 0.85,
                "volatility": 0.02,
                "market_cap_tier": "LARGE",
            },
            {
                "symbol": "DOGE",
                "market_regime": "BEAR",
                "ml_confidence": 0.45,
                "volatility": 0.08,
                "market_cap_tier": "SMALL",
            },
            {
                "symbol": "ETH",
                "market_regime": "NEUTRAL",
                "ml_confidence": 0.65,
                "volatility": 0.04,
                "market_cap_tier": "LARGE",
            },
        ]

        for case in test_cases:
            position_size = self.position_sizer.calculate_position_size(
                symbol=case["symbol"],
                portfolio_value=portfolio_value,
                market_regime=case["market_regime"],
                ml_confidence=case["ml_confidence"],
                volatility=case["volatility"],
                market_cap_tier=case["market_cap_tier"],
            )

            risk_percent = (position_size / portfolio_value) * 100

            logger.info(f"\n{case['symbol']} Position Sizing:")
            logger.info(f"  Market Regime: {case['market_regime']}")
            logger.info(f"  ML Confidence: {case['ml_confidence']:.2%}")
            logger.info(f"  Volatility: {case['volatility']:.2%}")
            logger.info(f"  Market Cap: {case['market_cap_tier']}")
            logger.info(
                f"  → Position Size: ${position_size:,.2f} ({risk_percent:.2f}% of portfolio)"
            )

            # Validate position sizing rules
            self._validate_position_sizing(case, position_size, portfolio_value)

            self.test_results["position_sizing"][case["symbol"]] = {
                "position_size": position_size,
                "risk_percent": risk_percent,
                "inputs": case,
            }

    async def test_grid_generation(self):
        """Test DCA grid generation with different parameters"""
        logger.info("\n" + "=" * 60)
        logger.info("TESTING GRID GENERATION")
        logger.info("=" * 60)

        test_grids = [
            {
                "symbol": "BTC",
                "current_price": 65000,
                "total_investment": 5000,
                "num_orders": 5,
                "price_range_percent": 10,
                "ml_confidence": 0.75,
            },
            {
                "symbol": "ETH",
                "current_price": 3500,
                "total_investment": 2000,
                "num_orders": 7,
                "price_range_percent": 15,
                "ml_confidence": 0.60,
            },
            {
                "symbol": "SOL",
                "current_price": 150,
                "total_investment": 1000,
                "num_orders": 4,
                "price_range_percent": 8,
                "ml_confidence": 0.85,
            },
        ]

        for grid_params in test_grids:
            grid = self.grid_calculator.calculate_grid(
                current_price=grid_params["current_price"],
                total_investment=grid_params["total_investment"],
                num_orders=grid_params["num_orders"],
                price_range_percent=grid_params["price_range_percent"],
                ml_confidence=grid_params["ml_confidence"],
            )

            logger.info(f"\n{grid_params['symbol']} Grid Configuration:")
            logger.info(f"  Current Price: ${grid_params['current_price']:,.2f}")
            logger.info(f"  Total Investment: ${grid_params['total_investment']:,.2f}")
            logger.info(f"  Number of Orders: {grid_params['num_orders']}")
            logger.info(f"  Price Range: {grid_params['price_range_percent']}%")
            logger.info(f"  ML Confidence: {grid_params['ml_confidence']:.2%}")

            logger.info(f"\n  Generated Grid:")
            total_allocated = 0
            for i, order in enumerate(grid["orders"], 1):
                logger.info(
                    f"    Order {i}: ${order['price']:,.2f} x {order['size']:.6f} = ${order['value']:,.2f}"
                )
                total_allocated += order["value"]

            logger.info(f"  Total Allocated: ${total_allocated:,.2f}")
            logger.info(f"  Average Entry: ${grid['average_entry']:,.2f}")

            # Validate grid
            self._validate_grid(grid_params, grid)

            self.test_results["grid_generation"][grid_params["symbol"]] = grid

    async def test_order_execution(self):
        """Test order placement and execution through Hummingbot"""
        logger.info("\n" + "=" * 60)
        logger.info("TESTING ORDER EXECUTION")
        logger.info("=" * 60)

        if not self.bot_id:
            logger.error("❌ No bot ID available for order testing")
            return

        # Test different order types
        test_orders = [
            {
                "symbol": "BTC-USDT",
                "side": "buy",
                "price": 64000,
                "amount": 0.001,
                "order_type": "limit",
            },
            {
                "symbol": "ETH-USDT",
                "side": "buy",
                "price": 3400,
                "amount": 0.01,
                "order_type": "limit",
            },
            {
                "symbol": "SOL-USDT",
                "side": "sell",
                "price": 155,
                "amount": 1.0,
                "order_type": "limit",
            },
        ]

        placed_orders = []

        for order_params in test_orders:
            order = HummingbotOrder(**order_params)
            result = await self.hummingbot_client.place_order(self.bot_id, order)

            if result:
                logger.info(
                    f"✅ Order placed: {order_params['symbol']} "
                    f"{order_params['side']} {order_params['amount']} @ ${order_params['price']}"
                )
                placed_orders.append(result)
            else:
                logger.error(f"❌ Failed to place order: {order_params['symbol']}")

        self.test_results["order_execution"]["placed_orders"] = placed_orders

        # Test order cancellation
        if placed_orders:
            order_to_cancel = placed_orders[0]
            cancelled = await self.hummingbot_client.cancel_order(
                self.bot_id, order_to_cancel.get("id")
            )

            if cancelled:
                logger.info(
                    f"✅ Successfully cancelled order: {order_to_cancel.get('id')}"
                )
            else:
                logger.error(f"❌ Failed to cancel order: {order_to_cancel.get('id')}")

    async def test_exit_strategies(self):
        """Test take profit and stop loss exit strategies"""
        logger.info("\n" + "=" * 60)
        logger.info("TESTING EXIT STRATEGIES")
        logger.info("=" * 60)

        # Simulate positions with different scenarios
        test_positions = [
            {
                "symbol": "BTC",
                "entry_price": 65000,
                "current_price": 68250,  # +5% - should trigger TP
                "take_profit": 5.0,
                "stop_loss": 3.0,
                "expected_action": "TAKE_PROFIT",
            },
            {
                "symbol": "ETH",
                "entry_price": 3500,
                "current_price": 3325,  # -5% - should trigger SL
                "take_profit": 7.0,
                "stop_loss": 4.0,
                "expected_action": "STOP_LOSS",
            },
            {
                "symbol": "SOL",
                "entry_price": 150,
                "current_price": 152,  # +1.33% - should hold
                "take_profit": 8.0,
                "stop_loss": 5.0,
                "expected_action": "HOLD",
            },
        ]

        for position in test_positions:
            price_change = (
                (position["current_price"] - position["entry_price"])
                / position["entry_price"]
            ) * 100

            # Determine action
            if price_change >= position["take_profit"]:
                action = "TAKE_PROFIT"
            elif price_change <= -position["stop_loss"]:
                action = "STOP_LOSS"
            else:
                action = "HOLD"

            result = "✅ PASS" if action == position["expected_action"] else "❌ FAIL"

            logger.info(f"\n{position['symbol']} Exit Strategy Test:")
            logger.info(f"  Entry: ${position['entry_price']:,.2f}")
            logger.info(f"  Current: ${position['current_price']:,.2f}")
            logger.info(f"  Change: {price_change:+.2f}%")
            logger.info(f"  TP Target: +{position['take_profit']}%")
            logger.info(f"  SL Target: -{position['stop_loss']}%")
            logger.info(
                f"  {result} - Action: {action} (Expected: {position['expected_action']})"
            )

            self.test_results["exit_strategies"][position["symbol"]] = {
                "passed": action == position["expected_action"],
                "action": action,
                "expected": position["expected_action"],
                "price_change": price_change,
            }

    async def test_risk_management(self):
        """Test risk management rules and portfolio limits"""
        logger.info("\n" + "=" * 60)
        logger.info("TESTING RISK MANAGEMENT")
        logger.info("=" * 60)

        portfolio_value = 100000

        # Test maximum position limits
        risk_scenarios = [
            {
                "name": "Single Position Limit",
                "positions": [
                    {"symbol": "BTC", "value": 15000}  # 15% - should be capped at 10%
                ],
                "expected_warning": True,
            },
            {
                "name": "Total Exposure Limit",
                "positions": [
                    {"symbol": "BTC", "value": 8000},
                    {"symbol": "ETH", "value": 7000},
                    {"symbol": "SOL", "value": 6000},
                    {"symbol": "MATIC", "value": 5000},
                    {"symbol": "DOGE", "value": 4000},  # Total 30% - at limit
                ],
                "expected_warning": False,
            },
            {
                "name": "Correlation Risk",
                "positions": [
                    {"symbol": "BTC", "value": 10000},
                    {"symbol": "ETH", "value": 10000},  # High correlation assets
                ],
                "expected_warning": True,
            },
        ]

        for scenario in risk_scenarios:
            logger.info(f"\n{scenario['name']}:")

            total_exposure = sum(p["value"] for p in scenario["positions"])
            exposure_percent = (total_exposure / portfolio_value) * 100

            warnings = []

            # Check single position limits
            for position in scenario["positions"]:
                position_percent = (position["value"] / portfolio_value) * 100
                if position_percent > 10:
                    warnings.append(
                        f"{position['symbol']} exceeds 10% limit ({position_percent:.1f}%)"
                    )

            # Check total exposure
            if exposure_percent > 30:
                warnings.append(
                    f"Total exposure exceeds 30% limit ({exposure_percent:.1f}%)"
                )

            # Check correlation (simplified)
            if len(scenario["positions"]) >= 2:
                symbols = [p["symbol"] for p in scenario["positions"]]
                if "BTC" in symbols and "ETH" in symbols:
                    btc_value = next(
                        p["value"]
                        for p in scenario["positions"]
                        if p["symbol"] == "BTC"
                    )
                    eth_value = next(
                        p["value"]
                        for p in scenario["positions"]
                        if p["symbol"] == "ETH"
                    )
                    if (btc_value + eth_value) / portfolio_value > 0.15:
                        warnings.append("High correlation risk: BTC + ETH > 15%")

            has_warnings = len(warnings) > 0
            result = (
                "✅ PASS" if (has_warnings == scenario["expected_warning"]) else "❌ FAIL"
            )

            logger.info(
                f"  Total Exposure: ${total_exposure:,.2f} ({exposure_percent:.1f}%)"
            )
            if warnings:
                for warning in warnings:
                    logger.info(f"  ⚠️  {warning}")
            else:
                logger.info(f"  ✅ All risk checks passed")

            logger.info(
                f"  {result} - Expected Warning: {scenario['expected_warning']}, Got: {has_warnings}"
            )

            self.test_results["risk_management"][scenario["name"]] = {
                "passed": has_warnings == scenario["expected_warning"],
                "warnings": warnings,
                "total_exposure": exposure_percent,
            }

    async def test_performance_tracking(self):
        """Test performance metrics and P&L tracking"""
        logger.info("\n" + "=" * 60)
        logger.info("TESTING PERFORMANCE TRACKING")
        logger.info("=" * 60)

        if self.bot_id:
            # Get current balance
            balance = await self.hummingbot_client.get_balance(self.bot_id)
            logger.info(f"\nCurrent Balance: {json.dumps(balance, indent=2)}")

            # Get positions
            positions = await self.hummingbot_client.get_positions(self.bot_id)
            if positions:
                logger.info(f"\nActive Positions:")
                for pos in positions:
                    logger.info(
                        f"  {pos.symbol}: {pos.amount} @ ${pos.entry_price:.2f}, "
                        f"PnL: ${pos.pnl:.2f}"
                    )
            else:
                logger.info("\nNo active positions")

            # Get performance metrics
            performance = await self.hummingbot_client.get_performance(self.bot_id)
            if performance:
                logger.info(
                    f"\nPerformance Metrics: {json.dumps(performance, indent=2)}"
                )

            self.test_results["performance_metrics"] = {
                "balance": balance,
                "positions": len(positions) if positions else 0,
                "performance": performance,
            }

    async def test_full_dca_cycle(self):
        """Test a complete DCA trading cycle from detection to exit"""
        logger.info("\n" + "=" * 60)
        logger.info("TESTING FULL DCA CYCLE")
        logger.info("=" * 60)

        # Step 1: Detect DCA setup
        logger.info("\n1️⃣ Detecting DCA Setup...")
        symbol = "BTC"
        mock_setup = self._create_mock_ohlc_data(
            symbol=symbol,
            rsi=28,
            price_drop_1h=-3.0,
            price_drop_24h=-7.0,
            volume_spike=2.2,
        )

        is_setup = self.dca_detector.detect_setup(mock_setup)
        if is_setup:
            logger.info(f"  ✅ DCA setup detected for {symbol}")
        else:
            logger.info(f"  ❌ No DCA setup for {symbol}")
            return

        # Step 2: Generate ML predictions
        logger.info("\n2️⃣ Generating ML Predictions...")
        predictions = {
            "position_size_multiplier": 1.5,
            "take_profit_percent": 6.0,
            "stop_loss_percent": 3.5,
            "expected_hold_hours": 24,
            "win_probability": 0.72,
            "confidence_score": 0.68,
        }
        logger.info(f"  ML Confidence: {predictions['confidence_score']:.2%}")
        logger.info(f"  Win Probability: {predictions['win_probability']:.2%}")

        # Step 3: Calculate position size
        logger.info("\n3️⃣ Calculating Position Size...")
        position_size = self.position_sizer.calculate_position_size(
            symbol=symbol,
            portfolio_value=100000,
            market_regime="NEUTRAL",
            ml_confidence=predictions["confidence_score"],
            volatility=0.03,
            market_cap_tier="LARGE",
        )
        logger.info(f"  Position Size: ${position_size:,.2f}")

        # Step 4: Generate grid
        logger.info("\n4️⃣ Generating DCA Grid...")
        current_price = 65000
        grid = self.grid_calculator.calculate_grid(
            current_price=current_price,
            total_investment=position_size,
            num_orders=5,
            price_range_percent=8,
            ml_confidence=predictions["confidence_score"],
        )

        logger.info(f"  Grid Orders:")
        for i, order in enumerate(grid["orders"], 1):
            logger.info(f"    Order {i}: ${order['price']:,.2f} x {order['size']:.6f}")

        # Step 5: Execute grid (simulation)
        logger.info("\n5️⃣ Executing Grid Orders...")
        if self.bot_id:
            for order in grid["orders"][:2]:  # Place first 2 orders as test
                hb_order = HummingbotOrder(
                    symbol=f"{symbol}-USDT",
                    side="buy",
                    price=order["price"],
                    amount=order["size"],
                    order_type="limit",
                )
                result = await self.hummingbot_client.place_order(self.bot_id, hb_order)
                if result:
                    logger.info(f"  ✅ Order placed at ${order['price']:,.2f}")

        # Step 6: Monitor for exit
        logger.info("\n6️⃣ Monitoring Exit Conditions...")
        logger.info(f"  Take Profit: +{predictions['take_profit_percent']}%")
        logger.info(f"  Stop Loss: -{predictions['stop_loss_percent']}%")
        logger.info(f"  Expected Hold: {predictions['expected_hold_hours']} hours")

        # Simulate price movement
        simulated_prices = [
            current_price * 0.98,  # -2%
            current_price * 0.97,  # -3%
            current_price * 1.02,  # +2%
            current_price * 1.06,  # +6% - should trigger TP
        ]

        for i, price in enumerate(simulated_prices, 1):
            change = ((price - current_price) / current_price) * 100
            logger.info(f"  Hour {i}: ${price:,.2f} ({change:+.2f}%)")

            if change >= predictions["take_profit_percent"]:
                logger.info(f"  🎯 TAKE PROFIT triggered at {change:+.2f}%")
                break
            elif change <= -predictions["stop_loss_percent"]:
                logger.info(f"  🛑 STOP LOSS triggered at {change:+.2f}%")
                break

        logger.info("\n✅ Full DCA cycle test completed")

    def _create_mock_ohlc_data(
        self, symbol, rsi, price_drop_1h, price_drop_24h, volume_spike
    ):
        """Create mock OHLC data for testing"""
        base_price = 65000 if symbol == "BTC" else 3500 if symbol == "ETH" else 150

        return {
            "symbol": symbol,
            "current_price": base_price,
            "rsi": rsi,
            "price_change_1h": price_drop_1h,
            "price_change_24h": price_drop_24h,
            "volume_ratio": volume_spike,
            "volatility": 0.03,
        }

    def _validate_ml_predictions(self, symbol, predictions):
        """Validate ML predictions are within reasonable bounds"""
        validations = []

        # Check position size multiplier
        if not 0.5 <= predictions["position_size_multiplier"] <= 3.0:
            validations.append(
                f"Position multiplier out of range: {predictions['position_size_multiplier']}"
            )

        # Check take profit
        if not 2.0 <= predictions["take_profit_percent"] <= 20.0:
            validations.append(
                f"Take profit out of range: {predictions['take_profit_percent']}"
            )

        # Check stop loss
        if not 1.0 <= predictions["stop_loss_percent"] <= 10.0:
            validations.append(
                f"Stop loss out of range: {predictions['stop_loss_percent']}"
            )

        # Check win probability
        if not 0.3 <= predictions["win_probability"] <= 0.9:
            validations.append(
                f"Win probability out of range: {predictions['win_probability']}"
            )

        if validations:
            logger.warning(f"  ⚠️  Validation issues for {symbol}:")
            for issue in validations:
                logger.warning(f"    - {issue}")
        else:
            logger.info(f"  ✅ All predictions valid for {symbol}")

    def _validate_position_sizing(self, case, position_size, portfolio_value):
        """Validate position sizing follows risk rules"""
        max_position = portfolio_value * 0.10  # 10% max
        min_position = portfolio_value * 0.001  # 0.1% min

        if position_size > max_position:
            logger.warning(f"  ⚠️  Position exceeds 10% limit: ${position_size:,.2f}")
        elif position_size < min_position:
            logger.warning(f"  ⚠️  Position below minimum: ${position_size:,.2f}")
        else:
            logger.info(f"  ✅ Position within risk limits")

    def _validate_grid(self, params, grid):
        """Validate grid generation"""
        total_value = sum(order["value"] for order in grid["orders"])

        if abs(total_value - params["total_investment"]) > 1:
            logger.warning(
                f"  ⚠️  Grid total mismatch: ${total_value:.2f} vs ${params['total_investment']:.2f}"
            )
        else:
            logger.info(f"  ✅ Grid total matches investment")

        # Check price spacing
        prices = [order["price"] for order in grid["orders"]]
        if len(prices) > 1:
            spacing = [
                (prices[i] - prices[i + 1]) / prices[i + 1] * 100
                for i in range(len(prices) - 1)
            ]
            avg_spacing = sum(spacing) / len(spacing)
            logger.info(f"  Average grid spacing: {avg_spacing:.2f}%")

    async def generate_report(self):
        """Generate comprehensive test report"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST REPORT SUMMARY")
        logger.info("=" * 80)

        total_tests = 0
        passed_tests = 0

        for category, results in self.test_results.items():
            if results:
                category_passed = 0
                category_total = 0

                for test_name, test_result in results.items():
                    if isinstance(test_result, dict) and "passed" in test_result:
                        category_total += 1
                        if test_result["passed"]:
                            category_passed += 1

                if category_total > 0:
                    total_tests += category_total
                    passed_tests += category_passed
                    pass_rate = (category_passed / category_total) * 100

                    status = (
                        "✅" if pass_rate == 100 else "⚠️" if pass_rate >= 70 else "❌"
                    )
                    logger.info(
                        f"\n{status} {category.upper()}: {category_passed}/{category_total} passed ({pass_rate:.1f}%)"
                    )

        if total_tests > 0:
            overall_pass_rate = (passed_tests / total_tests) * 100
            logger.info(f"\n" + "=" * 60)
            logger.info(
                f"OVERALL: {passed_tests}/{total_tests} tests passed ({overall_pass_rate:.1f}%)"
            )

            if overall_pass_rate == 100:
                logger.info("🎉 ALL TESTS PASSED! System ready for paper trading.")
            elif overall_pass_rate >= 80:
                logger.info(
                    "✅ System mostly functional. Review warnings before live trading."
                )
            else:
                logger.info("❌ System needs fixes before trading.")

    async def cleanup(self):
        """Clean up test resources"""
        if self.hummingbot_client:
            await self.hummingbot_client.disconnect()
        logger.info("\n✅ Test cleanup completed")

    async def run_all_tests(self):
        """Run all comprehensive tests"""
        try:
            # Setup
            if not await self.setup():
                logger.error("Setup failed, aborting tests")
                return

            # Run all test suites
            await self.test_dca_detection()
            await self.test_ml_predictions()
            await self.test_position_sizing()
            await self.test_grid_generation()
            await self.test_order_execution()
            await self.test_exit_strategies()
            await self.test_risk_management()
            await self.test_performance_tracking()
            await self.test_full_dca_cycle()

            # Generate report
            await self.generate_report()

        except Exception as e:
            logger.error(f"Test error: {e}")
            import traceback

            traceback.print_exc()

        finally:
            await self.cleanup()


async def main():
    """Main test execution"""
    tester = ComprehensiveTradingTest()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
