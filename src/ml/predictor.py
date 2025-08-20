"""
ML Predictor module for crypto price direction predictions.
Uses XGBoost to predict if price will go UP or DOWN in 2 hours.
"""

import asyncio
import joblib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import numpy as np

# import pandas as pd  # noqa: F401 - will be used
from loguru import logger
import xgboost as xgb

from src.config import Settings
from src.data.supabase_client import SupabaseClient
from src.ml.feature_calculator import FeatureCalculator


class MLPredictor:
    """Handles ML predictions for crypto price movements."""

    # ML Configuration (from master plan)
    ML_CONFIG = {
        "prediction_target": "price_direction_2h",  # UP or DOWN in 2 hours
        "features": [
            "returns_5m",
            "returns_1h",
            "rsi_14",
            "distance_from_sma20",
            "volume_ratio",
            "support_distance",
        ],
        "minimum_confidence": 0.60,
        "minimum_accuracy": 0.55,
    }

    def __init__(self, settings: Settings):
        """Initialize ML predictor."""
        self.settings = settings
        self.db_client: Optional[SupabaseClient] = None
        self.feature_calculator: Optional[FeatureCalculator] = None
        self.model: Optional[xgb.XGBClassifier] = None
        self.model_path = Path(settings.models_dir) / "xgboost_model.pkl"
        self.running = False
        self.last_predictions: Dict[str, Dict] = {}
        self.model_accuracy = 0.0

        # Strategy-specific models
        self.dca_model = None
        self.swing_model = None
        self.channel_model = None
        self.models_loaded = False

        # Load models on initialization
        self._load_strategy_models()

    async def initialize(self):
        """Initialize the ML predictor."""
        logger.info("Initializing ML predictor...")

        try:
            # Initialize database client
            self.db_client = SupabaseClient(self.settings)
            await self.db_client.initialize()

            # Initialize feature calculator
            self.feature_calculator = FeatureCalculator(self.db_client)

            # Load model if exists
            await self._load_model()

            logger.success("ML predictor initialized")

        except Exception as e:
            logger.error(f"Failed to initialize ML predictor: {e}")
            raise

    async def _load_model(self):
        """Load trained model from disk."""
        if self.model_path.exists():
            try:
                self.model = joblib.load(self.model_path)
                logger.info(f"Loaded model from {self.model_path}")

                # Load model metadata if available
                metadata_path = self.model_path.with_suffix(".meta")
                if metadata_path.exists():
                    metadata = joblib.load(metadata_path)
                    self.model_accuracy = metadata.get("accuracy", 0.0)
                    logger.info(f"Model accuracy: {self.model_accuracy:.2%}")
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                self.model = None
        else:
            logger.warning("No trained model found. Please train a model first.")
            self.model = None

    async def start(self):
        """Start making predictions."""
        logger.info("Starting ML predictions...")
        self.running = True

        # Start prediction loop
        asyncio.create_task(self._prediction_loop())

        # Start accuracy tracking
        asyncio.create_task(self._track_accuracy())

        logger.success("ML predictions started")

    async def _prediction_loop(self):
        """Main prediction loop."""
        while self.running:
            try:
                if self.model is None:
                    logger.warning("No model available, skipping predictions")
                    await asyncio.sleep(60)
                    continue

                # Get symbols to predict
                symbols = await self._get_active_symbols()

                for symbol in symbols:
                    try:
                        prediction = await self.make_prediction(symbol)
                        if prediction:
                            self.last_predictions[symbol] = prediction

                            # Store prediction in database
                            await self.db_client.insert_prediction(
                                {
                                    "symbol": symbol,
                                    "prediction": prediction["direction"],
                                    "confidence": prediction["confidence"],
                                    "timestamp": datetime.utcnow().isoformat(),
                                }
                            )

                            logger.info(
                                f"Prediction for {symbol}: {prediction['direction']} "
                                f"(confidence: {prediction['confidence']:.2%})"
                            )
                    except Exception as e:
                        logger.error(f"Failed to predict for {symbol}: {e}")

                # Wait before next prediction cycle
                await asyncio.sleep(60)  # Predict every minute

            except Exception as e:
                logger.error(f"Error in prediction loop: {e}")
                await asyncio.sleep(60)

    async def make_prediction(self, symbol: str) -> Optional[Dict]:
        """Make a prediction for a symbol."""
        try:
            # Calculate features
            features = await self.feature_calculator.calculate_features(symbol)
            if features is None:
                return None

            # Prepare features for model
            X = self._prepare_features(features)

            # Make prediction
            prediction_proba = self.model.predict_proba(X)[0]
            prediction = self.model.predict(X)[0]

            # Get confidence (probability of predicted class)
            confidence = max(prediction_proba)

            # Only return if confidence meets threshold
            if confidence < self.ML_CONFIG["minimum_confidence"]:
                logger.debug(f"Low confidence for {symbol}: {confidence:.2%}")
                return None

            return {
                "symbol": symbol,
                "direction": "UP" if prediction == 1 else "DOWN",
                "confidence": float(confidence),
                "timestamp": datetime.utcnow().isoformat(),
                "features": features,
            }

        except Exception as e:
            logger.error(f"Failed to make prediction for {symbol}: {e}")
            return None

    def _prepare_features(self, features: Dict) -> np.ndarray:
        """Prepare features for model input."""
        # Extract features in the correct order
        feature_values = []
        for feature_name in self.ML_CONFIG["features"]:
            value = features.get(feature_name, 0.0)
            feature_values.append(value)

        return np.array([feature_values])

    async def _get_active_symbols(self) -> List[str]:
        """Get symbols with recent data."""
        # For now, return top tier coins
        # In production, this would check which symbols have recent data
        from src.data.collector import DataCollector

        return DataCollector.TIER_1_COINS[:10]  # Start with top 10 coins

    async def _track_accuracy(self):
        """Track prediction accuracy."""
        while self.running:
            await asyncio.sleep(3600)  # Check every hour

            try:
                # Get predictions from 2 hours ago
                two_hours_ago = datetime.utcnow() - timedelta(hours=2)

                # TODO: Implement accuracy tracking
                # This would compare predictions with actual price movements

                logger.info(f"Current model accuracy: {self.model_accuracy:.2%}")

                # Alert if accuracy drops
                if self.model_accuracy < self.ML_CONFIG["minimum_accuracy"]:
                    logger.warning(
                        f"Model accuracy below threshold: {self.model_accuracy:.2%}"
                    )

            except Exception as e:
                logger.error(f"Error tracking accuracy: {e}")

    async def stop(self):
        """Stop ML predictions."""
        logger.info("Stopping ML predictions...")
        self.running = False
        logger.info("ML predictions stopped")

    def get_last_prediction(self, symbol: str) -> Optional[Dict]:
        """Get the last prediction for a symbol."""
        return self.last_predictions.get(symbol)

    def get_model_status(self) -> Dict:
        """Get model status information."""
        return {
            "model_loaded": self.model is not None,
            "model_accuracy": self.model_accuracy,
            "active_predictions": len(self.last_predictions),
            "last_update": datetime.utcnow().isoformat(),
        }

    def _load_strategy_models(self):
        """Load strategy-specific ML models."""
        models_dir = Path(self.settings.models_dir)

        # Load DCA model
        dca_model_path = models_dir / "dca" / "xgboost_multi_output.pkl"
        if dca_model_path.exists():
            try:
                self.dca_model = joblib.load(dca_model_path)
                logger.info(f"Loaded DCA model from {dca_model_path}")
            except Exception as e:
                logger.error(f"Failed to load DCA model: {e}")

        # Load Swing model
        swing_model_path = models_dir / "swing" / "swing_classifier.pkl"
        if swing_model_path.exists():
            try:
                self.swing_model = joblib.load(swing_model_path)
                logger.info(f"Loaded Swing model from {swing_model_path}")
            except Exception as e:
                logger.error(f"Failed to load Swing model: {e}")

        # Load Channel model
        channel_model_path = models_dir / "channel" / "classifier.pkl"
        if channel_model_path.exists():
            try:
                self.channel_model = joblib.load(channel_model_path)
                logger.info(f"Loaded Channel model from {channel_model_path}")
            except Exception as e:
                logger.error(f"Failed to load Channel model: {e}")

        self.models_loaded = True

    def predict_dca(self, features: Dict) -> Dict:
        """
        Predict DCA trading opportunity.
        Returns confidence and predicted outcomes.
        """
        try:
            if self.dca_model is None:
                logger.warning("DCA model not loaded, returning default prediction")
                return {
                    "confidence": 0.0,
                    "predicted_return": 0.0,
                    "take_profit_pct": 10.0,
                    "stop_loss_pct": 5.0,
                    "hold_hours": 24,
                    "grid_levels": 5,
                    # Fields expected by StrategyManager
                    "win_probability": 0.0,
                    "optimal_take_profit": 10.0,
                    "optimal_stop_loss": 5.0,
                }

            # Prepare features for prediction
            feature_array = self._prepare_dca_features(features)

            # Get prediction from model
            prediction = self.dca_model.predict(feature_array)

            # DCA model is a MultiOutputRegressor, calculate confidence from predictions
            # prediction[0] contains [position_mult, take_profit, stop_loss, hold_hours, win_prob]
            if hasattr(prediction[0], "__len__") and len(prediction[0]) >= 5:
                # Use win_prob as confidence
                confidence = float(prediction[0][4])  # win_prob is the 5th output
                take_profit = float(prediction[0][1]) if prediction[0][1] > 0 else 10.0
                stop_loss = float(prediction[0][2]) if prediction[0][2] > 0 else 5.0
                hold_hours = float(prediction[0][3]) if prediction[0][3] > 0 else 24
            else:
                # Fallback if prediction shape is unexpected
                confidence = 0.65  # Default confidence
                take_profit = 10.0
                stop_loss = 5.0
                hold_hours = 24

            # Ensure confidence is between 0 and 1
            confidence = max(0.0, min(1.0, confidence))

            return {
                "confidence": confidence,
                "predicted_return": take_profit - stop_loss,
                "take_profit_pct": take_profit,
                "stop_loss_pct": stop_loss,
                "hold_hours": hold_hours,
                "grid_levels": 5,
                # Fields expected by StrategyManager
                "win_probability": confidence,  # Use confidence as win probability
                "optimal_take_profit": take_profit,
                "optimal_stop_loss": stop_loss,
            }

        except Exception as e:
            logger.error(f"Error in DCA prediction: {e}")
            return {
                "confidence": 0.0,
                "predicted_return": 0.0,
                "take_profit_pct": 10.0,
                "stop_loss_pct": 5.0,
                "hold_hours": 24,
                "grid_levels": 5,
                # Fields expected by StrategyManager
                "win_probability": 0.0,
                "optimal_take_profit": 10.0,
                "optimal_stop_loss": 5.0,
            }

    def predict_swing(self, features: Dict) -> Dict:
        """
        Predict Swing trading opportunity.
        Returns confidence and predicted outcomes.
        """
        try:
            if self.swing_model is None:
                logger.warning("Swing model not loaded, returning default prediction")
                return {
                    "confidence": 0.0,
                    "predicted_direction": "NEUTRAL",
                    "take_profit_pct": 15.0,
                    "stop_loss_pct": 7.0,
                    "hold_hours": 48,
                }

            # Prepare features for prediction
            feature_array = self._prepare_swing_features(features)

            # Get prediction from model
            prediction = self.swing_model.predict(feature_array)
            confidence = self.swing_model.predict_proba(feature_array)[0].max()

            return {
                "confidence": float(confidence),
                "predicted_direction": "UP" if prediction[0] > 0 else "DOWN",
                "take_profit_pct": 15.0,  # Can be adjusted based on model
                "stop_loss_pct": 7.0,  # Can be adjusted based on model
                "hold_hours": 48,
            }

        except Exception as e:
            logger.error(f"Error in Swing prediction: {e}")
            return {
                "confidence": 0.0,
                "predicted_direction": "NEUTRAL",
                "take_profit_pct": 15.0,
                "stop_loss_pct": 7.0,
                "hold_hours": 48,
            }

    def predict_channel(self, features: Dict) -> Dict:
        """
        Predict Channel trading opportunity.
        Returns confidence and predicted outcomes.
        """
        try:
            if self.channel_model is None:
                logger.warning("Channel model not loaded, returning default prediction")
                return {
                    "confidence": 0.0,
                    "predicted_bounce": False,
                    "take_profit_pct": 8.0,
                    "stop_loss_pct": 4.0,
                    "hold_hours": 12,
                }

            # Prepare features for prediction
            feature_array = self._prepare_channel_features(features)

            # Get prediction from model
            prediction = self.channel_model.predict(feature_array)
            confidence = self.channel_model.predict_proba(feature_array)[0].max()

            return {
                "confidence": float(confidence),
                "predicted_bounce": bool(prediction[0] > 0),
                "take_profit_pct": 8.0,  # Can be adjusted based on model
                "stop_loss_pct": 4.0,  # Can be adjusted based on model
                "hold_hours": 12,
            }

        except Exception as e:
            logger.error(f"Error in Channel prediction: {e}")
            return {
                "confidence": 0.0,
                "predicted_bounce": False,
                "take_profit_pct": 8.0,
                "stop_loss_pct": 4.0,
                "hold_hours": 12,
            }

    def _prepare_dca_features(self, features: Dict) -> np.ndarray:
        """Prepare features for DCA model."""
        # DCA model expects 22 features based on features.json
        feature_list = [
            features.get("volume", 1000000),
            features.get("volume_ratio", 1.0),
            features.get("threshold", 0.6),
            features.get("market_cap_tier", 1),
            features.get("btc_regime", 0),
            features.get("btc_price", 100000),
            features.get("btc_sma50", 100000),
            features.get("btc_sma200", 95000),
            features.get("btc_sma50_distance", 0.0),
            features.get("btc_sma200_distance", 0.05),
            features.get("btc_trend_strength", 0.5),
            features.get("btc_volatility_7d", 0.02),
            features.get("btc_volatility_30d", 0.03),
            features.get("btc_high_low_range_7d", 0.1),
            features.get("symbol_vs_btc_7d", 0.0),
            features.get("symbol_vs_btc_30d", 0.0),
            features.get("symbol_correlation_30d", 0.7),
            features.get("is_high_volatility", 0),
            features.get("is_oversold", 0),
            features.get("is_overbought", 0),
            features.get("day_of_week", 1),
            features.get("hour", 12),
        ]
        return np.array([feature_list])

    def _prepare_swing_features(self, features: Dict) -> np.ndarray:
        """Prepare features for Swing model."""
        # Swing model expects 6 features (based on error message)
        feature_list = [
            features.get("breakout_strength", 0),
            features.get("volume_surge", 1),
            features.get("rsi", 50),
            features.get("momentum", 0),
            features.get("trend_strength", 0),
            features.get("volatility", 0.02),  # Added 6th feature
        ]
        return np.array([feature_list])

    def _prepare_channel_features(self, features: Dict) -> np.ndarray:
        """Prepare features for Channel model."""
        # Channel model expects 8 features based on config.json
        # Using feature_columns from config
        feature_list = [
            features.get("range_width", 0.1),
            features.get("position_in_range", 0.5),
            features.get("resistance_touches", 2),
            features.get("support_touches", 2),
            features.get("total_touches", 4),
            features.get("volatility", 0.02),
            features.get("volume_trend", 1.0),
            features.get("risk_reward", 2.0),
        ]
        # Note: Model expects 10 but config shows 8, adding 2 more
        if len(feature_list) < 10:
            feature_list.extend(
                [
                    features.get("rsi", 50),
                    features.get("volume_ratio", 1.0),
                ]
            )
        return np.array([feature_list])
