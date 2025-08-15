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
