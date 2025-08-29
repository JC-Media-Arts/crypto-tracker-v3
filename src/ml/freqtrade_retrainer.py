"""
Freqtrade-specific Model Retrainer
Trains ML models using only Freqtrade-generated scan_history data
"""

import os
import pickle
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Tuple, Optional, List
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
from loguru import logger
import sqlite3
from pathlib import Path


class FreqtradeRetrainer:
    """Retrainer that uses only Freqtrade scan_history and trades"""

    def __init__(self, supabase_client, model_dir: str = "models"):
        """
        Initialize the Freqtrade retrainer
        
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
        self.min_trades = 20  # Minimum trades to trigger training
        self.min_scans = 10000  # Minimum scans for feature diversity
        self.last_train_file = os.path.join(model_dir, "freqtrade_last_train.json")
        
        # Path to Freqtrade database
        self.freqtrade_db = Path.home() / "crypto-tracker-v3" / "freqtrade" / "user_data" / "tradesv3.dryrun.sqlite"

    def check_data_readiness(self) -> Tuple[bool, Dict]:
        """
        Check if we have enough Freqtrade data for training
        
        Returns:
            Tuple of (is_ready, stats_dict)
        """
        stats = {
            "trades": 0,
            "scans": 0,
            "ready": False,
            "message": ""
        }
        
        try:
            # Check Freqtrade trades
            if self.freqtrade_db.exists():
                conn = sqlite3.connect(self.freqtrade_db)
                trades_df = pd.read_sql_query("SELECT * FROM trades WHERE is_open = 0", conn)
                stats["trades"] = len(trades_df)
                conn.close()
            
            # Check scan_history (only Freqtrade scans)
            result = self.supabase.table("scan_history").select("*", count="exact").limit(1).execute()
            stats["scans"] = result.count if hasattr(result, "count") else 0
            
            # Check readiness
            trades_ready = stats["trades"] >= self.min_trades
            scans_ready = stats["scans"] >= self.min_scans
            
            stats["ready"] = trades_ready and scans_ready
            
            if not trades_ready:
                stats["message"] = f"Need {self.min_trades - stats['trades']} more trades"
            elif not scans_ready:
                stats["message"] = f"Need {self.min_scans - stats['scans']:,} more scans"
            else:
                stats["message"] = "Ready for training!"
                
            logger.info(f"Data readiness: {stats}")
            
        except Exception as e:
            logger.error(f"Error checking data readiness: {e}")
            stats["message"] = f"Error: {str(e)}"
            
        return stats["ready"], stats

    def get_freqtrade_trades(self) -> pd.DataFrame:
        """
        Get completed trades from Freqtrade database
        
        Returns:
            DataFrame with trade outcomes
        """
        if not self.freqtrade_db.exists():
            logger.warning("Freqtrade database not found")
            return pd.DataFrame()
            
        try:
            conn = sqlite3.connect(self.freqtrade_db)
            
            # Get closed trades with outcomes
            query = """
            SELECT 
                pair as symbol,
                open_date as entry_time,
                close_date as exit_time,
                amount,
                open_rate as entry_price,
                close_rate as exit_price,
                close_profit as profit_pct,
                close_profit_abs as profit_abs,
                sell_reason as exit_reason,
                strategy,
                timeframe,
                CASE 
                    WHEN close_profit > 0 THEN 1 
                    ELSE 0 
                END as profitable
            FROM trades
            WHERE is_open = 0
            ORDER BY close_date DESC
            """
            
            trades_df = pd.read_sql_query(query, conn)
            conn.close()
            
            # Clean symbol names (remove /USDT suffix)
            trades_df['symbol'] = trades_df['symbol'].str.replace('/USDT', '')
            
            # Convert timestamps
            trades_df['entry_time'] = pd.to_datetime(trades_df['entry_time'])
            trades_df['exit_time'] = pd.to_datetime(trades_df['exit_time'])
            
            logger.info(f"Loaded {len(trades_df)} Freqtrade trades")
            return trades_df
            
        except Exception as e:
            logger.error(f"Error loading Freqtrade trades: {e}")
            return pd.DataFrame()

    def get_scan_features(self, symbol: str, timestamp: datetime, lookback_hours: int = 24) -> Dict:
        """
        Get scan features for a trade entry
        
        Args:
            symbol: Trading symbol
            timestamp: Trade entry time
            lookback_hours: Hours to look back for features
            
        Returns:
            Dictionary of aggregated features
        """
        try:
            # Get scans around the trade time
            start_time = (timestamp - timedelta(hours=lookback_hours)).isoformat()
            end_time = timestamp.isoformat()
            
            result = self.supabase.table("scan_history")\
                .select("*")\
                .eq("symbol", symbol)\
                .gte("timestamp", start_time)\
                .lte("timestamp", end_time)\
                .order("timestamp", desc=True)\
                .limit(100)\
                .execute()
            
            if not result.data:
                return {}
            
            # Convert to DataFrame for easier processing
            scans_df = pd.DataFrame(result.data)
            
            # Extract and aggregate features
            features = {}
            
            # Technical indicators (most recent values)
            if len(scans_df) > 0:
                latest = scans_df.iloc[0]
                
                # Price features
                features['price'] = latest.get('price', 0)
                features['volume_24h'] = latest.get('volume_24h', 0)
                features['price_change_24h'] = latest.get('price_change_24h', 0)
                
                # Bollinger Bands
                features['bb_lower'] = latest.get('bb_lower', 0)
                features['bb_middle'] = latest.get('bb_middle', 0)
                features['bb_upper'] = latest.get('bb_upper', 0)
                features['bb_position'] = latest.get('bb_position', 0.5)
                
                # RSI
                features['rsi'] = latest.get('rsi', 50)
                
                # MACD
                features['macd'] = latest.get('macd', 0)
                features['macd_signal'] = latest.get('macd_signal', 0)
                features['macd_histogram'] = latest.get('macd_histogram', 0)
                
                # Strategy signals
                features['channel_signal'] = 1 if latest.get('channel_signal', False) else 0
                features['dca_signal'] = 1 if latest.get('dca_signal', False) else 0
                features['swing_signal'] = 1 if latest.get('swing_signal', False) else 0
                
                # Market conditions (aggregated over lookback period)
                if len(scans_df) > 1:
                    features['volatility'] = scans_df['price'].std() / scans_df['price'].mean() if scans_df['price'].mean() > 0 else 0
                    features['trend'] = (scans_df.iloc[0]['price'] - scans_df.iloc[-1]['price']) / scans_df.iloc[-1]['price'] if scans_df.iloc[-1]['price'] > 0 else 0
                    features['volume_trend'] = scans_df['volume_24h'].mean()
                else:
                    features['volatility'] = 0
                    features['trend'] = 0
                    features['volume_trend'] = features['volume_24h']
            
            return features
            
        except Exception as e:
            logger.error(f"Error getting scan features: {e}")
            return {}

    def prepare_training_data(self) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare training data from Freqtrade trades and scan history
        
        Returns:
            Tuple of (features_df, labels_series)
        """
        # Get Freqtrade trades
        trades_df = self.get_freqtrade_trades()
        
        if trades_df.empty:
            logger.warning("No Freqtrade trades available")
            return pd.DataFrame(), pd.Series()
        
        # Build feature matrix
        feature_rows = []
        labels = []
        
        for _, trade in trades_df.iterrows():
            # Get scan features at trade entry
            features = self.get_scan_features(
                trade['symbol'], 
                trade['entry_time'],
                lookback_hours=24
            )
            
            if features:
                # Add trade-specific features
                features['symbol'] = trade['symbol']
                features['hour'] = trade['entry_time'].hour
                features['day_of_week'] = trade['entry_time'].dayofweek
                
                feature_rows.append(features)
                labels.append(trade['profitable'])
        
        if not feature_rows:
            logger.warning("No features extracted")
            return pd.DataFrame(), pd.Series()
        
        # Create DataFrame
        X = pd.DataFrame(feature_rows)
        y = pd.Series(labels)
        
        # Handle categorical features
        if 'symbol' in X.columns:
            # Simple encoding for symbols (could use more sophisticated encoding)
            X['symbol_encoded'] = pd.Categorical(X['symbol']).codes
            X = X.drop('symbol', axis=1)
        
        # Fill missing values
        X = X.fillna(0)
        
        logger.info(f"Prepared {len(X)} training samples with {X.shape[1]} features")
        
        return X, y

    def train_model(self, strategy: str = "CHANNEL") -> Optional[str]:
        """
        Train a new model using Freqtrade data
        
        Args:
            strategy: Strategy name (for model naming)
            
        Returns:
            Status message
        """
        # Check data readiness
        is_ready, stats = self.check_data_readiness()
        
        if not is_ready:
            return f"Not ready: {stats['message']}"
        
        logger.info(f"Starting Freqtrade model training for {strategy}")
        
        try:
            # Prepare training data
            X, y = self.prepare_training_data()
            
            if len(X) < self.min_trades:
                return f"Insufficient samples: {len(X)}/{self.min_trades}"
            
            # Split data
            X_train, X_val, y_train, y_val = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_val_scaled = scaler.transform(X_val)
            
            # Train XGBoost model
            model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                objective='binary:logistic',
                use_label_encoder=False,
                eval_metric='logloss',
                random_state=42
            )
            
            model.fit(X_train_scaled, y_train)
            
            # Validate
            y_pred = model.predict(X_val_scaled)
            accuracy = accuracy_score(y_val, y_pred)
            precision = precision_score(y_val, y_pred, zero_division=0)
            recall = recall_score(y_val, y_pred, zero_division=0)
            
            logger.info(f"Model performance - Accuracy: {accuracy:.3f}, Precision: {precision:.3f}, Recall: {recall:.3f}")
            
            # Save model and scaler
            model_path = os.path.join(self.model_dir, strategy.lower(), "freqtrade_model.pkl")
            scaler_path = os.path.join(self.model_dir, strategy.lower(), "freqtrade_scaler.pkl")
            
            os.makedirs(os.path.dirname(model_path), exist_ok=True)
            
            with open(model_path, 'wb') as f:
                pickle.dump(model, f)
            
            with open(scaler_path, 'wb') as f:
                pickle.dump(scaler, f)
            
            # Save training metadata
            metadata = {
                "trained_at": datetime.now(timezone.utc).isoformat(),
                "samples": len(X),
                "features": list(X.columns),
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "trades_used": stats["trades"],
                "scans_used": stats["scans"]
            }
            
            metadata_path = os.path.join(self.model_dir, strategy.lower(), "freqtrade_metadata.json")
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Update last train time
            self._update_last_train_time(strategy)
            
            return f"Model trained successfully! Accuracy: {accuracy:.3f}, Samples: {len(X)}"
            
        except Exception as e:
            logger.error(f"Error training model: {e}")
            return f"Training failed: {str(e)}"

    def _update_last_train_time(self, strategy: str):
        """Update the last training timestamp"""
        try:
            # Load existing timestamps
            if os.path.exists(self.last_train_file):
                with open(self.last_train_file, 'r') as f:
                    last_trains = json.load(f)
            else:
                last_trains = {}
            
            # Update for this strategy
            last_trains[strategy] = datetime.now(timezone.utc).isoformat()
            
            # Save back
            os.makedirs(os.path.dirname(self.last_train_file), exist_ok=True)
            with open(self.last_train_file, 'w') as f:
                json.dump(last_trains, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error updating last train time: {e}")

    def retrain_all_strategies(self) -> Dict[str, str]:
        """
        Check and retrain all strategies if needed
        
        Returns:
            Dictionary of strategy: status
        """
        results = {}
        
        # For Freqtrade, we only have CHANNEL strategy active
        # But the ML can learn from all trades regardless of strategy
        for strategy in ["CHANNEL"]:
            logger.info(f"Checking {strategy} strategy...")
            result = self.train_model(strategy)
            results[strategy] = result
            
        return results
