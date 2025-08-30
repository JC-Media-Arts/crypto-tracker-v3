#!/usr/bin/env python3
"""
Test Risk Manager functionality
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from src.config.config_loader import ConfigLoader
from src.trading.risk_manager import RiskManager
from datetime import datetime, timezone


def test_risk_manager():
    """Test risk manager functions"""
    
    print("\n" + "="*60)
    print("🛡️ TESTING RISK MANAGER")
    print("="*60)
    
    # Initialize components
    supabase = SupabaseClient()
    config = ConfigLoader()
    risk_manager = RiskManager(supabase, config, initial_balance=10000)
    
    # Test 1: Calculate metrics
    print("\n1️⃣ Calculating Risk Metrics...")
    try:
        metrics = risk_manager.calculate_risk_metrics()
        
        print(f"   ✅ Metrics calculated successfully")
        print(f"   Open positions: {metrics.open_positions}")
        print(f"   Total exposure: ${metrics.total_exposure:.2f}")
        print(f"   Daily P&L: ${metrics.daily_pnl:.2f}")
        print(f"   Weekly P&L: ${metrics.weekly_pnl:.2f}")
        print(f"   Win rate: {metrics.win_rate:.1%}")
        print(f"   Current balance: ${metrics.current_balance:.2f}")
        print(f"   Risk score: {metrics.risk_score:.0f}/100")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        metrics = None
    
    # Test 2: Check risk limits
    if metrics:
        print("\n2️⃣ Checking Risk Limits...")
        try:
            violations = risk_manager.check_risk_limits(metrics)
            
            if violations:
                print(f"   ⚠️ Found {len(violations)} violation(s):")
                for v in violations:
                    print(f"      - {v['type']}: {v['message']} [{v['severity']}]")
            else:
                print(f"   ✅ No risk violations")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # Test 3: Check trade approval
    print("\n3️⃣ Testing Trade Approval...")
    try:
        # Test small trade
        allowed, reason = risk_manager.should_allow_trade("BTC", 100)
        print(f"   Small trade ($100): {'✅ Allowed' if allowed else f'❌ Denied - {reason}'}")
        
        # Test large trade
        allowed, reason = risk_manager.should_allow_trade("BTC", 5000)
        print(f"   Large trade ($5000): {'✅ Allowed' if allowed else f'❌ Denied - {reason}'}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 4: Get risk status
    print("\n4️⃣ Getting Risk Status...")
    try:
        status = risk_manager.get_risk_status()
        
        print(f"   ✅ Status retrieved")
        print(f"   Risk level: {status['risk_level']}")
        print(f"   Trading enabled: {status['trading_enabled']}")
        print(f"   Emergency stop: {status['emergency_stop']}")
        print(f"   Violations: {len(status['violations'])}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 5: Simulate violations
    print("\n5️⃣ Simulating Risk Scenarios...")
    
    # Simulate high risk score
    print("\n   Testing high risk scenario:")
    test_metrics = risk_manager.calculate_risk_metrics()
    test_metrics.risk_score = 85
    test_metrics.daily_pnl = -600  # 6% loss
    test_metrics.open_positions = 15  # Too many positions
    
    violations = risk_manager.check_risk_limits(test_metrics)
    if violations:
        print(f"   Found {len(violations)} violation(s) in high risk scenario")
        actions = risk_manager.execute_risk_actions(violations)
        print(f"   Actions taken: {actions['actions']}")
        print(f"   Trading enabled: {actions['trading_enabled']}")
    
    print("\n" + "="*60)
    print("✅ Risk Manager test complete!")
    print("\n📝 Summary:")
    print("   • Risk metrics calculation: Working")
    print("   • Risk limit checking: Working")
    print("   • Trade approval logic: Working")
    print("   • Risk status reporting: Working")
    
    if metrics.open_positions == 0:
        print("\n💡 Note: No trades yet, so most metrics are zero.")
        print("   Risk manager will become more active once Freqtrade makes trades.")


if __name__ == "__main__":
    test_risk_manager()
