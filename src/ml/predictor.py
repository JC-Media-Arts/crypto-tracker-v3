"""
ML Predictor module for making predictions with trained models.
Provides a unified interface for all strategy predictions.
"""

import joblib
import pickle
import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, Any
import os
from datetime import datetime, timezone
from pathlib import Path
from loguru import logger


class MLPredictor:
    """ML prediction interface for all strategies"""

    def __init__(self):
        """Initialize the predictor and load models"""
        self.models = {}
        self.scalers = {}
        self.feature_configs = {}
        self.model_paths = {
            "dca": {
                "model": "models/dca/xgboost_multi_output.pkl",
                "scaler": "models/dca/scaler.pkl",
                "features": "models/dca/features.json",
            },
            "swing": {
                "model": "models/swing/swing_classifier.pkl",
                "scaler": "models/swing/swing_scaler.pkl",
                "features": "models/swing/training_results.json",
            },
            "channel": {
                "model": "models/channel/classifier.pkl",
                "scaler": "models/channel/scaler.pkl",
                "features": "models/channel/config.json",
            },
        }
        self.load_models()

    def load_models(self):
        """Load all trained models and their configurations"""
        project_root = Path(__file__).parent.parent.parent

        for strategy, paths in self.model_paths.items():
            # Load model
            model_path = project_root / paths["model"]
            if model_path.exists():
                try:
                    with open(model_path, "rb") as f:
                        self.models[strategy] = pickle.load(f)
                    logger.info(f"✅ Loaded {strategy} model from {paths['model']}")
                except Exception as e:
                    logger.error(f"❌ Failed to load {strategy} model: {e}")
                    self.models[strategy] = None
            else:
                logger.warning(f"⚠️ Model not found: {paths['model']}")
                self.models[strategy] = None

            # Load scaler if exists
            scaler_path = project_root / paths["scaler"]
            if scaler_path.exists():
                try:
                    with open(scaler_path, "rb") as f:
                        self.scalers[strategy] = pickle.load(f)
                    logger.info(f"✅ Loaded {strategy} scaler")
                except Exception as e:
                    logger.error(f"Failed to load {strategy} scaler: {e}")
                    self.scalers[strategy] = None

            # Load feature config if exists
            if "features" in paths:
                features_path = project_root / paths["features"]
                if features_path.exists():
                    try:
                        import json

                        with open(features_path, "r") as f:
                            self.feature_configs[strategy] = json.load(f)
                    except Exception as e:
                        logger.error(f"Failed to load {strategy} features: {e}")

    async def predict(
        self, symbol: str, strategy: str = None, features: Dict = None
    ) -> Optional[Dict[str, Any]]:
        """
        Make prediction for a symbol

        Args:
            symbol: Trading symbol (e.g., 'BTC')
            strategy: Strategy type ('dca', 'swing', 'channel') or None for all
            features: Feature dictionary (if None, will calculate)

        Returns:
            Dictionary with predictions and confidence scores
        """
        if strategy:
            return await self._predict_single(symbol, strategy, features)
        else:
            # Predict for all strategies
            results = {}
            for strat in ["dca", "swing", "channel"]:
                result = await self._predict_single(symbol, strat, features)
                if result:
                    results[strat] = result
            return results if results else None

    async def _predict_single(
        self, symbol: str, strategy: str, features: Dict = None
    ) -> Optional[Dict[str, Any]]:
        """Make prediction for a single strategy"""

        if strategy not in self.models or self.models[strategy] is None:
            logger.warning(f"Model not available for {strategy}")
            return None

        try:
            # Get features if not provided
            if features is None:
                features = await self._calculate_features(symbol, strategy)
                if features is None:
                    return None

            # Prepare features for model
            feature_array = self._prepare_features(strategy, features)

            # Scale features if scaler exists
            if strategy in self.scalers and self.scalers[strategy]:
                feature_array = self.scalers[strategy].transform(feature_array)

            # Get prediction
            model = self.models[strategy]

            # Handle different model types
            if hasattr(model, "predict_proba"):
                # Classification model
                prediction = model.predict(feature_array)[0]
                probabilities = model.predict_proba(feature_array)[0]
                confidence = float(probabilities.max())
                signal = bool(prediction)
            elif hasattr(model, "predict"):
                # Regression or other model
                prediction = model.predict(feature_array)[0]

                # For multi-output models (like DCA)
                if isinstance(prediction, np.ndarray) and len(prediction) > 1:
                    signal = prediction[0] > 0.5  # First output as signal
                    confidence = float(prediction[1]) if len(prediction) > 1 else 0.7
                else:
                    signal = float(prediction) > 0.5
                    confidence = (
                        abs(float(prediction) - 0.5) * 2
                    )  # Convert to confidence
            else:
                logger.error(f"Unknown model type for {strategy}")
                return None

            result = {
                "symbol": symbol,
                "strategy": strategy,
                "signal": signal,
                "confidence": min(max(confidence, 0.0), 1.0),  # Ensure 0-1 range
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "features_used": list(features.keys()),
            }

            # Add strategy-specific outputs
            if (
                strategy == "dca"
                and isinstance(prediction, np.ndarray)
                and len(prediction) >= 4
            ):
                result["grid_levels"] = int(prediction[2]) if len(prediction) > 2 else 3
                result["position_size"] = (
                    float(prediction[3]) if len(prediction) > 3 else 0.01
                )

            return result

        except Exception as e:
            logger.error(f"❌ Prediction error for {symbol}/{strategy}: {e}")
            return None

    async def _calculate_features(self, symbol: str, strategy: str) -> Optional[Dict]:
        """Calculate features for a symbol (if not provided)"""
        try:
            # Import feature calculator
            from src.ml.feature_calculator import FeatureCalculator

            calculator = FeatureCalculator()

            # Calculate features
            features_df = await calculator.calculate_features_for_symbol(
                symbol, lookback_hours=72
            )

            if features_df is None or features_df.empty:
                logger.warning(f"No features calculated for {symbol}")
                return None

            # Get the latest features
            latest_features = features_df.iloc[-1].to_dict()

            return latest_features

        except Exception as e:
            logger.error(f"Error calculating features for {symbol}: {e}")
            return None

    def _prepare_features(self, strategy: str, features: Dict) -> np.ndarray:
        """Prepare features for model input"""

        # Define expected features for each strategy
        feature_orders = {
            "dca": [
                "rsi_14",
                "rsi_30",
                "macd_signal",
                "macd_histogram",
                "bb_position",
                "volume_ratio",
                "price_change_pct",
                "volatility",
                "support_distance",
                "resistance_distance",
                "trend_strength",
                "volume_trend",
                "bb_width",
                "stoch_k",
                "stoch_d",
                "atr_14",
                "obv",
                "ema_12",
                "ema_26",
                "sma_50",
                "sma_200",
                "price_position",
            ],
            "swing": [
                "rsi_14",
                "macd_signal",
                "bb_width",
                "volume_surge",
                "breakout_strength",
                "momentum_score",
                "trend_alignment",
                "volatility",
                "atr_14",
                "obv_trend",
                "price_momentum",
                "volume_profile",
            ],
            "channel": [
                "bb_position",
                "bb_width",
                "channel_position",
                "keltner_position",
                "volatility",
                "volume_ratio",
                "rsi_14",
                "stoch_k",
                "price_relative_high",
                "price_relative_low",
                "volume_profile",
                "trend_strength",
            ],
        }

        # Get feature order for strategy
        feature_order = feature_orders.get(strategy, [])

        if not feature_order:
            # If no predefined order, use all available features
            feature_order = sorted(features.keys())

        # Create feature array
        feature_list = []
        for feature_name in feature_order:
            if feature_name in features:
                value = features[feature_name]
                # Handle NaN or None values
                if pd.isna(value) or value is None:
                    value = 0.0
                feature_list.append(float(value))
            else:
                # Missing feature, use 0
                feature_list.append(0.0)

        return np.array([feature_list])

    def get_model_info(self, strategy: str = None) -> Dict:
        """Get information about loaded models"""
        if strategy:
            if strategy in self.models:
                return {
                    "strategy": strategy,
                    "model_loaded": self.models[strategy] is not None,
                    "scaler_loaded": self.scalers.get(strategy) is not None,
                    "features_config": bool(self.feature_configs.get(strategy)),
                }
            else:
                return {"error": f"Unknown strategy: {strategy}"}
        else:
            # Return info for all strategies
            info = {}
            for strat in ["dca", "swing", "channel"]:
                info[strat] = {
                    "model_loaded": self.models.get(strat) is not None,
                    "scaler_loaded": self.scalers.get(strat) is not None,
                    "features_config": bool(self.feature_configs.get(strat)),
                }
            return info


# Create global instance for easy access
ml_predictor = MLPredictor()
