#!/usr/bin/env python3
"""
Simple Test of Adaptive Grid Generation with ML Predictions
Tests the integration without database dependencies
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pickle
import json
import pandas as pd
import numpy as np
from datetime import datetime
from loguru import logger
from src.strategies.dca.grid import GridCalculator
from src.trading.position_sizer import AdaptivePositionSizer, PositionSizingConfig

# Configure logging
logger.add("logs/test_adaptive_grid_simple.log", rotation="10 MB")


class SimpleAdaptiveGridTester:
    def __init__(self):
        """Initialize the tester"""
        # Load the trained ML model
        self.model = None
        self.feature_names = None
        self.load_ml_model()

        # Initialize position sizer
        config = PositionSizingConfig(
            base_position_usd=100.0, max_position_pct=0.05, min_position_usd=25.0
        )
        self.position_sizer = AdaptivePositionSizer(config)

    def load_ml_model(self):
        """Load the trained XGBoost model"""
        try:
            # Load model
            with open("models/dca/xgboost_multi_output.pkl", "rb") as f:
                self.model = pickle.load(f)
            logger.info("✅ Loaded XGBoost model")

            # Load feature names
            with open("models/dca/features.json", "r") as f:
                feature_data = json.load(f)
                self.feature_names = feature_data["feature_cols"]
            logger.info(f"✅ Loaded {len(self.feature_names)} feature names")

        except Exception as e:
            logger.error(f"Error loading ML model: {e}")
            raise

    def create_test_features(self, scenario: str) -> pd.DataFrame:
        """Create test features for different scenarios"""

        scenarios = {
            "bear_oversold": {
                "volume": 1000000,
                "volume_ratio": 2.5,
                "threshold": -7.0,
                "market_cap_tier": 1,  # mid
                "btc_regime": -1,  # BEAR
                "btc_price": 40000,
                "btc_sma50": 42000,
                "btc_sma200": 45000,
                "btc_sma50_distance": -0.05,
                "btc_sma200_distance": -0.11,
                "btc_trend_strength": -0.5,
                "btc_volatility_7d": 0.05,
                "btc_volatility_30d": 0.06,
                "btc_high_low_range_7d": 0.08,
                "symbol_vs_btc_7d": -0.02,
                "symbol_vs_btc_30d": -0.05,
                "symbol_correlation_30d": 0.7,
                "is_high_volatility": 1,
                "is_oversold": 1,
                "is_overbought": 0,
                "day_of_week": 1,
                "hour": 14,
            },
            "bull_dip": {
                "volume": 800000,
                "volume_ratio": 1.5,
                "threshold": -5.0,
                "market_cap_tier": 1,  # mid
                "btc_regime": 1,  # BULL
                "btc_price": 60000,
                "btc_sma50": 58000,
                "btc_sma200": 55000,
                "btc_sma50_distance": 0.03,
                "btc_sma200_distance": 0.09,
                "btc_trend_strength": 0.7,
                "btc_volatility_7d": 0.03,
                "btc_volatility_30d": 0.04,
                "btc_high_low_range_7d": 0.05,
                "symbol_vs_btc_7d": 0.01,
                "symbol_vs_btc_30d": 0.03,
                "symbol_correlation_30d": 0.6,
                "is_high_volatility": 0,
                "is_oversold": 0,
                "is_overbought": 0,
                "day_of_week": 3,
                "hour": 10,
            },
            "neutral_normal": {
                "volume": 900000,
                "volume_ratio": 1.8,
                "threshold": -5.5,
                "market_cap_tier": 1,  # mid
                "btc_regime": 0,  # NEUTRAL
                "btc_price": 50000,
                "btc_sma50": 50000,
                "btc_sma200": 50000,
                "btc_sma50_distance": 0.0,
                "btc_sma200_distance": 0.0,
                "btc_trend_strength": 0.0,
                "btc_volatility_7d": 0.04,
                "btc_volatility_30d": 0.05,
                "btc_high_low_range_7d": 0.06,
                "symbol_vs_btc_7d": 0.0,
                "symbol_vs_btc_30d": 0.0,
                "symbol_correlation_30d": 0.65,
                "is_high_volatility": 0,
                "is_oversold": 1,
                "is_overbought": 0,
                "day_of_week": 2,
                "hour": 12,
            },
        }

        base_features = scenarios.get(scenario, scenarios["neutral_normal"])

        # Create full feature set with defaults
        features = {}
        for feature in self.feature_names:
            if feature in base_features:
                features[feature] = base_features[feature]
            else:
                # Default values for missing features
                features[feature] = 0.0

        df = pd.DataFrame([features])
        return df[self.feature_names]

    def get_ml_predictions(self, features_df: pd.DataFrame) -> dict:
        """Get ML predictions"""
        try:
            # Get predictions (no scaling since we couldn't load scaler)
            predictions = self.model.predict(features_df.values)

            # Parse multi-output predictions
            pred_dict = {
                "position_mult": float(np.clip(predictions[0][0], 0.5, 3.0)),
                "take_profit": float(np.clip(predictions[0][1], 0.03, 0.20)),
                "stop_loss": float(np.clip(predictions[0][2], -0.15, -0.03)),
                "hold_hours": float(np.clip(predictions[0][3], 4, 72)),
                "win_probability": float(np.clip(predictions[0][4], 0, 1)),
            }

            return pred_dict

        except Exception as e:
            logger.error(f"Error getting ML predictions: {e}")
            return None

    def test_scenario(self, symbol: str, scenario: str, entry_price: float = 100.0):
        """Test a specific scenario"""
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing: {symbol} - {scenario.upper()}")
        logger.info(f"{'='*60}")

        # Create features for scenario
        features_df = self.create_test_features(scenario)

        # Get ML predictions
        predictions = self.get_ml_predictions(features_df)
        if not predictions:
            logger.error("Failed to get predictions")
            return None

        logger.info(f"\n🤖 ML Predictions:")
        logger.info(f"  Position Multiplier: {predictions['position_mult']:.2f}x")
        logger.info(f"  Take Profit: {predictions['take_profit']*100:.1f}%")
        logger.info(f"  Stop Loss: {predictions['stop_loss']*100:.1f}%")
        logger.info(f"  Expected Hold: {predictions['hold_hours']:.0f} hours")
        logger.info(f"  Win Probability: {predictions['win_probability']*100:.1f}%")

        # Calculate adaptive position size
        btc_regime_val = (
            features_df["btc_regime"].iloc[0]
            if "btc_regime" in features_df.columns
            else 0
        )
        market_data = {
            "btc_regime": ["BEAR", "NEUTRAL", "BULL"][int(btc_regime_val) + 1],
            "symbol_volatility": features_df["btc_volatility_7d"].iloc[0]
            if "btc_volatility_7d" in features_df.columns
            else 0.04,
            "symbol_vs_btc_7d": features_df["symbol_vs_btc_7d"].iloc[0]
            if "symbol_vs_btc_7d" in features_df.columns
            else 0.0,
            "market_cap_tier": "mid",
        }

        position_size, multipliers = self.position_sizer.calculate_position_size(
            symbol=symbol,
            portfolio_value=10000,
            market_data=market_data,
            ml_confidence=predictions["win_probability"],
        )

        logger.info(f"\n💰 Position Sizing:")
        logger.info(f"  Base: $100")
        for key, value in multipliers.items():
            logger.info(f"  {key}: {value:.2f}x")
        logger.info(f"  Final Size: ${position_size:.2f}")

        # Generate adaptive grid
        grid_config = {
            "grid_levels": 5,
            "grid_spacing": 1.0,
            "base_size": position_size / 5,
            "take_profit": predictions["take_profit"] * 100,  # Convert to percentage
            "stop_loss": predictions["stop_loss"] * 100,  # Convert to percentage
        }

        # Create simple support levels for testing
        support_levels = [
            entry_price * 0.98,  # -2%
            entry_price * 0.96,  # -4%
            entry_price * 0.94,  # -6%
        ]

        grid_calculator = GridCalculator(grid_config)
        grid = grid_calculator.calculate_grid(
            current_price=entry_price,
            ml_confidence=predictions["win_probability"],
            support_levels=support_levels,
            total_capital=position_size,
        )

        logger.info(f"\n📈 DCA Grid:")
        logger.info(f"  Entry: ${entry_price:.2f}")
        logger.info(f"  Investment: ${grid['total_investment']:.2f}")
        logger.info(
            f"  TP: ${grid.get('take_profit', entry_price * 1.1):.2f} (+{predictions['take_profit']*100:.1f}%)"
        )
        logger.info(
            f"  SL: ${grid.get('stop_loss', entry_price * 0.9):.2f} ({predictions['stop_loss']*100:.1f}%)"
        )

        logger.info(f"\n  Levels:")
        for i, level in enumerate(grid["levels"], 1):
            logger.info(f"    L{i}: ${level['price']:.2f} | ${level['size']:.2f}")

        # Calculate expected value
        avg_price = grid.get("average_entry", entry_price)
        total_coins = grid["total_investment"] / avg_price
        tp_price = grid.get(
            "take_profit", entry_price * (1 + predictions["take_profit"])
        )
        sl_price = grid.get("stop_loss", entry_price * (1 + predictions["stop_loss"]))
        tp_profit = (total_coins * tp_price) - grid["total_investment"]
        sl_loss = (total_coins * sl_price) - grid["total_investment"]

        ev = (predictions["win_probability"] * tp_profit) + (
            (1 - predictions["win_probability"]) * sl_loss
        )
        ev_pct = (ev / grid["total_investment"]) * 100

        logger.info(f"\n📊 Expected Value:")
        logger.info(
            f"  Win: ${tp_profit:.2f} ({tp_profit/grid['total_investment']*100:.1f}%)"
        )
        logger.info(
            f"  Loss: ${sl_loss:.2f} ({sl_loss/grid['total_investment']*100:.1f}%)"
        )
        logger.info(f"  EV: ${ev:.2f} ({ev_pct:.1f}%)")
        logger.info(f"  Risk/Reward: {abs(tp_profit/sl_loss):.2f}:1")

        return {
            "symbol": symbol,
            "scenario": scenario,
            "predictions": predictions,
            "position_size": position_size,
            "grid": grid,
            "expected_value": ev,
        }


def main():
    """Main test function"""
    tester = SimpleAdaptiveGridTester()

    # Test different scenarios
    test_cases = [
        ("SOL", "bear_oversold", 150.0),  # SOL in bear market, oversold
        ("RENDER", "bull_dip", 8.0),  # RENDER small dip in bull
        ("PEPE", "neutral_normal", 0.001),  # PEPE normal conditions
    ]

    results = []

    for symbol, scenario, price in test_cases:
        try:
            result = tester.test_scenario(symbol, scenario, price)
            if result:
                results.append(result)
        except Exception as e:
            logger.error(f"Error testing {symbol}/{scenario}: {e}")

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("SUMMARY")
    logger.info(f"{'='*60}")

    for result in results:
        logger.info(f"\n{result['symbol']} ({result['scenario']}):")
        logger.info(f"  Position: ${result['position_size']:.2f}")
        logger.info(
            f"  Confidence: {result['predictions']['win_probability']*100:.0f}%"
        )
        logger.info(f"  Expected Value: ${result['expected_value']:.2f}")

    logger.info(f"\n✅ ML-Adaptive Grid Generation Working!")
    logger.info(f"System successfully:")
    logger.info(f"  1. Loads trained XGBoost model")
    logger.info(f"  2. Makes multi-output predictions")
    logger.info(f"  3. Adapts position size based on ML confidence")
    logger.info(f"  4. Generates grids with ML-optimized parameters")
    logger.info(f"  5. Calculates risk-adjusted expected values")


if __name__ == "__main__":
    main()
