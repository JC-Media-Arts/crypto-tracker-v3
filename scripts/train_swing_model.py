#!/usr/bin/env python3
"""
Train XGBoost model for Swing Trading Strategy
Adheres to MASTER_PLAN.md specifications:
- Model type: XGBoost
- Prediction: breakout_success (binary) + optimal TP/SL parameters
- Features: breakout_strength, volume_profile, resistance_cleared, trend_alignment, momentum_score, market_regime
- Minimum 500 setups, 6-month lookback
- 60/20/20 train/val/test split
"""

import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)
import joblib
from loguru import logger
import warnings

warnings.filterwarnings("ignore")

# Configure logger
logger.add("logs/swing_model_training.log", rotation="10 MB")


class SwingModelTrainer:
    def __init__(self):
        self.model_dir = Path("models/swing")
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = Path("data")

        # From MASTER_PLAN.md
        self.min_samples = 500  # Minimum required setups
        self.lookback_months = 6
        self.confidence_threshold = 0.65
        self.minimum_accuracy = 0.55

        # TP/SL ranges to test (will find optimal via ML)
        self.tp_range = np.arange(5, 25, 1)  # 5% to 25% in 1% increments
        self.sl_range = np.arange(3, 10, 0.5)  # 3% to 10% in 0.5% increments

    def load_swing_labels(self):
        """Load the generated swing labels"""
        try:
            # Try adaptive labels first (has more data)
            adaptive_path = self.data_dir / "adaptive_swing_labels.json"
            if adaptive_path.exists():
                with open(adaptive_path, "r") as f:
                    data = json.load(f)
                logger.info(f"Loaded {len(data['labels'])} adaptive swing setups")
                return data["labels"]

            # Fallback to regular labels
            regular_path = self.data_dir / "swing_labels.json"
            if regular_path.exists():
                with open(regular_path, "r") as f:
                    data = json.load(f)
                logger.info(f"Loaded {len(data.get('labels', []))} swing setups")
                return data.get("labels", [])

            logger.error("No swing label files found")
            return []

        except Exception as e:
            logger.error(f"Error loading labels: {e}")
            return []

    def calculate_features(self, setups):
        """
        Calculate the 6 required features from MASTER_PLAN.md:
        1. breakout_strength - How strong is the move?
        2. volume_profile - Volume confirmation?
        3. resistance_cleared - Above key levels?
        4. trend_alignment - Multiple timeframes aligned?
        5. momentum_score - RSI, MACD momentum
        6. market_regime - Overall market trend
        """
        features_list = []
        labels_list = []
        optimal_params_list = []

        for setup in setups:
            try:
                features = setup.get("features", {})
                entry_price = setup.get("entry_price", 0)

                # 1. Breakout Strength (using actual breakout_strength or price_change)
                breakout_strength = (
                    features.get("breakout_strength", 0) * 100
                )  # Convert to percentage
                if breakout_strength == 0:
                    breakout_strength = features.get("price_change_24h", 0) * 100

                # 2. Volume Profile (volume surge ratio)
                volume_ratio = features.get("volume_ratio", 1.0)
                volume_profile = min(
                    volume_ratio / 2.0, 1.0
                )  # Normalize to 0-1 (2x volume = 1.0)

                # 3. Resistance Cleared (using breakout strength as proxy)
                # Higher breakout = more resistance cleared
                resistance_cleared = min(
                    breakout_strength / 5.0, 1.0
                )  # Normalize (5% = 1.0)

                # 4. Trend Alignment (using SMA distances)
                dist_sma20 = features.get("distance_from_sma20", 0)
                dist_sma50 = features.get("distance_from_sma50", 0)

                # All positive = uptrend alignment
                trend_score = 0
                if dist_sma20 > 0:
                    trend_score += 0.5
                if dist_sma50 > 0:
                    trend_score += 0.5
                if dist_sma20 > dist_sma50:
                    trend_score += 0.5  # Accelerating trend
                trend_alignment = min(trend_score, 1.0)

                # 5. Momentum Score (RSI + MACD composite)
                rsi = features.get("rsi", 50)
                rsi_normalized = rsi / 100.0  # Normalize to 0-1

                # MACD bullishness
                macd_hist = features.get("macd_histogram", 0)
                macd_bullish = 1.0 if macd_hist > 0 else 0.0

                # Combine RSI and MACD (per MASTER_PLAN: RSI > 60 is good)
                if rsi > 60:
                    rsi_score = min((rsi - 60) / 40, 1.0)  # 60-100 mapped to 0-1
                else:
                    rsi_score = 0

                momentum_score = rsi_score * 0.7 + macd_bullish * 0.3

                # 6. Market Regime (using market_condition or default)
                market_condition = setup.get("market_condition", "neutral")
                if market_condition in ["trending_up", "bullish"]:
                    market_regime = 1.0
                elif market_condition in ["trending_down", "bearish"]:
                    market_regime = -1.0
                else:
                    market_regime = 0.0

                # Create feature vector
                feature_vector = [
                    breakout_strength,
                    volume_profile,
                    resistance_cleared,
                    trend_alignment,
                    momentum_score,
                    market_regime,
                ]

                # Determine optimal TP/SL from historical data
                outcome = setup.get("outcome", "LOSS")
                max_profit = setup.get("max_profit", 0)
                max_loss = setup.get("max_loss", 0)
                tp_used = setup.get("take_profit_pct", 15.0)
                sl_used = abs(setup.get("stop_loss_pct", 5.0))

                # Find optimal TP/SL that would have worked
                if outcome == "WIN":
                    # Use the TP that was hit
                    optimal_tp = tp_used
                    # Could have used tighter stop
                    optimal_sl = (
                        min(abs(max_loss), sl_used) if max_loss < 0 else sl_used
                    )
                elif outcome == "LOSS":
                    # Should have used tighter stop
                    optimal_sl = 3.0  # Tight stop for losses
                    # Would need higher target
                    optimal_tp = 20.0
                else:  # BREAKEVEN
                    # Somewhere in between
                    optimal_tp = max(max_profit, 10.0) if max_profit > 0 else 15.0
                    optimal_sl = min(abs(max_loss), 5.0) if max_loss < 0 else 5.0

                # Binary label for breakout success
                label = 1 if outcome == "WIN" else 0

                features_list.append(feature_vector)
                labels_list.append(label)
                optimal_params_list.append([optimal_tp, optimal_sl])

            except Exception as e:
                logger.warning(f"Error processing setup: {e}")
                continue

        return (
            np.array(features_list),
            np.array(labels_list),
            np.array(optimal_params_list),
        )

    def train_models(self, X, y, optimal_params):
        """Train both binary classifier and parameter optimizer"""

        # Split data (60/20/20 as per MASTER_PLAN)
        X_temp, X_test, y_temp, y_test, params_temp, params_test = train_test_split(
            X, y, optimal_params, test_size=0.2, random_state=42, stratify=y
        )

        X_train, X_val, y_train, y_val, params_train, params_val = train_test_split(
            X_temp,
            y_temp,
            params_temp,
            test_size=0.25,
            random_state=42,
            stratify=y_temp,
        )

        logger.info(f"Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")

        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_val_scaled = scaler.transform(X_val)
        X_test_scaled = scaler.transform(X_test)

        # 1. Train binary classifier for breakout success
        logger.info("Training breakout success classifier...")

        clf_model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            objective="binary:logistic",
            use_label_encoder=False,
            random_state=42,
        )

        clf_model.fit(X_train_scaled, y_train)

        # Evaluate classifier
        y_pred = clf_model.predict(X_test_scaled)
        y_prob = clf_model.predict_proba(X_test_scaled)[:, 1]

        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)

        logger.info(f"Classifier Performance:")
        logger.info(f"  Accuracy: {accuracy:.3f}")
        logger.info(f"  Precision: {precision:.3f}")
        logger.info(f"  Recall: {recall:.3f}")
        logger.info(f"  F1 Score: {f1:.3f}")

        # Check if meets minimum accuracy requirement
        if accuracy < self.minimum_accuracy:
            logger.warning(
                f"Accuracy {accuracy:.3f} below minimum {self.minimum_accuracy}"
            )

        # 2. Train parameter optimizer (multi-output regression)
        logger.info("Training parameter optimizer...")

        param_model = xgb.XGBRegressor(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            objective="reg:squarederror",
            random_state=42,
        )

        # Train separate models for TP and SL
        tp_model = param_model.fit(X_train_scaled, params_train[:, 0])

        sl_model = xgb.XGBRegressor(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            objective="reg:squarederror",
            random_state=42,
        ).fit(X_train_scaled, params_train[:, 1])

        # Feature importance
        feature_names = [
            "breakout_strength",
            "volume_profile",
            "resistance_cleared",
            "trend_alignment",
            "momentum_score",
            "market_regime",
        ]

        importance = clf_model.feature_importances_
        feature_importance = dict(zip(feature_names, importance))

        logger.info("Feature Importance:")
        for feat, imp in sorted(
            feature_importance.items(), key=lambda x: x[1], reverse=True
        ):
            logger.info(f"  {feat}: {imp:.3f}")

        # Save models and scaler
        joblib.dump(clf_model, self.model_dir / "swing_classifier.pkl")
        joblib.dump(tp_model, self.model_dir / "swing_tp_optimizer.pkl")
        joblib.dump(sl_model, self.model_dir / "swing_sl_optimizer.pkl")
        joblib.dump(scaler, self.model_dir / "swing_scaler.pkl")

        # Save training results
        results = {
            "timestamp": datetime.now().isoformat(),
            "total_samples": int(len(X)),
            "train_samples": int(len(X_train)),
            "val_samples": int(len(X_val)),
            "test_samples": int(len(X_test)),
            "accuracy": float(accuracy),
            "precision": float(precision),
            "recall": float(recall),
            "f1_score": float(f1),
            "confidence_threshold": float(self.confidence_threshold),
            "feature_importance": {k: float(v) for k, v in feature_importance.items()},
            "meets_requirements": bool(accuracy >= self.minimum_accuracy),
        }

        with open(self.model_dir / "training_results.json", "w") as f:
            json.dump(results, f, indent=2)

        return clf_model, tp_model, sl_model, scaler, results

    def validate_predictions(
        self, clf_model, tp_model, sl_model, scaler, X, y, optimal_params
    ):
        """Validate model predictions with confidence filtering"""

        X_scaled = scaler.transform(X)

        # Get predictions
        y_prob = clf_model.predict_proba(X_scaled)[:, 1]
        tp_pred = tp_model.predict(X_scaled)
        sl_pred = sl_model.predict(X_scaled)

        # Apply confidence threshold
        high_conf_mask = y_prob >= self.confidence_threshold

        logger.info(
            f"\nValidation with {self.confidence_threshold:.0%} confidence threshold:"
        )
        logger.info(f"  Total predictions: {len(y)}")
        logger.info(
            f"  High confidence predictions: {high_conf_mask.sum()} ({high_conf_mask.mean():.1%})"
        )

        if high_conf_mask.sum() > 0:
            # Calculate accuracy on high confidence predictions
            y_pred_high_conf = (y_prob[high_conf_mask] >= 0.5).astype(int)
            accuracy_high_conf = accuracy_score(y[high_conf_mask], y_pred_high_conf)

            # Calculate average predicted parameters
            avg_tp = tp_pred[high_conf_mask].mean()
            avg_sl = sl_pred[high_conf_mask].mean()

            logger.info(f"  High confidence accuracy: {accuracy_high_conf:.3f}")
            logger.info(f"  Average predicted TP: {avg_tp:.1f}%")
            logger.info(f"  Average predicted SL: {avg_sl:.1f}%")

            # Compare to actual optimal parameters for wins
            win_mask = (y == 1) & high_conf_mask
            if win_mask.sum() > 0:
                actual_tp = optimal_params[win_mask, 0].mean()
                actual_sl = optimal_params[win_mask, 1].mean()
                logger.info(f"  Actual optimal TP for wins: {actual_tp:.1f}%")
                logger.info(f"  Actual optimal SL for wins: {actual_sl:.1f}%")

    def run(self):
        """Main training pipeline"""
        logger.info("=" * 50)
        logger.info("Starting Swing Model Training")
        logger.info(f"Requirements from MASTER_PLAN.md:")
        logger.info(f"  - Minimum samples: {self.min_samples}")
        logger.info(f"  - Lookback: {self.lookback_months} months")
        logger.info(f"  - Confidence threshold: {self.confidence_threshold:.0%}")
        logger.info(f"  - Minimum accuracy: {self.minimum_accuracy:.0%}")
        logger.info("=" * 50)

        # Load data
        setups = self.load_swing_labels()

        if len(setups) < self.min_samples:
            logger.warning(
                f"Only {len(setups)} setups found, need {self.min_samples} minimum"
            )
            logger.info("Consider expanding to more symbols or longer timeframe")

        # Filter by lookback period
        cutoff_date = datetime.now() - timedelta(days=self.lookback_months * 30)
        filtered_setups = []
        for setup in setups:
            try:
                setup_date = datetime.fromisoformat(
                    setup["timestamp"].replace("Z", "+00:00")
                )
                if setup_date >= cutoff_date:
                    filtered_setups.append(setup)
            except:
                filtered_setups.append(setup)  # Keep if can't parse date

        logger.info(
            f"Setups after {self.lookback_months}-month filter: {len(filtered_setups)}"
        )

        if len(filtered_setups) == 0:
            logger.error("No setups found after filtering")
            return

        # Calculate features
        X, y, optimal_params = self.calculate_features(filtered_setups)

        logger.info(f"Features calculated: {X.shape}")
        logger.info(f"Win rate in data: {y.mean():.1%}")

        if len(X) == 0:
            logger.error("No valid features extracted")
            return

        # Train models
        clf_model, tp_model, sl_model, scaler, results = self.train_models(
            X, y, optimal_params
        )

        # Validate with confidence threshold
        self.validate_predictions(
            clf_model, tp_model, sl_model, scaler, X, y, optimal_params
        )

        # Summary
        logger.info("=" * 50)
        logger.info("Training Complete!")
        logger.info(f"Models saved to: {self.model_dir}")
        logger.info(f"Results: {self.model_dir / 'training_results.json'}")

        if results["meets_requirements"]:
            logger.info("✅ Model meets minimum accuracy requirements")
        else:
            logger.warning(
                "⚠️ Model below minimum accuracy - consider more data or feature engineering"
            )

        logger.info("=" * 50)

        return results


if __name__ == "__main__":
    trainer = SwingModelTrainer()
    results = trainer.run()
