"""
Simple Model Retrainer for Continuous ML Improvement
Retrains models using Freqtrade trade data and scan_history
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
import sqlite3
from pathlib import Path


class SimpleRetrainer:
    """Simple retrainer that updates models when enough new Freqtrade data is available"""

    def __init__(self, supabase_client, model_dir: str = "models"):
        """
        Initialize the retrainer

        Args:
            supabase_client: Supabase client for database access
            model_dir: Directory where models are stored
        """
        # Handle both direct client and wrapper
        if hasattr(supabase_client, "client"):
            self.supabase = supabase_client.client  # Our wrapper
        else:
            self.supabase = supabase_client  # Direct client
        self.model_dir = model_dir
        self.min_new_samples = 20  # Minimum new trades to trigger retraining
        self.retrain_frequency = "daily"
        self.last_train_file = os.path.join(model_dir, "freqtrade_last_train.json")
        
        # Freqtrade database path
        self.freqtrade_db = Path.home() / "crypto-tracker-v3" / "freqtrade" / "user_data" / "tradesv3.dryrun.sqlite"

    def should_retrain(self, strategy: str = "CHANNEL") -> Tuple[bool, int]:
        """
        Check if we should retrain the model

        Args:
            strategy: Strategy to check (for Freqtrade, mainly CHANNEL)

        Returns:
            Tuple of (should_retrain, new_sample_count)
        """
        try:
            # Get last training timestamp
            last_train_time = self._get_last_train_time(strategy)

            # Check synced Freqtrade trades
            query = self.supabase.table("freqtrade_trades").select("*", count="exact")
            query = query.eq("is_open", False)  # Only closed trades
            
            if last_train_time:
                query = query.gte("close_date", last_train_time.isoformat())
            
            result = query.execute()
            new_outcomes = result.count if hasattr(result, "count") else 0

            logger.info(
                f"Found {new_outcomes} new completed trades for {strategy} since last training"
            )

            return new_outcomes >= self.min_new_samples, new_outcomes

        except Exception as e:
            logger.error(f"Error checking retrain status: {e}")
            return False, 0

    def retrain(self, strategy: str = "CHANNEL") -> str:
        """
        Retrain the model if conditions are met

        Args:
            strategy: Strategy to retrain (for Freqtrade, mainly CHANNEL)

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
            # Get all training data from Freqtrade
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
                # Check if feature dimensions match
                try:
                    current_score = self._validate_model(current_model, X_val, y_val)
                    logger.info(
                        f"Current model score: {current_score:.3f}, New model score: {new_score:.3f}"
                    )

                    # Only update if new model is significantly better (2% improvement threshold)
                    improvement_threshold = 0.02
                    if new_score > (current_score + improvement_threshold):
                        # Save new model
                        self._save_model(new_model, strategy, new_score)
                        self._update_last_train_time(strategy)
                        return f"Model updated (improvement: {new_score:.3f} > {current_score:.3f})"
                    else:
                        return (
                            f"Kept existing model (current: {current_score:.3f}, "
                            f"new: {new_score:.3f}, threshold: {improvement_threshold:.1%})"
                        )
                except Exception as e:
                    if "Feature shape mismatch" in str(
                        e
                    ) or "feature_names mismatch" in str(e):
                        logger.warning(
                            f"Legacy model has incompatible features. Score new model: {new_score:.3f}"
                        )
                        logger.warning(
                            "Consider manual review before replacing legacy model"
                        )
                        # Use reasonable threshold for legacy model replacement
                        if new_score > 0.65:  # More reasonable threshold for updates
                            self._save_model(new_model, strategy, new_score)
                            self._update_last_train_time(strategy)
                            return f"Legacy model replaced with high-scoring new model (score: {new_score:.3f})"
                        else:
                            return f"Kept legacy model (feature mismatch, new score {new_score:.3f} < 0.65 threshold)"
                    else:
                        raise
            else:
                # No existing model, save the new one
                self._save_model(new_model, strategy, new_score)
                self._update_last_train_time(strategy)
                return f"Initial model trained (score: {new_score:.3f})"

        except Exception as e:
            logger.error(f"Error during retraining: {e}")
            return f"Retraining failed: {str(e)}"

    def _get_all_training_data(self, strategy: str) -> pd.DataFrame:
        """Get all training data from synced Freqtrade trades"""
        
        try:
            # Get closed trades from freqtrade_trades table
            result = self.supabase.table("freqtrade_trades")\
                .select("*")\
                .eq("is_open", False)\
                .order("close_date", desc=True)\
                .execute()
            
            if not result.data:
                logger.warning("No closed trades found in freqtrade_trades table")
                return pd.DataFrame()
            
            trades_df = pd.DataFrame(result.data)
            
            # Convert timestamps
            trades_df['entry_time'] = pd.to_datetime(trades_df['open_date'])
            trades_df['exit_time'] = pd.to_datetime(trades_df['close_date'])
            
            # Create outcome label
            trades_df['outcome_label'] = trades_df['close_profit'].apply(
                lambda x: 'WIN' if x > 0 else 'LOSS'
            )
            
            # Rename columns to match expected format
            trades_df['profit_pct'] = trades_df['close_profit']
            trades_df['profit_abs'] = trades_df['close_profit_abs']
            trades_df['exit_reason'] = trades_df['sell_reason']
            trades_df['entry_price'] = trades_df['open_rate']
            trades_df['exit_price'] = trades_df['close_rate']
            
            # Get scan features for each trade
            logger.info(f"Fetching scan features for {len(trades_df)} trades...")
            for idx, trade in trades_df.iterrows():
                features = self._get_scan_features_for_trade(
                    trade['symbol'], 
                    trade['entry_time']
                )
                trades_df.at[idx, 'features'] = features
            
            # Set strategy name (all Freqtrade trades use CHANNEL for now)
            trades_df['strategy_name'] = strategy
            
            logger.info(f"Loaded {len(trades_df)} Freqtrade trades with features")
            return trades_df
            
        except Exception as e:
            logger.error(f"Error loading Freqtrade data: {e}")
            return pd.DataFrame()
    
    def _get_scan_features_for_trade(self, symbol: str, entry_time) -> dict:
        """Get scan features from scan_history for a specific trade"""
        try:
            # Get scans around trade entry (24 hours before to capture market context)
            start_time = (entry_time - timedelta(hours=24)).isoformat()
            end_time = entry_time.isoformat()
            
            # Get the most recent scan before trade entry
            result = self.supabase.table("scan_history")\
                .select("*")\
                .eq("symbol", symbol)\
                .gte("timestamp", start_time)\
                .lte("timestamp", end_time)\
                .order("timestamp", desc=True)\
                .limit(1)\
                .execute()
            
            if result.data:
                scan = result.data[0]
                
                # Extract comprehensive features for ML
                features = {
                    # Bollinger Band features (for CHANNEL strategy)
                    "channel_position": scan.get('bb_position', 0.5),
                    "channel_width": (scan.get('bb_upper', 0) - scan.get('bb_lower', 0)) / scan.get('bb_middle', 1) if scan.get('bb_middle', 0) > 0 else 0,
                    
                    # Volume features
                    "volume_profile": scan.get('volume_24h', 0) / 1e6,  # Normalize to millions
                    "volume_ratio": scan.get('volume_ratio', 1.0),
                    
                    # Price action features
                    "range_strength": abs(scan.get('price_change_24h', 0)),
                    "price_drop": scan.get('price_drop_pct', 0),
                    
                    # Momentum indicators
                    "rsi": scan.get('rsi', 50),
                    "mean_reversion_score": (50 - abs(scan.get('rsi', 50) - 50)) / 50,  # 0-1 score
                    
                    # MACD features
                    "macd": scan.get('macd', 0),
                    "macd_signal": scan.get('macd_signal', 0),
                    "macd_histogram": scan.get('macd_histogram', 0),
                    
                    # Market regime
                    "market_regime": 1 if scan.get('price_change_24h', 0) > 0 else -1,
                    
                    # Additional context
                    "btc_correlation": scan.get('btc_correlation', 0),
                    "distance_from_support": scan.get('distance_from_support', 0),
                    "breakout_strength": scan.get('breakout_strength', 0),
                    "trend_alignment": scan.get('trend_alignment', 0),
                    "momentum_score": scan.get('momentum_score', 0),
                    "resistance_cleared": scan.get('resistance_cleared', 0),
                }
                
                return features
            
            # Return default features if no scan found
            logger.warning(f"No scan found for {symbol} at {entry_time}")
            return self._get_default_features()
            
        except Exception as e:
            logger.error(f"Error getting scan features: {e}")
            return self._get_default_features()
    
    def _get_default_features(self) -> dict:
        """Return default feature values when scan data is missing"""
        return {
            "channel_position": 0.5,
            "channel_width": 0,
            "volume_profile": 0,
            "volume_ratio": 1.0,
            "range_strength": 0,
            "price_drop": 0,
            "rsi": 50,
            "mean_reversion_score": 0,
            "macd": 0,
            "macd_signal": 0,
            "macd_histogram": 0,
            "market_regime": 0,
            "btc_correlation": 0,
            "distance_from_support": 0,
            "breakout_strength": 0,
            "trend_alignment": 0,
            "momentum_score": 0,
            "resistance_cleared": 0,
        }

    def _prepare_features_labels(
        self, data: pd.DataFrame, strategy: str
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare features and labels for training"""
        features_list = []
        labels_list = []

        for _, row in data.iterrows():
            # Extract features based on strategy
            # For Freqtrade, we use all available features
            if strategy == "CHANNEL":
                features = [
                    row.get("features", {}).get("channel_position", 0),
                    row.get("features", {}).get("channel_width", 0),
                    row.get("features", {}).get("volume_profile", 0),
                    row.get("features", {}).get("range_strength", 0),
                    row.get("features", {}).get("mean_reversion_score", 0),
                    row.get("features", {}).get("market_regime", 0),
                    row.get("features", {}).get("rsi", 50),
                    row.get("features", {}).get("macd_histogram", 0),
                ]
            elif strategy == "DCA":
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
            else:
                # Default to CHANNEL features
                features = [
                    row.get("features", {}).get("channel_position", 0),
                    row.get("features", {}).get("channel_width", 0),
                    row.get("features", {}).get("volume_profile", 0),
                    row.get("features", {}).get("range_strength", 0),
                    row.get("features", {}).get("mean_reversion_score", 0),
                    row.get("features", {}).get("market_regime", 0),
                ]

            features_list.append(features)
            
            # Convert string labels to numeric for XGBoost
            # 'WIN' -> 1, 'LOSS' -> 0
            label = 1 if row["outcome_label"] == "WIN" else 0
            labels_list.append(label)

        return np.array(features_list), np.array(labels_list)

    def _train_model(
        self, X_train: np.ndarray, y_train: np.ndarray, strategy: str
    ) -> xgb.XGBClassifier:
        """Train an XGBoost model"""
        # Use consistent parameters for reproducibility
        model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            objective="binary:logistic",
            use_label_encoder=False,
            eval_metric="logloss",
            random_state=42,
        )

        model.fit(X_train, y_train, verbose=False)
        return model

    def _validate_model(
        self, model: xgb.XGBClassifier, X_val: np.ndarray, y_val: np.ndarray
    ) -> float:
        """Validate model and return accuracy score"""
        y_pred = model.predict(X_val)
        return accuracy_score(y_val, y_pred)

    def _load_current_model(self, strategy: str) -> Optional[xgb.XGBClassifier]:
        """Load the current model for a strategy"""
        # Try new model location first
        model_path = os.path.join(self.model_dir, strategy.lower(), "classifier.pkl")
        
        if os.path.exists(model_path):
            try:
                with open(model_path, "rb") as f:
                    return pickle.load(f)
            except Exception as e:
                logger.error(f"Error loading model from {model_path}: {e}")
        
        # Try legacy model location
        legacy_path = os.path.join(self.model_dir, f"{strategy.lower()}_model.pkl")
        if os.path.exists(legacy_path):
            try:
                with open(legacy_path, "rb") as f:
                    return pickle.load(f)
            except Exception as e:
                logger.error(f"Error loading legacy model from {legacy_path}: {e}")
        
        return None

    def _save_model(
        self, model: xgb.XGBClassifier, strategy: str, score: float
    ) -> None:
        """Save a trained model"""
        # Create strategy directory if it doesn't exist
        strategy_dir = os.path.join(self.model_dir, strategy.lower())
        os.makedirs(strategy_dir, exist_ok=True)

        # Save model
        model_path = os.path.join(strategy_dir, "classifier.pkl")
        with open(model_path, "wb") as f:
            pickle.dump(model, f)

        # Save metadata
        metadata = {
            "trained_at": datetime.now().isoformat(),
            "accuracy": score,
            "model_type": "XGBClassifier",
            "features_count": model.n_features_in_,
            "data_source": "freqtrade",
        }

        metadata_path = os.path.join(strategy_dir, "training_results.json")
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Model saved to {model_path} with score {score:.3f}")

    def _get_last_train_time(self, strategy: str) -> Optional[datetime]:
        """Get the last training timestamp for a strategy"""
        if not os.path.exists(self.last_train_file):
            return None

        try:
            with open(self.last_train_file, "r") as f:
                last_trains = json.load(f)
                if strategy in last_trains:
                    return datetime.fromisoformat(last_trains[strategy])
        except Exception as e:
            logger.error(f"Error reading last train time: {e}")

        return None

    def _update_last_train_time(self, strategy: str) -> None:
        """Update the last training timestamp"""
        try:
            # Load existing timestamps
            if os.path.exists(self.last_train_file):
                with open(self.last_train_file, "r") as f:
                    last_trains = json.load(f)
            else:
                last_trains = {}

            # Update for this strategy
            last_trains[strategy] = datetime.now().isoformat()

            # Save back
            os.makedirs(os.path.dirname(self.last_train_file), exist_ok=True)
            with open(self.last_train_file, "w") as f:
                json.dump(last_trains, f, indent=2)

        except Exception as e:
            logger.error(f"Error updating last train time: {e}")

    def retrain_all_strategies(self) -> Dict[str, str]:
        """
        Check and retrain all strategies if needed
        
        For Freqtrade, we focus on CHANNEL strategy
        """
        results = {}
        
        # With Freqtrade, we primarily use CHANNEL strategy
        # But we can still maintain models for DCA and SWING for future use
        for strategy in ["CHANNEL"]:
            logger.info(f"Checking {strategy} strategy...")
            result = self.retrain(strategy)
            results[strategy] = result

        return results