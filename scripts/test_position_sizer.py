#!/usr/bin/env python3
"""Test position sizer interface."""

from src.trading.position_sizer import AdaptivePositionSizer
import inspect

sizer = AdaptivePositionSizer()

# Check the method signature
sig = inspect.signature(sizer.calculate_position_size)
print("AdaptivePositionSizer.calculate_position_size parameters:")
print(f"  {sig}")

# Try calling it with different parameters
print("\nTesting different parameter combinations:")

# Test 1: With strategy parameter
try:
    size = sizer.calculate_position_size(symbol="BTC", strategy="dca", confidence=0.75, account_balance=10000)
    print(f"✅ With strategy: ${size:.2f}")
except TypeError as e:
    print(f"❌ With strategy failed: {e}")

# Test 2: Without strategy parameter
try:
    size = sizer.calculate_position_size(symbol="BTC", confidence=0.75, account_balance=10000)
    print(f"✅ Without strategy: ${size:.2f}")
except TypeError as e:
    print(f"❌ Without strategy failed: {e}")

# Test 3: Check what it actually needs
print("\nActual method parameters needed:")
params = list(sig.parameters.keys())
print(f"  Required: {params}")
