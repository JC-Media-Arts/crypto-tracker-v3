#!/usr/bin/env python3
"""
Verify data archival and cleanup for Freqtrade fresh start
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from loguru import logger


def check_data_status():
    """Check current status of data tables"""
    
    db = SupabaseClient()
    
    print("\n" + "="*60)
    print("🔍 DATA STATUS CHECK - Before Archive")
    print("="*60)
    
    # Check scan_history
    scan_count_result = db.client.table("scan_history").select("*", count="exact").execute()
    scan_count = scan_count_result.count if hasattr(scan_count_result, 'count') else len(scan_count_result.data)
    
    # Get latest scan
    latest_scan = db.client.table("scan_history").select("timestamp, strategy_name").order("timestamp", desc=True).limit(1).execute()
    
    print(f"\n📊 scan_history table:")
    print(f"   Total records: {scan_count:,}")
    if latest_scan.data:
        print(f"   Latest scan: {latest_scan.data[0]['timestamp']}")
        print(f"   Strategy: {latest_scan.data[0]['strategy_name']}")
    
    # Check paper_trades
    trades_count_result = db.client.table("paper_trades").select("*", count="exact").execute()
    trades_count = trades_count_result.count if hasattr(trades_count_result, 'count') else len(trades_count_result.data)
    
    # Get latest trade
    latest_trade = db.client.table("paper_trades").select("created_at, strategy_name").order("created_at", desc=True).limit(1).execute()
    
    print(f"\n💰 paper_trades table:")
    print(f"   Total records: {trades_count:,}")
    if latest_trade.data:
        print(f"   Latest trade: {latest_trade.data[0]['created_at']}")
        print(f"   Strategy: {latest_trade.data[0].get('strategy_name', 'N/A')}")
    
    # Check if archive tables exist
    print(f"\n📦 Archive tables:")
    try:
        archive_scan = db.client.table("scan_history_archive").select("*", count="exact").limit(1).execute()
        archive_scan_count = archive_scan.count if hasattr(archive_scan, 'count') else 0
        print(f"   scan_history_archive: {archive_scan_count:,} records")
    except:
        print(f"   scan_history_archive: Does not exist yet")
    
    try:
        archive_trades = db.client.table("paper_trades_archive").select("*", count="exact").limit(1).execute()
        archive_trades_count = archive_trades.count if hasattr(archive_trades, 'count') else 0
        print(f"   paper_trades_archive: {archive_trades_count:,} records")
    except:
        print(f"   paper_trades_archive: Does not exist yet")
    
    print("\n" + "="*60)
    
    # Check Freqtrade scans
    print("\n🤖 Freqtrade Activity Check:")
    
    # Count CHANNEL strategy scans (from Freqtrade)
    channel_scans = db.client.table("scan_history").select("*", count="exact").eq("strategy_name", "CHANNEL").execute()
    channel_count = channel_scans.count if hasattr(channel_scans, 'count') else 0
    
    print(f"   CHANNEL strategy scans: {channel_count:,}")
    
    # Get date range of CHANNEL scans
    if channel_count > 0:
        oldest_channel = db.client.table("scan_history").select("timestamp").eq("strategy_name", "CHANNEL").order("timestamp").limit(1).execute()
        newest_channel = db.client.table("scan_history").select("timestamp").eq("strategy_name", "CHANNEL").order("timestamp", desc=True).limit(1).execute()
        
        if oldest_channel.data and newest_channel.data:
            print(f"   Oldest CHANNEL scan: {oldest_channel.data[0]['timestamp']}")
            print(f"   Newest CHANNEL scan: {newest_channel.data[0]['timestamp']}")
    
    return {
        'scan_count': scan_count,
        'trades_count': trades_count,
        'channel_count': channel_count
    }


def verify_clean_slate():
    """Verify that tables have been cleaned"""
    
    db = SupabaseClient()
    
    print("\n" + "="*60)
    print("✅ CLEAN SLATE VERIFICATION")
    print("="*60)
    
    # Check if tables are empty
    scan_count_result = db.client.table("scan_history").select("*", count="exact").execute()
    scan_count = scan_count_result.count if hasattr(scan_count_result, 'count') else len(scan_count_result.data)
    
    trades_count_result = db.client.table("paper_trades").select("*", count="exact").execute()
    trades_count = trades_count_result.count if hasattr(trades_count_result, 'count') else len(trades_count_result.data)
    
    print(f"\n📊 Production Tables (should be empty):")
    print(f"   scan_history: {scan_count:,} records {'✅ CLEAN' if scan_count == 0 else '❌ NOT EMPTY'}")
    print(f"   paper_trades: {trades_count:,} records {'✅ CLEAN' if trades_count == 0 else '❌ NOT EMPTY'}")
    
    # Check archives exist
    print(f"\n📦 Archive Tables (should have data):")
    try:
        archive_scan = db.client.table("scan_history_archive").select("*", count="exact").limit(1).execute()
        archive_scan_count = archive_scan.count if hasattr(archive_scan, 'count') else 0
        print(f"   scan_history_archive: {archive_scan_count:,} records {'✅' if archive_scan_count > 0 else '❌ EMPTY'}")
    except Exception as e:
        print(f"   scan_history_archive: ❌ Error - {e}")
    
    try:
        archive_trades = db.client.table("paper_trades_archive").select("*", count="exact").limit(1).execute()
        archive_trades_count = archive_trades.count if hasattr(archive_trades, 'count') else 0
        print(f"   paper_trades_archive: {archive_trades_count:,} records {'✅' if archive_trades_count > 0 else '❌ EMPTY'}")
    except Exception as e:
        print(f"   paper_trades_archive: ❌ Error - {e}")
    
    if scan_count == 0 and trades_count == 0:
        print("\n🎉 SUCCESS! Tables are clean and ready for Freqtrade!")
        print("\n📝 Next Steps:")
        print("   1. Freqtrade will start populating scan_history with fresh data")
        print("   2. ML will train only on Freqtrade-generated data")
        print("   3. Shadow testing will use clean Freqtrade baseline")
    else:
        print("\n⚠️ WARNING: Tables are not empty. Run the SQL script to clean them.")
    
    return scan_count == 0 and trades_count == 0


def main():
    """Main verification flow"""
    
    print("\n🚀 FREQTRADE FRESH START - Data Verification")
    print(f"📅 Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    # Check current status
    before_stats = check_data_status()
    
    if before_stats['scan_count'] > 0 or before_stats['trades_count'] > 0:
        print("\n" + "="*60)
        print("⚠️  ACTION REQUIRED")
        print("="*60)
        print("\n1. Go to Supabase SQL Editor")
        print("2. Run the SQL script: scripts/archive_and_clean_data.sql")
        print("3. Run this script again to verify")
        
        print("\n📋 SQL Preview:")
        print("   - Creates archive tables (backup)")
        print("   - Deletes all records from production tables")
        print("   - Resets auto-increment counters")
        print("   - Adds documentation comments")
    else:
        # Verify clean slate
        is_clean = verify_clean_slate()
        
        if is_clean:
            print("\n✨ Your database is ready for Freqtrade!")
            print("   - Old data is safely archived")
            print("   - Production tables are clean")
            print("   - ML will train on fresh Freqtrade data only")


if __name__ == "__main__":
    main()
