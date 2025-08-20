#!/usr/bin/env python3
"""
Test script to verify ML predictor is working correctly
"""

import sys
sys.path.append(".")

from src.ml.predictor import MLPredictor
from src.config.settings import Settings

def test_ml_predictor():
    """Test ML predictor functionality"""
    
    print("=" * 60)
    print("TESTING ML PREDICTOR")
    print("=" * 60)
    
    # Initialize predictor
    settings = Settings()
    predictor = MLPredictor(settings)
    
    # Check if models loaded
    print("\n1. MODEL LOADING STATUS:")
    print(f"   DCA model loaded: {predictor.dca_model is not None}")
    print(f"   Swing model loaded: {predictor.swing_model is not None}")
    print(f"   Channel model loaded: {predictor.channel_model is not None}")
    
    # Test DCA prediction
    print("\n2. TESTING DCA PREDICTION:")
    dca_features = {
        "rsi": 45,
        "price_change_5m": -0.02,
        "price_change_1h": -0.05,
        "volume_ratio": 1.5,
        "distance_from_support": 0.03,
        "distance_from_resistance": 0.10,
    }
    
    dca_result = predictor.predict_dca(dca_features)
    print(f"   DCA Confidence: {dca_result['confidence']:.3f}")
    print(f"   Take Profit: {dca_result['take_profit_pct']}%")
    print(f"   Stop Loss: {dca_result['stop_loss_pct']}%")
    
    # Test Swing prediction
    print("\n3. TESTING SWING PREDICTION:")
    swing_features = {
        "breakout_strength": 1.5,
        "volume_surge": 2.0,
        "rsi": 65,
        "momentum": 0.08,
        "trend_strength": 0.7,
    }
    
    swing_result = predictor.predict_swing(swing_features)
    print(f"   Swing Confidence: {swing_result['confidence']:.3f}")
    print(f"   Direction: {swing_result['predicted_direction']}")
    print(f"   Take Profit: {swing_result['take_profit_pct']}%")
    
    # Test Channel prediction
    print("\n4. TESTING CHANNEL PREDICTION:")
    channel_features = {
        "distance_from_upper": 0.02,
        "distance_from_lower": 0.08,
        "channel_width": 0.10,
        "rsi": 35,
        "volume_ratio": 0.9,
    }
    
    channel_result = predictor.predict_channel(channel_features)
    print(f"   Channel Confidence: {channel_result['confidence']:.3f}")
    print(f"   Predicted Bounce: {channel_result['predicted_bounce']}")
    print(f"   Take Profit: {channel_result['take_profit_pct']}%")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    
    # Return True if all models loaded
    return (predictor.dca_model is not None or 
            predictor.swing_model is not None or 
            predictor.channel_model is not None)

if __name__ == "__main__":
    success = test_ml_predictor()
    sys.exit(0 if success else 1)
