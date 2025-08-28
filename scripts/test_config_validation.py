#!/usr/bin/env python3
"""
Test configuration validation
"""

import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.config_loader import ConfigLoader


def test_validation():
    """Test various validation scenarios"""
    loader = ConfigLoader()
    config = loader.load()
    
    print("=" * 80)
    print("CONFIGURATION VALIDATION TESTING")
    print("=" * 80)
    
    # Test 1: Valid configuration
    print("\n1. Testing current configuration...")
    validation = loader.validate_config(config)
    if validation["errors"]:
        print(f"   ❌ Errors found: {validation['errors']}")
    else:
        print("   ✅ No errors in current configuration")
    if validation["warnings"]:
        print(f"   ⚠️  Warnings: {validation['warnings']}")
    
    # Test 2: Invalid take profit (too low)
    print("\n2. Testing invalid take profit (below fees)...")
    test_updates = {
        "strategies.CHANNEL.exits_by_tier.large_cap.take_profit": 0.001  # 0.1% - below fees
    }
    validation = loader.validate_config(config, test_updates)
    if validation["errors"]:
        print(f"   ✅ Correctly caught error: {validation['errors'][0]}")
    else:
        print("   ❌ Should have caught take profit error")
    
    # Test 3: Invalid position limits
    print("\n3. Testing invalid position limits...")
    test_updates = {
        "position_management.max_positions_per_strategy": 100,
        "position_management.max_positions_total": 50  # Less than per strategy
    }
    validation = loader.validate_config(config, test_updates)
    if validation["errors"]:
        print(f"   ✅ Correctly caught error: {validation['errors'][0]}")
    else:
        print("   ❌ Should have caught position limit error")
    
    # Test 4: Invalid regime thresholds
    print("\n4. Testing invalid regime thresholds...")
    test_updates = {
        "market_protection.enhanced_regime.panic_threshold": -0.02,  # Less negative than caution
        "market_protection.enhanced_regime.caution_threshold": -0.05
    }
    validation = loader.validate_config(config, test_updates)
    if validation["errors"]:
        print(f"   ✅ Correctly caught error: {validation['errors'][0]}")
    else:
        print("   ❌ Should have caught regime threshold error")
    
    # Test 5: Warning for small position size
    print("\n5. Testing warning for small position size...")
    test_updates = {
        "position_management.position_sizing.base_position_size_usd": 20  # Below $25
    }
    validation = loader.validate_config(config, test_updates)
    if validation["warnings"]:
        print(f"   ✅ Correctly generated warning: {validation['warnings'][0]}")
    else:
        print("   ❌ Should have generated position size warning")
    
    # Test 6: Multiple errors at once
    print("\n6. Testing multiple validation errors...")
    test_updates = {
        "strategies.DCA.exits_by_tier.large_cap.stop_loss": 0.6,  # > 50%
        "strategies.SWING.exits_by_tier.mid_cap.take_profit": -0.05,  # Negative
        "risk_management.max_daily_loss_pct": 100  # > 50%
    }
    validation = loader.validate_config(config, test_updates)
    print(f"   Found {len(validation['errors'])} errors:")
    for error in validation["errors"]:
        print(f"      - {error}")
    
    print("\n" + "=" * 80)
    print("VALIDATION TESTING COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    test_validation()
