#!/usr/bin/env python3
"""Test script to debug Railway deployment issues"""

import os
import sys

print("=== Railway Test Script ===")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"Script location: {os.path.abspath(__file__)}")

# Check if directories exist
dirs_to_check = ['scripts', 'src', 'src/ml', 'src/config', 'src/data']
for d in dirs_to_check:
    exists = os.path.exists(d)
    print(f"Directory '{d}' exists: {exists}")
    if exists:
        print(f"  Contents: {os.listdir(d)[:5]}...")  # Show first 5 items

# Try importing modules
print("\n=== Testing imports ===")
try:
    from src.config.settings import get_settings
    print("✓ Successfully imported get_settings")
except Exception as e:
    print(f"✗ Failed to import get_settings: {e}")

try:
    from src.ml.feature_calculator import FeatureCalculator
    print("✓ Successfully imported FeatureCalculator")
except Exception as e:
    print(f"✗ Failed to import FeatureCalculator: {e}")

try:
    from src.ml.model_trainer import ModelTrainer
    print("✓ Successfully imported ModelTrainer")
except Exception as e:
    print(f"✗ Failed to import ModelTrainer: {e}")

print("\n=== Test complete ===")
