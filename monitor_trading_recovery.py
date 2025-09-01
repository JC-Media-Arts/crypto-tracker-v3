#!/usr/bin/env python3
"""
Monitor Freqtrade recovery after MKR/USD fix
"""

import os
import time
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))

def check_status():
    """Check current status of scans and trades"""
    now = datetime.now(timezone.utc)
    five_min_ago = now - timedelta(minutes=5)
    
    # Check recent scans
    scans = supabase.table('scan_history') \
        .select('*') \
        .gte('timestamp', five_min_ago.isoformat()) \
        .order('timestamp', desc=True) \
        .execute()
    
    # Check recent trades
    trades = supabase.table('freqtrade_trades') \
        .select('*') \
        .gte('open_date', five_min_ago.isoformat()) \
        .execute()
    
    # Get last scan time
    last_scan = supabase.table('scan_history') \
        .select('timestamp') \
        .order('timestamp', desc=True) \
        .limit(1) \
        .execute()
    
    scan_count = len(scans.data) if scans.data else 0
    trade_count = len(trades.data) if trades.data else 0
    
    if last_scan.data:
        last_scan_time = datetime.fromisoformat(last_scan.data[0]['timestamp'].replace('Z', '+00:00'))
        mins_since_scan = (now - last_scan_time).total_seconds() / 60
    else:
        mins_since_scan = 999
    
    return scan_count, trade_count, mins_since_scan

def monitor_loop(duration_minutes=5):
    """Monitor for specified duration"""
    print("🔍 MONITORING FREQTRADE RECOVERY")
    print("="*60)
    print(f"Started at: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")
    print(f"Monitoring for {duration_minutes} minutes...")
    print("="*60)
    
    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)
    
    check_interval = 30  # Check every 30 seconds
    iteration = 0
    
    while time.time() < end_time:
        iteration += 1
        scan_count, trade_count, mins_since = check_status()
        
        timestamp = datetime.now(timezone.utc).strftime('%H:%M:%S')
        
        # Status indicators
        scan_status = "✅" if scan_count > 0 else "❌"
        trade_status = "✅" if trade_count > 0 else "⚠️"
        
        print(f"\n[{timestamp}] Check #{iteration}:")
        print(f"  Scans (last 5min): {scan_status} {scan_count}")
        print(f"  Trades (last 5min): {trade_status} {trade_count}")
        print(f"  Last scan: {mins_since:.1f} minutes ago")
        
        if scan_count > 0 and iteration == 1:
            print("  🎉 SCANS ARE WORKING AGAIN!")
        
        if trade_count > 0:
            print("  🎉 TRADES ARE BEING EXECUTED!")
            # Get trade details
            trades = supabase.table('freqtrade_trades') \
                .select('pair, stake_amount, open_date') \
                .gte('open_date', (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()) \
                .execute()
            for trade in trades.data:
                print(f"    - {trade['pair']}: ${trade.get('stake_amount', 'N/A')}")
        
        if scan_count == 0 and mins_since < 10:
            print("  ⚠️ Scans may have just stopped - service might be restarting")
        
        # Check if we're recovered
        if scan_count > 10 and mins_since < 1:
            print("\n✅ SYSTEM RECOVERED - Scans are flowing normally")
            if trade_count == 0:
                print("⚠️ But no trades yet - may need to wait for good signals")
        
        # Wait before next check
        if time.time() < end_time:
            time.sleep(check_interval)
    
    print("\n" + "="*60)
    print("MONITORING COMPLETE")
    print("="*60)
    
    # Final status
    scan_count, trade_count, mins_since = check_status()
    
    if scan_count > 0:
        print("✅ Scan logger: WORKING")
    else:
        print("❌ Scan logger: NOT WORKING")
    
    if trade_count > 0:
        print("✅ Trade execution: WORKING")
    else:
        print("⚠️ Trade execution: No trades (check if signals are too strict)")
    
    if mins_since < 2:
        print("✅ System stability: STABLE")
    else:
        print("⚠️ System stability: May still be having issues")

if __name__ == "__main__":
    # Monitor for 3 minutes
    monitor_loop(3)
