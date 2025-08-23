#!/usr/bin/env python3
"""
Train ML model for Channel Trading Strategy
Uses XGBoost to predict channel trade success and optimal parameters
"""

import json
import numpy as np
import pandas as pd
import pickle
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.metrics import mean_squared_error, mean_absolute_error
import xgboost as xgb
from loguru import logger
import sys
import os

sys.path.append(".")

# Configure logger
logger.add("logs/channel_model_training.log", rotation="10 MB")


class ChannelModelTrainer:
    """Train ML model for Channel strategy optimization"""

    def __init__(self):
        self.scaler = StandardScaler()
        self.models = {}

    def load_labels(self, filepath: str = "data/channel_labels.json") -> pd.DataFrame:
        """Load channel training labels"""
        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            labels = data["labels"]
            logger.info(f"Loaded {len(labels)} channel labels")

            # Convert to DataFrame
            df = pd.DataFrame(labels)

            # Extract features from nested dict
            if "features" in df.columns:
                features_df = pd.json_normalize(df["features"])
                df = pd.concat([df, features_df], axis=1)
                df = df.drop("features", axis=1)

            return df

        except Exception as e:
            logger.error(f"Error loading labels: {e}")
            return pd.DataFrame()

    def prepare_features(self, df: pd.DataFrame) -> tuple:
        """Prepare features and targets for training"""

        # Features to use
        feature_columns = [
            "range_width",
            "position_in_range",
            "resistance_touches",
            "support_touches",
            "total_touches",
            "volatility",
            "volume_trend",
            "risk_reward",
        ]

        # Ensure all features exist
        for col in feature_columns:
            if col not in df.columns:
                logger.warning(f"Missing feature: {col}")
                df[col] = 0

        X = df[feature_columns].values

        # Binary target: WIN vs NOT WIN
        y_binary = (df["outcome"] == "WIN").astype(int)

        # Regression targets for optimization
        y_optimal_tp = []
        y_optimal_sl = []
        y_hold_time = []

        for _, row in df.iterrows():
            if row["outcome"] == "WIN":
                # Use actual successful targets
                y_optimal_tp.append(abs(row["actual_pnl_pct"]))
                y_optimal_sl.append(abs((row["stop_loss"] - row["entry_price"]) / row["entry_price"] * 100))
                y_hold_time.append(row.get("exit_bars", 24))
            else:
                # For losses, suggest better targets based on max profit
                max_profit = row.get("max_profit_pct", 5)
                max_loss = abs(row.get("max_loss_pct", -3))

                # Conservative targets for failed trades
                y_optimal_tp.append(min(max_profit * 0.7, 5) if max_profit > 0 else 3)
                y_optimal_sl.append(min(max_loss * 0.8, 3) if max_loss > 0 else 2)
                y_hold_time.append(min(row.get("exit_bars", 48), 48))

        return (
            X,
            y_binary,
            np.array(y_optimal_tp),
            np.array(y_optimal_sl),
            np.array(y_hold_time),
        )

    def train_models(self, X, y_binary, y_tp, y_sl, y_hold):
        """Train multiple models for different predictions"""

        # Split data
        (
            X_train,
            X_test,
            y_binary_train,
            y_binary_test,
            y_tp_train,
            y_tp_test,
            y_sl_train,
            y_sl_test,
            y_hold_train,
            y_hold_test,
        ) = train_test_split(X, y_binary, y_tp, y_sl, y_hold, test_size=0.2, random_state=42)

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        logger.info(f"Training set size: {len(X_train)}")
        logger.info(f"Test set size: {len(X_test)}")
        logger.info(f"Win rate in training: {y_binary_train.mean():.1%}")

        # 1. Binary classifier for trade selection
        logger.info("Training binary classifier for trade selection...")
        clf = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42,
            use_label_encoder=False,
        )
        clf.fit(X_train_scaled, y_binary_train)

        # Evaluate classifier
        y_pred = clf.predict(X_test_scaled)
        y_prob = clf.predict_proba(X_test_scaled)[:, 1]

        accuracy = accuracy_score(y_binary_test, y_pred)
        precision = precision_score(y_binary_test, y_pred, zero_division=0)
        recall = recall_score(y_binary_test, y_pred, zero_division=0)
        f1 = f1_score(y_binary_test, y_pred, zero_division=0)

        logger.info(f"Binary Classifier Performance:")
        logger.info(f"  Accuracy: {accuracy:.3f}")
        logger.info(f"  Precision: {precision:.3f}")
        logger.info(f"  Recall: {recall:.3f}")
        logger.info(f"  F1 Score: {f1:.3f}")

        # Find optimal confidence threshold
        thresholds = np.arange(0.3, 0.8, 0.05)
        best_threshold = 0.5
        best_f1 = 0

        for threshold in thresholds:
            y_pred_thresh = (y_prob >= threshold).astype(int)
            f1_thresh = f1_score(y_binary_test, y_pred_thresh, zero_division=0)
            if f1_thresh > best_f1:
                best_f1 = f1_thresh
                best_threshold = threshold

        logger.info(f"  Optimal threshold: {best_threshold:.2f} (F1: {best_f1:.3f})")

        self.models["classifier"] = clf
        self.models["confidence_threshold"] = best_threshold

        # 2. Regression model for take profit optimization
        logger.info("Training take profit optimizer...")
        tp_model = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42)
        tp_model.fit(X_train_scaled, y_tp_train)

        y_tp_pred = tp_model.predict(X_test_scaled)
        tp_mae = mean_absolute_error(y_tp_test, y_tp_pred)
        tp_rmse = np.sqrt(mean_squared_error(y_tp_test, y_tp_pred))

        logger.info(f"Take Profit Model Performance:")
        logger.info(f"  MAE: {tp_mae:.2f}%")
        logger.info(f"  RMSE: {tp_rmse:.2f}%")

        self.models["tp_optimizer"] = tp_model

        # 3. Regression model for stop loss optimization
        logger.info("Training stop loss optimizer...")
        sl_model = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42)
        sl_model.fit(X_train_scaled, y_sl_train)

        y_sl_pred = sl_model.predict(X_test_scaled)
        sl_mae = mean_absolute_error(y_sl_test, y_sl_pred)
        sl_rmse = np.sqrt(mean_squared_error(y_sl_test, y_sl_pred))

        logger.info(f"Stop Loss Model Performance:")
        logger.info(f"  MAE: {sl_mae:.2f}%")
        logger.info(f"  RMSE: {sl_rmse:.2f}%")

        self.models["sl_optimizer"] = sl_model

        # 4. Regression model for hold time prediction
        logger.info("Training hold time predictor...")
        hold_model = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42)
        hold_model.fit(X_train_scaled, y_hold_train)

        y_hold_pred = hold_model.predict(X_test_scaled)
        hold_mae = mean_absolute_error(y_hold_test, y_hold_pred)

        logger.info(f"Hold Time Model Performance:")
        logger.info(f"  MAE: {hold_mae:.1f} bars")

        self.models["hold_predictor"] = hold_model

        # Feature importance
        feature_names = [
            "range_width",
            "position_in_range",
            "resistance_touches",
            "support_touches",
            "total_touches",
            "volatility",
            "volume_trend",
            "risk_reward",
        ]

        feature_importance = clf.feature_importances_
        # Ensure arrays have same length
        if len(feature_importance) != len(feature_names):
            logger.warning(f"Feature importance length mismatch: {len(feature_importance)} vs {len(feature_names)}")
            feature_importance = feature_importance[: len(feature_names)]

        importance_df = pd.DataFrame({"feature": feature_names, "importance": list(feature_importance)}).sort_values(
            "importance", ascending=False
        )

        logger.info("\nFeature Importance (Binary Classifier):")
        for _, row in importance_df.iterrows():
            logger.info(f"  {row['feature']}: {row['importance']:.3f}")

        return {
            "accuracy": float(accuracy),
            "precision": float(precision),
            "recall": float(recall),
            "f1_score": float(f1),
            "confidence_threshold": float(best_threshold),
            "tp_mae": float(tp_mae),
            "sl_mae": float(sl_mae),
            "hold_mae": float(hold_mae),
            "feature_importance": importance_df.to_dict("records"),
        }

    def save_models(self, output_dir: str = "models/channel"):
        """Save trained models and scaler"""
        os.makedirs(output_dir, exist_ok=True)

        # Save models
        with open(f"{output_dir}/classifier.pkl", "wb") as f:
            pickle.dump(self.models["classifier"], f)

        with open(f"{output_dir}/tp_optimizer.pkl", "wb") as f:
            pickle.dump(self.models["tp_optimizer"], f)

        with open(f"{output_dir}/sl_optimizer.pkl", "wb") as f:
            pickle.dump(self.models["sl_optimizer"], f)

        with open(f"{output_dir}/hold_predictor.pkl", "wb") as f:
            pickle.dump(self.models["hold_predictor"], f)

        # Save scaler
        with open(f"{output_dir}/scaler.pkl", "wb") as f:
            pickle.dump(self.scaler, f)

        # Save configuration
        config = {
            "confidence_threshold": self.models.get("confidence_threshold", 0.5),
            "feature_columns": [
                "range_width",
                "position_in_range",
                "resistance_touches",
                "support_touches",
                "total_touches",
                "volatility",
                "volume_trend",
                "risk_reward",
            ],
            "trained_at": datetime.now().isoformat(),
        }

        with open(f"{output_dir}/config.json", "w") as f:
            json.dump(config, f, indent=2)

        logger.info(f"Models saved to {output_dir}/")

    def train(self):
        """Main training pipeline"""
        logger.info("Starting Channel ML Model Training")
        logger.info("=" * 60)

        # Load labels
        df = self.load_labels()

        if df.empty:
            logger.error("No labels to train on!")
            return

        logger.info(f"Dataset statistics:")
        logger.info(f"  Total samples: {len(df)}")
        logger.info(f"  Win rate: {(df['outcome'] == 'WIN').mean():.1%}")
        logger.info(f"  Avg risk/reward: {df['risk_reward'].mean():.2f}")

        # Prepare features
        X, y_binary, y_tp, y_sl, y_hold = self.prepare_features(df)

        # Train models
        results = self.train_models(X, y_binary, y_tp, y_sl, y_hold)

        # Save models
        self.save_models()

        # Save training results
        with open("models/channel/training_results.json", "w") as f:
            json.dump(results, f, indent=2)

        logger.info("\n" + "=" * 60)
        logger.info("✅ Channel ML Model Training Complete!")
        logger.info(f"Models saved to models/channel/")
        logger.info(f"Binary classifier accuracy: {results['accuracy']:.1%}")
        logger.info(f"Optimal confidence threshold: {results['confidence_threshold']:.2f}")


def main():
    trainer = ChannelModelTrainer()
    trainer.train()


if __name__ == "__main__":
    main()
