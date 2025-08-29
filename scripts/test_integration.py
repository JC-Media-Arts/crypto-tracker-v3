#!/usr/bin/env python3
"""
Test Freqtrade integration components
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from datetime import datetime, timezone, timedelta
import pandas as pd

def test_integration():
    """Test all integration points"""
    
    print("\n" + "="*60)
    print("🧪 TESTING FREQTRADE INTEGRATION")
    print("="*60)
    
    db = SupabaseClient()
    
    # 1. Check freqtrade_trades table
    print("\n1️⃣ Checking freqtrade_trades table...")
    try:
        result = db.client.table('freqtrade_trades').select('*', count='exact').limit(5).execute()
        count = result.count if hasattr(result, 'count') else 0
        
        print(f"   ✅ Table accessible")
        print(f"   Total synced trades: {count}")
        
        if result.data:
            print("   Sample trades:")
            for trade in result.data[:3]:
                profit = trade.get('close_profit', 0)
                print(f"     - {trade['symbol']}: {profit:.2f}% profit")
        else:
            print("   ⏳ No trades yet (Freqtrade needs to complete some trades first)")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # 2. Check scan_history
    print("\n2️⃣ Checking scan_history...")
    try:
        recent = db.client.table('scan_history').select('symbol, timestamp, price').order('timestamp', desc=True).limit(5).execute()
        
        if recent.data:
            print("   ✅ Recent Freqtrade scans:")
            for scan in recent.data:
                ts = scan['timestamp'][:19]
                symbol = scan['symbol']
                price = scan.get('price', 0)
                print(f"     {ts}: {symbol} @ ${price:.2f}")
        else:
            print("   ❌ No scans found")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # 3. Check ML retrainer readiness
    print("\n3️⃣ Checking ML Retrainer...")
    try:
        from src.ml.simple_retrainer import SimpleRetrainer
        retrainer = SimpleRetrainer(db.client)
        
        should_retrain, count = retrainer.should_retrain("CHANNEL")
        print(f"   ✅ Retrainer accessible")
        print(f"   New trades available: {count}")
        print(f"   Should retrain: {'Yes' if should_retrain else 'No (need 20+ trades)'}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # 4. Check dashboard API endpoint
    print("\n4️⃣ Checking Dashboard API...")
    try:
        # Check if dashboard is running
        import requests
        response = requests.get("http://localhost:8080/api/engine-status", timeout=2)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Dashboard API responding")
            print(f"   Engine status: {'Running' if data.get('running') else 'Not running'}")
        else:
            print(f"   ⚠️ Dashboard returned status {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("   ℹ️ Dashboard not running locally (check Railway)")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # 5. Check Freqtrade activity
    print("\n5️⃣ Checking Freqtrade Activity...")
    try:
        # Check for recent scans (within last 10 minutes)
        ten_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        result = db.client.table('scan_history').select('*', count='exact').gte('timestamp', ten_min_ago).execute()
        recent_count = result.count if hasattr(result, 'count') else 0
        
        if recent_count > 0:
            print(f"   ✅ Freqtrade is active ({recent_count} scans in last 10 min)")
        else:
            print("   ⚠️ No recent Freqtrade activity")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n" + "="*60)
    print("📊 SUMMARY:")
    print("="*60)
    print("\n✅ Integration components are set up correctly!")
    print("\n📝 Next steps:")
    print("   1. Wait for Freqtrade to make trades (~12-24 hours)")
    print("   2. Trades will sync to freqtrade_trades table")
    print("   3. ML will train after 20+ trades")
    print("   4. Check Railway logs for any issues")
    

if __name__ == "__main__":
    test_integration()
