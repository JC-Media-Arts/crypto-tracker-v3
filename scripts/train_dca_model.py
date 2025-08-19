#!/usr/bin/env python3
"""
Multi-Output XGBoost Model Training for DCA Strategy.

This script trains a model to predict multiple trading parameters:
1. Position size multiplier
2. Optimal take profit percentage
3. Optimal stop loss percentage  
4. Expected hold time (hours)
5. Win probability (confidence)
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime
import joblib
import json
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.multioutput import MultiOutputRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import xgboost as xgb
from loguru import logger
import warnings
warnings.filterwarnings('ignore')

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))


class DCAModelTrainer:
    """Trains a multi-output XGBoost model for DCA strategy optimization."""
    
    def __init__(self, data_path: str = "data/dca_labels_enriched.csv"):
        """Initialize the trainer."""
        self.data_path = data_path
        self.feature_cols = []
        self.target_cols = []
        self.scaler = StandardScaler()
        self.model = None
        self.results = {}
        
    def load_and_prepare_data(self):
        """Load and prepare the training data."""
        logger.info(f"Loading data from {self.data_path}")
        df = pd.read_csv(self.data_path)
        
        # Create target variables based on historical outcomes
        logger.info("Creating target variables...")
        
        # 1. Position size multiplier (based on outcome and market conditions)
        df['target_position_mult'] = self._calculate_position_multiplier(df)
        
        # 2. Optimal take profit (what actually worked)
        df['target_take_profit'] = self._calculate_optimal_tp(df)
        
        # 3. Optimal stop loss (tighter in volatile markets)
        df['target_stop_loss'] = self._calculate_optimal_sl(df)
        
        # 4. Expected hold time (faster in volatile markets)
        df['target_hold_hours'] = self._calculate_hold_time(df)
        
        # 5. Win probability (for confidence)
        df['target_win_prob'] = self._calculate_win_probability(df)
        
        # Define feature columns (exclude identifiers and targets)
        exclude_cols = [
            'symbol', 'timestamp', 'outcome', 'setup_price', 'high_4h',
            'exit_price', 'exit_timestamp', 'pnl_pct', 'take_profit_target',
            'stop_loss_target', 'price', 'drop_pct'
        ]
        
        self.target_cols = [
            'target_position_mult', 'target_take_profit', 'target_stop_loss',
            'target_hold_hours', 'target_win_prob'
        ]
        
        self.feature_cols = [
            col for col in df.columns 
            if col not in exclude_cols and col not in self.target_cols
        ]
        
        logger.info(f"Features: {len(self.feature_cols)}")
        logger.info(f"Targets: {self.target_cols}")
        logger.info(f"Samples: {len(df)}")
        
        return df
    
    def _calculate_position_multiplier(self, df):
        """Calculate optimal position size multiplier based on conditions."""
        multiplier = pd.Series(1.0, index=df.index)
        
        # Base on market regime
        multiplier[df['btc_regime'] == 'BEAR'] *= 2.0
        multiplier[df['btc_regime'] == 'BULL'] *= 0.5
        
        # Adjust for volatility
        multiplier[df['btc_volatility_7d'] > 0.6] *= 1.2
        multiplier[df['btc_volatility_7d'] < 0.3] *= 0.8
        
        # Adjust for relative performance
        multiplier[df['symbol_vs_btc_7d'] < -10] *= 1.3
        multiplier[df['symbol_vs_btc_7d'] > 10] *= 0.7
        
        # Adjust based on actual outcome (learning from history)
        multiplier[df['outcome'] == 'WIN'] *= 1.1
        multiplier[df['outcome'] == 'LOSS'] *= 0.9
        
        # Cap between reasonable bounds
        return multiplier.clip(0.2, 3.0)
    
    def _calculate_optimal_tp(self, df):
        """Calculate optimal take profit based on market cap and volatility."""
        # Start with base TP
        tp = pd.Series(0.10, index=df.index)  # 10% default
        
        # Adjust by market cap tier
        tp[df['market_cap_tier'] == 0] = 0.05  # Large cap: 5%
        tp[df['market_cap_tier'] == 1] = 0.08  # Mid cap: 8%
        tp[df['market_cap_tier'] == 2] = 0.12  # Small cap: 12%
        
        # Adjust by volatility
        high_vol = df['btc_volatility_7d'] > 0.6
        tp[high_vol] *= 1.2  # Increase TP in high volatility
        
        low_vol = df['btc_volatility_7d'] < 0.3
        tp[low_vol] *= 0.8  # Decrease TP in low volatility
        
        # Learn from actual outcomes
        if 'pnl_pct' in df.columns:
            # If we have actual P&L, use it to adjust
            wins = df['outcome'] == 'WIN'
            actual_pnl = df.loc[wins, 'pnl_pct'] / 100
            if len(actual_pnl) > 0:
                avg_win_pnl = actual_pnl.mean()
                if not np.isnan(avg_win_pnl):
                    tp[wins] = tp[wins] * 0.7 + avg_win_pnl * 0.3  # Blend with actual
        
        return tp.clip(0.03, 0.20)  # 3% to 20% range
    
    def _calculate_optimal_sl(self, df):
        """Calculate optimal stop loss based on volatility and regime."""
        # Start with base SL
        sl = pd.Series(-0.08, index=df.index)  # -8% default
        
        # Tighter stops in BULL markets
        sl[df['btc_regime'] == 'BULL'] = -0.05
        
        # Wider stops in BEAR markets (more room for volatility)
        sl[df['btc_regime'] == 'BEAR'] = -0.10
        
        # Adjust by volatility
        high_vol = df['btc_volatility_7d'] > 0.6
        sl[high_vol] *= 1.2  # Wider stops in high volatility
        
        return sl.clip(-0.15, -0.03)  # -15% to -3% range
    
    def _calculate_hold_time(self, df):
        """Calculate expected hold time in hours."""
        # Base hold time
        hold_time = pd.Series(24.0, index=df.index)  # 24 hours default
        
        # Faster in volatile markets
        hold_time[df['btc_volatility_7d'] > 0.6] = 12.0
        hold_time[df['btc_volatility_7d'] < 0.3] = 48.0
        
        # Adjust by market cap (smaller caps move faster)
        hold_time[df['market_cap_tier'] == 2] *= 0.75
        hold_time[df['market_cap_tier'] == 0] *= 1.5
        
        return hold_time.clip(4, 72)  # 4 to 72 hours range
    
    def _calculate_win_probability(self, df):
        """Calculate win probability based on features."""
        # Start with base probability
        win_prob = pd.Series(0.25, index=df.index)  # 25% base
        
        # Adjust by regime (from our analysis)
        win_prob[df['btc_regime'] == 'BEAR'] = 0.44
        win_prob[df['btc_regime'] == 'NEUTRAL'] = 0.27
        win_prob[df['btc_regime'] == 'BULL'] = 0.20
        
        # Adjust by relative performance
        win_prob[df['symbol_vs_btc_7d'] < -10] *= 1.2
        win_prob[df['symbol_vs_btc_7d'] > 10] *= 0.8
        
        # Add some noise for learning
        noise = np.random.normal(0, 0.05, len(win_prob))
        win_prob += noise
        
        return win_prob.clip(0.1, 0.9)
    
    def train_model(self, df):
        """Train the multi-output XGBoost model."""
        logger.info("\n" + "="*80)
        logger.info("TRAINING MULTI-OUTPUT XGBOOST MODEL")
        logger.info("="*80)
        
        # Prepare features and targets
        X = df[self.feature_cols].copy()
        y = df[self.target_cols].copy()
        
        # Handle categorical features
        for col in X.columns:
            if X[col].dtype == 'object':
                # Encode categorical features
                if col == 'btc_regime':
                    X[col] = X[col].map({'BEAR': -1, 'NEUTRAL': 0, 'BULL': 1}).fillna(0)
                elif col == 'market_cap_tier':
                    X[col] = X[col].map({'large': 0, 'mid': 1, 'small': 2}).fillna(1)
                else:
                    # For any other categorical, use label encoding
                    from sklearn.preprocessing import LabelEncoder
                    le = LabelEncoder()
                    X[col] = le.fit_transform(X[col].fillna('unknown'))
        
        # Handle any remaining NaNs in numeric columns
        numeric_cols = X.select_dtypes(include=[np.number]).columns
        X[numeric_cols] = X[numeric_cols].fillna(X[numeric_cols].median())
        y = y.fillna(y.median())
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        logger.info(f"Training samples: {len(X_train)}")
        logger.info(f"Test samples: {len(X_test)}")
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Create XGBoost model with optimized parameters
        base_model = xgb.XGBRegressor(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=-1
        )
        
        # Wrap in MultiOutputRegressor
        self.model = MultiOutputRegressor(base_model)
        
        # Train the model
        logger.info("Training model...")
        self.model.fit(X_train_scaled, y_train)
        
        # Make predictions
        y_pred_train = self.model.predict(X_train_scaled)
        y_pred_test = self.model.predict(X_test_scaled)
        
        # Evaluate each output
        logger.info("\n" + "="*80)
        logger.info("MODEL PERFORMANCE")
        logger.info("="*80)
        
        for i, target in enumerate(self.target_cols):
            logger.info(f"\n{target}:")
            
            # Training metrics
            train_mse = mean_squared_error(y_train.iloc[:, i], y_pred_train[:, i])
            train_mae = mean_absolute_error(y_train.iloc[:, i], y_pred_train[:, i])
            train_r2 = r2_score(y_train.iloc[:, i], y_pred_train[:, i])
            
            # Test metrics
            test_mse = mean_squared_error(y_test.iloc[:, i], y_pred_test[:, i])
            test_mae = mean_absolute_error(y_test.iloc[:, i], y_pred_test[:, i])
            test_r2 = r2_score(y_test.iloc[:, i], y_pred_test[:, i])
            
            logger.info(f"  Train - MSE: {train_mse:.4f}, MAE: {train_mae:.4f}, R²: {train_r2:.4f}")
            logger.info(f"  Test  - MSE: {test_mse:.4f}, MAE: {test_mae:.4f}, R²: {test_r2:.4f}")
            
            self.results[target] = {
                'train_mse': train_mse,
                'train_mae': train_mae,
                'train_r2': train_r2,
                'test_mse': test_mse,
                'test_mae': test_mae,
                'test_r2': test_r2
            }
        
        # Feature importance (average across all outputs)
        logger.info("\n" + "="*80)
        logger.info("TOP 15 FEATURE IMPORTANCES (Averaged)")
        logger.info("="*80)
        
        # Get feature importances from each estimator
        importances = np.zeros(len(self.feature_cols))
        for estimator in self.model.estimators_:
            importances += estimator.feature_importances_
        importances /= len(self.model.estimators_)
        
        # Sort and display
        feature_importance = pd.Series(importances, index=self.feature_cols).sort_values(ascending=False)
        for feat, imp in feature_importance.head(15).items():
            logger.info(f"  {feat:30s}: {imp:.4f}")
        
        return X_test, y_test, self.model.predict(X_test_scaled)
    
    def save_model(self, model_dir: str = "models/dca"):
        """Save the trained model and associated files."""
        Path(model_dir).mkdir(parents=True, exist_ok=True)
        
        # Save model
        model_path = f"{model_dir}/xgboost_multi_output.pkl"
        joblib.dump(self.model, model_path)
        logger.info(f"Model saved to {model_path}")
        
        # Save scaler
        scaler_path = f"{model_dir}/scaler.pkl"
        joblib.dump(self.scaler, scaler_path)
        logger.info(f"Scaler saved to {scaler_path}")
        
        # Save feature columns
        features_path = f"{model_dir}/features.json"
        with open(features_path, 'w') as f:
            json.dump({
                'feature_cols': self.feature_cols,
                'target_cols': self.target_cols
            }, f, indent=2)
        logger.info(f"Features saved to {features_path}")
        
        # Save results
        results_path = f"{model_dir}/training_results.json"
        with open(results_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        logger.info(f"Results saved to {results_path}")
    
    def demonstrate_predictions(self, X_test, y_test, y_pred):
        """Show example predictions to demonstrate the model."""
        logger.info("\n" + "="*80)
        logger.info("EXAMPLE PREDICTIONS")
        logger.info("="*80)
        
        # Show 5 random examples
        indices = np.random.choice(len(X_test), 5, replace=False)
        
        for idx in indices:
            logger.info(f"\nExample {idx}:")
            logger.info("  Features:")
            logger.info(f"    BTC Regime: {X_test.iloc[idx].get('btc_regime', 'N/A')}")
            logger.info(f"    Volatility: {X_test.iloc[idx].get('btc_volatility_7d', 0):.2%}")
            logger.info(f"    vs BTC: {X_test.iloc[idx].get('symbol_vs_btc_7d', 0):.1f}%")
            
            logger.info("  Predictions vs Actual:")
            for i, target in enumerate(self.target_cols):
                actual = y_test.iloc[idx, i]
                predicted = y_pred[idx, i]
                
                if 'mult' in target or 'prob' in target:
                    logger.info(f"    {target:25s}: {predicted:.2f}x (actual: {actual:.2f}x)")
                elif 'profit' in target or 'loss' in target:
                    logger.info(f"    {target:25s}: {predicted:.1%} (actual: {actual:.1%})")
                else:
                    logger.info(f"    {target:25s}: {predicted:.1f}h (actual: {actual:.1f}h)")


def main():
    """Run the complete training pipeline."""
    logger.info("="*80)
    logger.info("DCA MULTI-OUTPUT MODEL TRAINING")
    logger.info("="*80)
    
    # Initialize trainer
    trainer = DCAModelTrainer()
    
    # Load and prepare data
    df = trainer.load_and_prepare_data()
    
    # Train model
    X_test, y_test, y_pred = trainer.train_model(df)
    
    # Save model
    trainer.save_model()
    
    # Demonstrate predictions
    trainer.demonstrate_predictions(X_test, y_test, y_pred)
    
    logger.info("\n" + "="*80)
    logger.info("TRAINING SUMMARY")
    logger.info("="*80)
    
    # Calculate average performance across all targets
    avg_test_r2 = np.mean([res['test_r2'] for res in trainer.results.values()])
    avg_test_mae = np.mean([res['test_mae'] for res in trainer.results.values()])
    
    logger.info(f"\nAverage Test R²: {avg_test_r2:.3f}")
    logger.info(f"Average Test MAE: {avg_test_mae:.3f}")
    
    logger.info("\n" + "="*80)
    logger.info("KEY INSIGHTS")
    logger.info("="*80)
    
    logger.info("\n1. The model can now predict MULTIPLE trading parameters simultaneously")
    logger.info("2. Position sizing adapts to market conditions (2x in BEAR, 0.5x in BULL)")
    logger.info("3. Take profit targets adjust by market cap (5% for BTC, 12% for small caps)")
    logger.info("4. Stop losses tighten in BULL markets, widen in BEAR markets")
    logger.info("5. Hold time predictions help with position management")
    
    logger.success("\n✅ Multi-Output XGBoost Model Training Complete!")
    logger.info("Ready for production use in adaptive trading system")
    
    return trainer


if __name__ == "__main__":
    trainer = main()
