"""
Shadow-Enhanced Model Retrainer
Incorporates shadow trading data into ML model training with weighted samples
"""

import os
import pickle
import json
from datetime import datetime
from typing import Dict, Tuple, Optional
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
import xgboost as xgb
from loguru import logger


class ShadowEnhancedRetrainer:
    """
    Enhanced retrainer that uses both real and shadow trade data
    Implements graduated weighting based on shadow quality
    """

    def __init__(self, supabase_client, model_dir: str = "models"):
        """
        Initialize the enhanced retrainer

        Args:
            supabase_client: Supabase client for database access
            model_dir: Directory where models are stored
        """
        self.supabase = supabase_client
        self.model_dir = model_dir
        self.min_real_trades = 5  # Minimum real trades required
        self.min_total_samples = 50  # Minimum total samples for training
        self.max_shadow_ratio = 20  # Maximum 20:1 shadow to real ratio
        self.improvement_threshold = 0.02  # 2% improvement required to deploy
        self.last_train_file = os.path.join(model_dir, "last_train_shadow.json")

    def should_retrain(self, strategy: str = "DCA") -> Tuple[bool, Dict]:
        """
        Check if we should retrain with shadow data

        Returns:
            Tuple of (should_retrain, statistics)
        """
        try:
            # Count real trades
            real_count = self._count_real_trades(strategy)

            # Count shadow trades
            shadow_count = self._count_shadow_trades(strategy)

            # Calculate effective sample size
            effective_samples = self._calculate_effective_samples(
                real_count, shadow_count
            )

            stats = {
                "real_trades": real_count,
                "shadow_trades": shadow_count,
                "effective_samples": effective_samples,
                "shadow_ratio": shadow_count / max(real_count, 1),
                "can_retrain": real_count >= self.min_real_trades
                and effective_samples >= self.min_total_samples,
            }

            logger.info(
                f"{strategy} - Real: {real_count}, Shadow: {shadow_count}, "
                f"Effective: {effective_samples:.1f}, Can retrain: {stats['can_retrain']}"
            )

            return stats["can_retrain"], stats

        except Exception as e:
            logger.error(f"Error checking retrain status: {e}")
            return False, {}

    def retrain_with_shadows(self, strategy: str = "DCA") -> Dict:
        """
        Retrain model using both real and shadow data

        Returns:
            Dictionary with training results
        """
        # Check if we should retrain
        should_retrain, stats = self.should_retrain(strategy)

        if not should_retrain:
            return {
                "status": "skipped",
                "reason": f"Insufficient data - Real: {stats.get('real_trades', 0)}, "
                f"Effective: {stats.get('effective_samples', 0):.1f}",
                "stats": stats,
            }

        logger.info(f"Starting shadow-enhanced retraining for {strategy}")

        try:
            # Get real training data
            real_data = self._get_real_training_data(strategy)

            # Get shadow training data
            shadow_data = self._get_shadow_training_data(strategy, len(real_data))

            # Combine with weights
            combined_data = self._combine_training_data(real_data, shadow_data)

            logger.info(
                f"Combined training data: {len(real_data)} real + {len(shadow_data)} shadow "
                f"= {len(combined_data)} total samples"
            )

            # Prepare features and labels
            X, y, sample_weights = self._prepare_features_labels(
                combined_data, strategy
            )

            # Add shadow consensus features
            X = self._add_shadow_features(X, combined_data)

            # Split for validation (stratified by real vs shadow)
            X_train, X_val, y_train, y_val, w_train, w_val = self._split_with_weights(
                X, y, sample_weights, test_size=0.2
            )

            # Train new model
            new_model = self._train_model(X_train, y_train, w_train, strategy)

            # Validate new model
            new_metrics = self._validate_model(new_model, X_val, y_val, w_val)

            # Compare with current model
            improvement = self._compare_with_current(new_model, X_val, y_val, strategy)

            result = {
                "status": "success",
                "strategy": strategy,
                "real_samples": len(real_data),
                "shadow_samples": len(shadow_data),
                "metrics": new_metrics,
                "improvement": improvement,
            }

            if improvement and improvement > self.improvement_threshold:
                # Save new model
                self._save_model(new_model, strategy, new_metrics)
                self._update_metadata(strategy, result)
                result["action"] = "deployed"
                result["message"] = f"Model updated with {improvement:.1%} improvement"
                logger.info(
                    f"✅ Deployed new {strategy} model with {improvement:.1%} improvement"
                )
            else:
                result["action"] = "rejected"
                result[
                    "message"
                ] = f"Insufficient improvement ({improvement:.1%} < {self.improvement_threshold:.1%})"
                logger.info(
                    f"❌ Kept existing {strategy} model (improvement only {improvement:.1%})"
                )

            return result

        except Exception as e:
            logger.error(f"Error during shadow-enhanced retraining: {e}")
            return {"status": "error", "error": str(e), "strategy": strategy}

    def _count_real_trades(self, strategy: str) -> int:
        """Count completed real trades"""
        try:
            result = (
                self.supabase.table("trade_logs")
                .select("trade_id", count="exact")
                .eq("strategy_name", strategy)
                .in_("status", ["CLOSED_WIN", "CLOSED_LOSS"])
                .execute()
            )

            return result.count if hasattr(result, "count") else len(result.data)

        except Exception as e:
            logger.error(f"Error counting real trades: {e}")
            return 0

    def _count_shadow_trades(self, strategy: str) -> int:
        """Count evaluated shadow trades"""
        try:
            # Complex query through joins
            result = self.supabase.rpc(
                "count_shadow_trades_by_strategy", {"p_strategy": strategy}
            ).execute()

            if result.data and len(result.data) > 0:
                return result.data[0].get("count", 0)

            # Fallback to direct count
            result = (
                self.supabase.table("shadow_outcomes")
                .select("outcome_id", count="exact")
                .neq("outcome_status", "PENDING")
                .execute()
            )

            return result.count if hasattr(result, "count") else 0

        except Exception as e:
            logger.error(f"Error counting shadow trades: {e}")
            return 0

    def _calculate_effective_samples(self, real_count: int, shadow_count: int) -> float:
        """
        Calculate effective sample size considering shadow weights
        Average shadow weight is ~0.3, so effective = real + (shadow * 0.3)
        """
        avg_shadow_weight = 0.3  # Conservative estimate
        capped_shadows = min(shadow_count, real_count * self.max_shadow_ratio)
        return real_count + (capped_shadows * avg_shadow_weight)

    def _get_real_training_data(self, strategy: str) -> pd.DataFrame:
        """Get real trade training data"""
        try:
            # Use the ml_training_feedback view
            result = (
                self.supabase.table("ml_training_feedback")
                .select("*")
                .eq("strategy_name", strategy)
                .not_.is_("outcome_label", "null")
                .execute()
            )

            if result.data:
                df = pd.DataFrame(result.data)
                df["is_shadow"] = False
                df["sample_weight"] = 1.0  # Real trades get weight 1.0
                return df

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error getting real training data: {e}")
            return pd.DataFrame()

    def _get_shadow_training_data(self, strategy: str, real_count: int) -> pd.DataFrame:
        """Get shadow trade training data"""
        try:
            # Limit shadows based on ratio
            max_shadows = real_count * self.max_shadow_ratio

            # Use the ml_training_with_shadows view
            result = (
                self.supabase.table("ml_training_with_shadows")
                .select("*")
                .eq("strategy_name", strategy)
                .not_.is_("best_shadow_status", "null")
                .limit(int(max_shadows))
                .execute()
            )

            if result.data:
                df = pd.DataFrame(result.data)
                df["is_shadow"] = True

                # Calculate dynamic weights for each shadow
                df["sample_weight"] = df.apply(
                    lambda row: self._calculate_shadow_weight(row), axis=1
                )

                return df

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error getting shadow training data: {e}")
            return pd.DataFrame()

    def _calculate_shadow_weight(self, shadow_row: pd.Series) -> float:
        """
        Calculate weight for a shadow sample based on quality factors
        """
        base_weight = 0.1

        # Factor 1: Shadow consensus (how many shadows agreed)
        if (
            "shadow_consensus_score" in shadow_row
            and shadow_row["shadow_consensus_score"]
        ):
            if shadow_row["shadow_consensus_score"] > 0.7:  # 70% agreement
                base_weight += 0.1

        # Factor 2: Performance delta (is this variation performing well)
        if (
            "shadow_performance_delta" in shadow_row
            and shadow_row["shadow_performance_delta"]
        ):
            if shadow_row["shadow_performance_delta"] > 0.05:  # 5% better
                base_weight += 0.1

        # Factor 3: Did shadow match reality (for validation)
        if "real_status" in shadow_row and "best_shadow_status" in shadow_row:
            if shadow_row["real_status"] == shadow_row["best_shadow_status"]:
                base_weight += 0.2

        # Factor 4: Statistical significance
        if (
            "shadow_avg_confidence" in shadow_row
            and shadow_row["shadow_avg_confidence"]
        ):
            if shadow_row["shadow_avg_confidence"] > 0.65:
                base_weight += 0.1

        return min(base_weight, 0.5)  # Cap at 0.5

    def _combine_training_data(
        self, real_data: pd.DataFrame, shadow_data: pd.DataFrame
    ) -> pd.DataFrame:
        """Combine real and shadow data"""
        if real_data.empty:
            return pd.DataFrame()

        if shadow_data.empty:
            return real_data

        # Combine dataframes
        combined = pd.concat([real_data, shadow_data], ignore_index=True)

        # Sort by timestamp to maintain temporal order
        if "scan_time" in combined.columns:
            combined = combined.sort_values("scan_time")

        return combined

    def _prepare_features_labels(
        self, data: pd.DataFrame, strategy: str
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Prepare features, labels, and sample weights
        """
        # Parse features from JSON if needed
        if "scan_features" in data.columns:
            features_df = pd.json_normalize(data["scan_features"].apply(json.loads))
        else:
            # Use numeric columns as features
            feature_cols = data.select_dtypes(include=[np.number]).columns
            feature_cols = [
                c
                for c in feature_cols
                if c not in ["outcome_label", "sample_weight", "is_shadow"]
            ]
            features_df = data[feature_cols]

        # Get labels (1 for win, 0 for loss)
        if "outcome_label" in data.columns:
            # Convert string labels to numeric for XGBoost
            # 'WIN' -> 1, 'LOSS' -> 0
            labels = (
                data["outcome_label"].apply(lambda x: 1 if x == "WIN" else 0).values
            )
        else:
            # Create labels from status
            labels = (data["status"] == "CLOSED_WIN").astype(int).values

        # Get sample weights
        weights = (
            data["sample_weight"].values
            if "sample_weight" in data.columns
            else np.ones(len(data))
        )

        return features_df.values, labels, weights

    def _add_shadow_features(self, X: np.ndarray, data: pd.DataFrame) -> np.ndarray:
        """
        Add shadow-derived features to training data
        """
        shadow_features = []

        # Shadow consensus score
        if "shadow_consensus_score" in data.columns:
            shadow_features.append(
                data["shadow_consensus_score"].fillna(0).values.reshape(-1, 1)
            )

        # Shadow performance delta
        if "shadow_performance_delta" in data.columns:
            shadow_features.append(
                data["shadow_performance_delta"].fillna(0).values.reshape(-1, 1)
            )

        # Shadow average confidence
        if "shadow_avg_confidence" in data.columns:
            shadow_features.append(
                data["shadow_avg_confidence"].fillna(0).values.reshape(-1, 1)
            )

        if shadow_features:
            shadow_array = np.hstack(shadow_features)
            return np.hstack([X, shadow_array])

        return X

    def _split_with_weights(self, X, y, weights, test_size=0.2):
        """
        Split data while preserving weights
        """
        # Create stratification groups (real vs shadow)
        is_real = weights == 1.0
        stratify_groups = is_real.astype(int) * 2 + y  # Creates 4 groups

        indices = np.arange(len(X))
        train_idx, val_idx = train_test_split(
            indices, test_size=test_size, random_state=42, stratify=stratify_groups
        )

        return (
            X[train_idx],
            X[val_idx],
            y[train_idx],
            y[val_idx],
            weights[train_idx],
            weights[val_idx],
        )

    def _train_model(self, X_train, y_train, sample_weights, strategy: str):
        """
        Train XGBoost model with sample weights
        """
        # Strategy-specific parameters
        params = {
            "DCA": {
                "max_depth": 6,
                "learning_rate": 0.1,
                "n_estimators": 100,
                "objective": "binary:logistic",
                "eval_metric": "auc",
            },
            "SWING": {
                "max_depth": 5,
                "learning_rate": 0.15,
                "n_estimators": 80,
                "objective": "binary:logistic",
                "eval_metric": "auc",
            },
            "CHANNEL": {
                "max_depth": 4,
                "learning_rate": 0.2,
                "n_estimators": 60,
                "objective": "binary:logistic",
                "eval_metric": "auc",
            },
        }

        model_params = params.get(strategy, params["DCA"])

        model = xgb.XGBClassifier(
            **model_params, random_state=42, use_label_encoder=False
        )

        # Train with sample weights
        model.fit(X_train, y_train, sample_weight=sample_weights, verbose=False)

        return model

    def _validate_model(self, model, X_val, y_val, sample_weights) -> Dict:
        """
        Validate model and return metrics
        """
        predictions = model.predict(X_val)
        probabilities = model.predict_proba(X_val)[:, 1]

        # Calculate weighted metrics
        accuracy = accuracy_score(y_val, predictions, sample_weight=sample_weights)
        precision = precision_score(
            y_val, predictions, sample_weight=sample_weights, zero_division=0
        )
        recall = recall_score(
            y_val, predictions, sample_weight=sample_weights, zero_division=0
        )
        auc = roc_auc_score(y_val, probabilities, sample_weight=sample_weights)

        return {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "auc": auc,
            "f1_score": (
                2 * (precision * recall) / (precision + recall)
                if (precision + recall) > 0
                else 0
            ),
        }

    def _compare_with_current(
        self, new_model, X_val, y_val, strategy: str
    ) -> Optional[float]:
        """
        Compare new model with current model
        Returns improvement percentage
        """
        try:
            # Load current model
            model_file = os.path.join(self.model_dir, f"{strategy.lower()}_model.pkl")
            if not os.path.exists(model_file):
                return None  # No existing model

            with open(model_file, "rb") as f:
                current_model = pickle.load(f)

            # Get predictions
            current_probs = current_model.predict_proba(X_val)[:, 1]
            new_probs = new_model.predict_proba(X_val)[:, 1]

            # Compare AUC scores
            current_auc = roc_auc_score(y_val, current_probs)
            new_auc = roc_auc_score(y_val, new_probs)

            improvement = new_auc - current_auc

            logger.info(
                f"Model comparison - Current AUC: {current_auc:.3f}, "
                f"New AUC: {new_auc:.3f}, Improvement: {improvement:.3f}"
            )

            return improvement

        except Exception as e:
            logger.error(f"Error comparing models: {e}")
            return None

    def _save_model(self, model, strategy: str, metrics: Dict):
        """Save model and metadata"""
        try:
            # Save model
            model_file = os.path.join(
                self.model_dir, f"{strategy.lower()}_shadow_model.pkl"
            )
            with open(model_file, "wb") as f:
                pickle.dump(model, f)

            # Save metadata
            metadata = {
                "strategy": strategy,
                "trained_at": datetime.utcnow().isoformat(),
                "metrics": metrics,
                "shadow_enhanced": True,
            }

            metadata_file = os.path.join(
                self.model_dir, f"{strategy.lower()}_shadow_metadata.json"
            )
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"Saved shadow-enhanced model for {strategy}")

        except Exception as e:
            logger.error(f"Error saving model: {e}")

    def _update_metadata(self, strategy: str, result: Dict):
        """Update training metadata"""
        try:
            metadata = {
                "strategy": strategy,
                "last_train": datetime.utcnow().isoformat(),
                "result": result,
            }

            # Update or create metadata file
            if os.path.exists(self.last_train_file):
                with open(self.last_train_file, "r") as f:
                    all_metadata = json.load(f)
            else:
                all_metadata = {}

            all_metadata[strategy] = metadata

            with open(self.last_train_file, "w") as f:
                json.dump(all_metadata, f, indent=2)

        except Exception as e:
            logger.error(f"Error updating metadata: {e}")

    def retrain_all_strategies(self) -> Dict:
        """
        Retrain all strategies with shadow data
        """
        results = {}

        for strategy in ["DCA", "SWING", "CHANNEL"]:
            logger.info(f"\n{'='*60}")
            logger.info(f"Retraining {strategy} with shadow data...")
            logger.info(f"{'='*60}")

            result = self.retrain_with_shadows(strategy)
            results[strategy] = result

            # Log summary
            if result["status"] == "success" and result.get("action") == "deployed":
                logger.info(
                    f"✅ {strategy}: Model updated with {result['improvement']:.1%} improvement"
                )
            elif result["status"] == "success":
                logger.info(
                    f"❌ {strategy}: Model not updated (insufficient improvement)"
                )
            else:
                logger.info(f"⏭️ {strategy}: {result.get('reason', 'Skipped')}")

        return results
