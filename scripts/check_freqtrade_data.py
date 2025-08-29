#!/usr/bin/env python3
"""
Check Freqtrade data generation progress
Monitor when we have enough data for ML training
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import sqlite3
import pandas as pd

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from loguru import logger


def check_freqtrade_trades():
    """Check Freqtrade's SQLite database for trades"""
    
    print("\n" + "="*60)
    print("🤖 FREQTRADE TRADING ACTIVITY")
    print("="*60)
    
    # Connect to Freqtrade database
    db_path = Path(__file__).parent.parent / "freqtrade" / "user_data" / "tradesv3.dryrun.sqlite"
    
    if not db_path.exists():
        print("❌ Freqtrade database not found")
        return 0
    
    conn = sqlite3.connect(db_path)
    
    # Count trades
    trades_df = pd.read_sql_query("SELECT * FROM trades", conn)
    total_trades = len(trades_df)
    
    print(f"\n📊 Freqtrade Trades:")
    print(f"   Total trades: {total_trades}")
    
    if total_trades > 0:
        # Get trade statistics
        closed_trades = trades_df[trades_df['is_open'] == 0]
        open_trades = trades_df[trades_df['is_open'] == 1]
        
        print(f"   Open positions: {len(open_trades)}")
        print(f"   Closed trades: {len(closed_trades)}")
        
        if len(closed_trades) > 0:
            # Calculate win rate
            profitable = closed_trades[closed_trades['close_profit'] > 0]
            win_rate = (len(profitable) / len(closed_trades)) * 100
            print(f"   Win rate: {win_rate:.1f}%")
            
            # Get date range
            oldest = pd.to_datetime(trades_df['open_date'].min())
            newest = pd.to_datetime(trades_df['open_date'].max())
            print(f"   Date range: {oldest.strftime('%Y-%m-%d')} to {newest.strftime('%Y-%m-%d')}")
    
    conn.close()
    return total_trades


def check_scan_history():
    """Check scan_history table for Freqtrade scans"""
    
    print("\n" + "="*60)
    print("📡 FREQTRADE SCAN HISTORY")
    print("="*60)
    
    db = SupabaseClient()
    
    # Count total scans (should all be from Freqtrade now)
    result = db.client.table("scan_history").select("*", count="exact").limit(1).execute()
    total_scans = result.count if hasattr(result, 'count') else 0
    
    print(f"\n📊 Scan History:")
    print(f"   Total scans: {total_scans:,}")
    
    if total_scans > 0:
        # Get date range
        oldest = db.client.table("scan_history").select("timestamp").order("timestamp").limit(1).execute()
        newest = db.client.table("scan_history").select("timestamp").order("timestamp", desc=True).limit(1).execute()
        
        if oldest.data and newest.data:
            oldest_time = datetime.fromisoformat(oldest.data[0]['timestamp'].replace('Z', '+00:00'))
            newest_time = datetime.fromisoformat(newest.data[0]['timestamp'].replace('Z', '+00:00'))
            
            print(f"   Date range: {oldest_time.strftime('%Y-%m-%d %H:%M')} to {newest_time.strftime('%Y-%m-%d %H:%M')}")
            
            # Calculate scan rate
            time_diff = newest_time - oldest_time
            if time_diff.total_seconds() > 0:
                hours_running = time_diff.total_seconds() / 3600
                scans_per_hour = total_scans / hours_running
                print(f"   Scan rate: {scans_per_hour:.0f} scans/hour")
        
        # Check recent activity
        ten_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        recent = db.client.table("scan_history").select("*", count="exact").gte("timestamp", ten_min_ago).execute()
        recent_count = recent.count if hasattr(recent, 'count') else 0
        
        if recent_count > 0:
            print(f"   Recent activity: {recent_count} scans in last 10 minutes ✅")
        else:
            print(f"   Recent activity: No scans in last 10 minutes ⚠️")
    
    return total_scans


def check_ml_readiness(trades, scans):
    """Check if we have enough data for ML training"""
    
    print("\n" + "="*60)
    print("🧠 ML TRAINING READINESS")
    print("="*60)
    
    # Minimum thresholds for ML
    MIN_TRADES = 20  # Minimum closed trades for meaningful training
    MIN_SCANS = 10000  # Minimum scans for feature diversity
    
    print(f"\n📊 Data Requirements:")
    print(f"   Minimum trades needed: {MIN_TRADES}")
    print(f"   Minimum scans needed: {MIN_SCANS:,}")
    
    print(f"\n📈 Current Status:")
    trades_ready = trades >= MIN_TRADES
    scans_ready = scans >= MIN_SCANS
    
    print(f"   Trades: {trades} / {MIN_TRADES} {'✅ Ready' if trades_ready else f'⏳ Need {MIN_TRADES - trades} more'}")
    print(f"   Scans: {scans:,} / {MIN_SCANS:,} {'✅ Ready' if scans_ready else f'⏳ Need {MIN_SCANS - scans:,} more'}")
    
    if trades_ready and scans_ready:
        print("\n🎉 Ready for ML training!")
        print("\n📝 Next Steps:")
        print("   1. Run ML retrainer with Freqtrade-only data")
        print("   2. Start shadow testing with new models")
        print("   3. Generate recommendations for threshold tuning")
    else:
        print("\n⏳ Not enough data yet. Let Freqtrade run longer.")
        
        # Estimate time needed
        if scans > 0:
            # Assume current scan rate continues
            db = SupabaseClient()
            oldest = db.client.table("scan_history").select("timestamp").order("timestamp").limit(1).execute()
            if oldest.data:
                oldest_time = datetime.fromisoformat(oldest.data[0]['timestamp'].replace('Z', '+00:00'))
                time_running = datetime.now(timezone.utc) - oldest_time
                hours_running = time_running.total_seconds() / 3600
                
                if hours_running > 0:
                    scans_per_hour = scans / hours_running
                    
                    if not scans_ready and scans_per_hour > 0:
                        hours_needed = (MIN_SCANS - scans) / scans_per_hour
                        print(f"\n⏰ Estimated time to {MIN_SCANS:,} scans: {hours_needed:.1f} hours")


def main():
    """Main check flow"""
    
    print("\n🚀 FREQTRADE DATA CHECK - ML Readiness")
    print(f"📅 Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    # Check Freqtrade trades
    trades = check_freqtrade_trades()
    
    # Check scan history
    scans = check_scan_history()
    
    # Check ML readiness
    check_ml_readiness(trades, scans)
    
    print("\n" + "="*60)
    print("\n💡 Remember:")
    print("   • Freqtrade is running on Railway 24/7")
    print("   • Dashboard shows real-time trading activity")
    print("   • ML will only train on this clean Freqtrade data")
    print("   • No old paper trading data will be used")


if __name__ == "__main__":
    main()
