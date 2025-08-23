"""
Simple Model Retrainer for Continuous ML Improvement
Retrains models daily when enough new data is available
"""

import os
import pickle
import json
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score
import xgboost as xgb
from loguru import logger


class SimpleRetrainer:
    """Simple retrainer that updates models when enough new data is available"""

    def __init__(self, supabase_client, model_dir: str = "models"):
        """
        Initialize the retrainer

        Args:
            supabase_client: Supabase client for database access
            model_dir: Directory where models are stored
        """
        self.supabase = supabase_client
        self.model_dir = model_dir
        self.min_new_samples = 20  # Minimum new trades to trigger retraining
        self.retrain_frequency = "daily"
        self.last_train_file = os.path.join(model_dir, "last_train.json")

    def should_retrain(self, strategy: str = "DCA") -> Tuple[bool, int]:
        """
        Check if we should retrain the model

        Args:
            strategy: Strategy to check (DCA, SWING, CHANNEL)

        Returns:
            Tuple of (should_retrain, new_sample_count)
        """
        try:
            # Get last training timestamp
            last_train_time = self._get_last_train_time(strategy)

            # Count completed trades since last training
            query = self.supabase.table("trade_logs").select("*", count="exact")
            query = query.eq("strategy_name", strategy)
            query = query.in_("status", ["CLOSED_WIN", "CLOSED_LOSS"])

            if last_train_time:
                query = query.gte("closed_at", last_train_time.isoformat())

            result = query.execute()

            new_outcomes = (
                result.count if hasattr(result, "count") else len(result.data)
            )

            logger.info(
                f"Found {new_outcomes} new completed trades for {strategy} since last training"
            )

            return new_outcomes >= self.min_new_samples, new_outcomes

        except Exception as e:
            logger.error(f"Error checking retrain status: {e}")
            return False, 0

    def retrain(self, strategy: str = "DCA") -> str:
        """
        Retrain the model if conditions are met

        Args:
            strategy: Strategy to retrain (DCA, SWING, CHANNEL)

        Returns:
            Status message
        """
        # Check if we should retrain
        should_retrain, new_samples = self.should_retrain(strategy)

        if not should_retrain:
            return f"Not enough data ({new_samples}/{self.min_new_samples} samples)"

        logger.info(
            f"Starting retraining for {strategy} with {new_samples} new samples"
        )

        try:
            # Get all training data (old + new)
            training_data = self._get_all_training_data(strategy)

            if training_data.empty:
                return "No training data available"

            logger.info(f"Loaded {len(training_data)} total training samples")

            # Prepare features and labels
            X, y = self._prepare_features_labels(training_data, strategy)

            if len(X) < 50:  # Need minimum samples for reliable training
                return f"Insufficient total samples ({len(X)}/50 minimum)"

            # Split for validation
            X_train, X_val, y_train, y_val = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )

            # Train new model with same parameters as original
            new_model = self._train_model(X_train, y_train, strategy)

            # Validate new model
            new_score = self._validate_model(new_model, X_val, y_val)

            # Compare with current model
            current_model = self._load_current_model(strategy)
            if current_model:
                current_score = self._validate_model(current_model, X_val, y_val)
                logger.info(
                    f"Current model score: {current_score:.3f}, New model score: {new_score:.3f}"
                )

                if new_score > current_score:
                    # Save new model
                    self._save_model(new_model, strategy, new_score)
                    self._update_last_train_time(strategy)
                    return f"Model updated (improvement: {new_score:.3f} > {current_score:.3f})"
                else:
                    return f"Kept existing model (current: {current_score:.3f} >= new: {new_score:.3f})"
            else:
                # No existing model, save the new one
                self._save_model(new_model, strategy, new_score)
                self._update_last_train_time(strategy)
                return f"Initial model trained (score: {new_score:.3f})"

        except Exception as e:
            logger.error(f"Error during retraining: {e}")
            return f"Retraining failed: {str(e)}"

    def _get_all_training_data(self, strategy: str) -> pd.DataFrame:
        """Get all training data from the feedback view"""
        try:
            # Query the ml_training_feedback view
            query = self.supabase.table("ml_training_feedback").select("*")
            query = query.eq("strategy_name", strategy)
            query = query.not_.is_("outcome_label", "null")  # Only completed trades

            result = query.execute()

            if result.data:
                df = pd.DataFrame(result.data)

                # Parse JSON features
                if "scan_features" in df.columns:
                    df["features"] = df["scan_features"].apply(
                        lambda x: json.loads(x) if isinstance(x, str) else x
                    )

                return df

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error loading training data: {e}")
            return pd.DataFrame()

    def _prepare_features_labels(
        self, data: pd.DataFrame, strategy: str
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare features and labels for training"""
        features_list = []
        labels_list = []

        for _, row in data.iterrows():
            # Extract features based on strategy
            if strategy == "DCA":
                features = [
                    row.get("features", {}).get("price_drop", 0),
                    row.get("features", {}).get("rsi", 50),
                    row.get("features", {}).get("volume_ratio", 1),
                    row.get("features", {}).get("distance_from_support", 0),
                    row.get("features", {}).get("btc_correlation", 0),
                    row.get("features", {}).get("market_regime", 0),
                ]
            elif strategy == "SWING":
                features = [
                    row.get("features", {}).get("breakout_strength", 0),
                    row.get("features", {}).get("volume_ratio", 1),
                    row.get("features", {}).get("resistance_cleared", 0),
                    row.get("features", {}).get("trend_alignment", 0),
                    row.get("features", {}).get("momentum_score", 0),
                    row.get("features", {}).get("market_regime", 0),
                ]
            else:  # CHANNEL
                features = [
                    row.get("features", {}).get("channel_position", 0),
                    row.get("features", {}).get("channel_width", 0),
                    row.get("features", {}).get("volume_profile", 0),
                    row.get("features", {}).get("range_strength", 0),
                    row.get("features", {}).get("mean_reversion_score", 0),
                    row.get("features", {}).get("market_regime", 0),
                ]

            features_list.append(features)
            labels_list.append(row["outcome_label"])

        return np.array(features_list), np.array(labels_list)

    def _train_model(self, X_train: np.ndarray, y_train: np.ndarray, strategy: str):
        """Train XGBoost model with same parameters as original"""
        # Use same parameters as original model
        params = {
            "n_estimators": 100,
            "max_depth": 5,
            "learning_rate": 0.1,
            "objective": "binary:logistic",
            "random_state": 42,
            "use_label_encoder": False,
            "eval_metric": "logloss",
        }

        model = xgb.XGBClassifier(**params)
        model.fit(X_train, y_train)

        return model

    def _validate_model(self, model, X_val: np.ndarray, y_val: np.ndarray) -> float:
        """Validate model and return score"""
        predictions = model.predict(X_val)

        # Calculate multiple metrics
        accuracy = accuracy_score(y_val, predictions)
        precision = precision_score(y_val, predictions, zero_division=0)
        recall = recall_score(y_val, predictions, zero_division=0)

        # Weighted score (prioritize precision to avoid false positives)
        score = (accuracy * 0.3) + (precision * 0.5) + (recall * 0.2)

        return score

    def _load_current_model(self, strategy: str):
        """Load the current model"""
        try:
            model_file = os.path.join(self.model_dir, f"{strategy.lower()}_model.pkl")
            if os.path.exists(model_file):
                with open(model_file, "rb") as f:
                    return pickle.load(f)
            return None
        except Exception as e:
            logger.error(f"Error loading current model: {e}")
            return None

    def _save_model(self, model, strategy: str, score: float):
        """Save the model and metadata"""
        try:
            # Create model directory if it doesn't exist
            os.makedirs(self.model_dir, exist_ok=True)

            # Save model
            model_file = os.path.join(self.model_dir, f"{strategy.lower()}_model.pkl")
            with open(model_file, "wb") as f:
                pickle.dump(model, f)

            # Save metadata
            metadata = {
                "strategy": strategy,
                "score": score,
                "timestamp": datetime.utcnow().isoformat(),
                "samples_trained": len(model.feature_importances_),
            }

            metadata_file = os.path.join(
                self.model_dir, f"{strategy.lower()}_metadata.json"
            )
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"Model saved: {model_file}")

        except Exception as e:
            logger.error(f"Error saving model: {e}")

    def _get_last_train_time(self, strategy: str) -> Optional[datetime]:
        """Get the last training timestamp"""
        try:
            if os.path.exists(self.last_train_file):
                with open(self.last_train_file, "r") as f:
                    data = json.load(f)
                    if strategy in data:
                        return datetime.fromisoformat(data[strategy])
            return None
        except Exception as e:
            logger.error(f"Error reading last train time: {e}")
            return None

    def _update_last_train_time(self, strategy: str):
        """Update the last training timestamp"""
        try:
            data = {}
            if os.path.exists(self.last_train_file):
                with open(self.last_train_file, "r") as f:
                    data = json.load(f)

            data[strategy] = datetime.utcnow().isoformat()

            with open(self.last_train_file, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Error updating last train time: {e}")

    def retrain_all_strategies(self) -> Dict[str, str]:
        """Retrain all strategies and return status for each"""
        results = {}

        for strategy in ["DCA", "SWING", "CHANNEL"]:
            logger.info(f"Checking {strategy} for retraining...")
            results[strategy] = self.retrain(strategy)

        return results
