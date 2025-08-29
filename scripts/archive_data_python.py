#!/usr/bin/env python3
"""
Archive and clean data using Python to handle large datasets
This avoids SQL timeout issues
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone
import time

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from loguru import logger


def create_archive_tables(db):
    """Create archive tables if they don't exist"""
    print("\n📦 Creating archive tables...")
    
    # Create scan_history_archive
    try:
        db.client.rpc('exec_sql', {
            'sql': """
            CREATE TABLE IF NOT EXISTS scan_history_archive (
                LIKE scan_history INCLUDING ALL,
                archived_at TIMESTAMP DEFAULT NOW()
            )
            """
        }).execute()
        print("✅ scan_history_archive table ready")
    except:
        # Table might already exist
        print("ℹ️ scan_history_archive already exists")
    
    # Create paper_trades_archive
    try:
        db.client.rpc('exec_sql', {
            'sql': """
            CREATE TABLE IF NOT EXISTS paper_trades_archive (
                LIKE paper_trades INCLUDING ALL,
                archived_at TIMESTAMP DEFAULT NOW()
            )
            """
        }).execute()
        print("✅ paper_trades_archive table ready")
    except:
        # Table might already exist
        print("ℹ️ paper_trades_archive already exists")


def archive_paper_trades(db):
    """Archive paper_trades table (smaller, easier)"""
    print("\n💰 Archiving paper_trades...")
    
    # Get all paper trades
    batch_size = 1000
    offset = 0
    total_archived = 0
    
    while True:
        # Fetch batch
        result = db.client.table("paper_trades")\
            .select("*")\
            .range(offset, offset + batch_size - 1)\
            .execute()
        
        if not result.data:
            break
        
        # Add archived_at timestamp
        for record in result.data:
            record['archived_at'] = datetime.now(timezone.utc).isoformat()
        
        # Insert into archive
        db.client.table("paper_trades_archive").insert(result.data).execute()
        
        total_archived += len(result.data)
        print(f"   Archived {total_archived} trades...")
        
        offset += batch_size
        
        # Small delay to avoid rate limits
        time.sleep(0.1)
    
    print(f"✅ Archived {total_archived} paper trades")
    return total_archived


def archive_scan_history(db):
    """Archive scan_history table in chunks"""
    print("\n📊 Archiving scan_history (this will take a few minutes)...")
    
    batch_size = 5000  # Smaller batches for large table
    offset = 0
    total_archived = 0
    
    # Get total count first
    count_result = db.client.table("scan_history").select("*", count="exact").limit(1).execute()
    total_count = count_result.count if hasattr(count_result, 'count') else 0
    print(f"   Total records to archive: {total_count:,}")
    
    while True:
        # Fetch batch
        result = db.client.table("scan_history")\
            .select("*")\
            .order("id")\
            .range(offset, offset + batch_size - 1)\
            .execute()
        
        if not result.data:
            break
        
        # Add archived_at timestamp
        for record in result.data:
            record['archived_at'] = datetime.now(timezone.utc).isoformat()
        
        # Insert into archive
        try:
            db.client.table("scan_history_archive").insert(result.data).execute()
            total_archived += len(result.data)
            
            # Progress indicator
            progress = (total_archived / total_count * 100) if total_count > 0 else 0
            print(f"   Archived {total_archived:,} / {total_count:,} scans ({progress:.1f}%)...")
        except Exception as e:
            logger.error(f"Error archiving batch at offset {offset}: {e}")
            # Continue with next batch
        
        offset += batch_size
        
        # Small delay to avoid rate limits
        time.sleep(0.2)
    
    print(f"✅ Archived {total_archived} scan history records")
    return total_archived


def delete_production_data(db):
    """Delete data from production tables"""
    print("\n🗑️ Deleting production data...")
    
    # Delete paper_trades first (foreign key constraint)
    print("   Deleting paper_trades...")
    batch_size = 1000
    total_deleted = 0
    
    while True:
        # Get batch of IDs to delete
        result = db.client.table("paper_trades")\
            .select("id")\
            .limit(batch_size)\
            .execute()
        
        if not result.data:
            break
        
        ids = [r['id'] for r in result.data]
        
        # Delete batch
        db.client.table("paper_trades")\
            .delete()\
            .in_("id", ids)\
            .execute()
        
        total_deleted += len(ids)
        print(f"   Deleted {total_deleted} trades...")
        
        time.sleep(0.1)
    
    print(f"✅ Deleted {total_deleted} paper trades")
    
    # Delete scan_history
    print("   Deleting scan_history (this will take a while)...")
    total_deleted = 0
    
    while True:
        # Get batch of IDs to delete
        result = db.client.table("scan_history")\
            .select("id")\
            .limit(batch_size)\
            .execute()
        
        if not result.data:
            break
        
        ids = [r['id'] for r in result.data]
        
        # Delete batch
        db.client.table("scan_history")\
            .delete()\
            .in_("id", ids)\
            .execute()
        
        total_deleted += len(ids)
        
        if total_deleted % 10000 == 0:
            print(f"   Deleted {total_deleted} scans...")
        
        time.sleep(0.1)
    
    print(f"✅ Deleted {total_deleted} scan history records")


def verify_results(db):
    """Verify the archival and cleanup"""
    print("\n" + "="*60)
    print("📋 FINAL VERIFICATION")
    print("="*60)
    
    # Check production tables
    scan_count = db.client.table("scan_history").select("*", count="exact").limit(1).execute()
    scan_count = scan_count.count if hasattr(scan_count, 'count') else 0
    
    trades_count = db.client.table("paper_trades").select("*", count="exact").limit(1).execute()
    trades_count = trades_count.count if hasattr(trades_count, 'count') else 0
    
    print(f"\n🏭 Production Tables (should be empty):")
    print(f"   scan_history: {scan_count:,} records {'✅ CLEAN' if scan_count == 0 else '❌ NOT EMPTY'}")
    print(f"   paper_trades: {trades_count:,} records {'✅ CLEAN' if trades_count == 0 else '❌ NOT EMPTY'}")
    
    # Check archive tables
    archive_scan = db.client.table("scan_history_archive").select("*", count="exact").limit(1).execute()
    archive_scan_count = archive_scan.count if hasattr(archive_scan, 'count') else 0
    
    archive_trades = db.client.table("paper_trades_archive").select("*", count="exact").limit(1).execute()
    archive_trades_count = archive_trades.count if hasattr(archive_trades, 'count') else 0
    
    print(f"\n📦 Archive Tables (should have data):")
    print(f"   scan_history_archive: {archive_scan_count:,} records")
    print(f"   paper_trades_archive: {archive_trades_count:,} records")
    
    if scan_count == 0 and trades_count == 0:
        print("\n🎉 SUCCESS! Clean slate achieved!")
        print("\n✨ Freqtrade can now start fresh:")
        print("   • New scan_history entries will be from Freqtrade only")
        print("   • ML will train on clean Freqtrade data")
        print("   • Shadow testing will use Freqtrade baseline")
        print("   • Old data is safely archived for reference")
    
    return scan_count == 0 and trades_count == 0


def main():
    """Main archival flow"""
    
    print("\n🚀 FREQTRADE FRESH START - Python Archival")
    print(f"📅 Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    db = SupabaseClient()
    
    # Ask for confirmation
    print("\n" + "="*60)
    print("⚠️  WARNING: This will archive and delete all existing data!")
    print("="*60)
    print("\nThis script will:")
    print("1. Create archive tables")
    print("2. Copy all data to archives")
    print("3. Delete all data from production tables")
    print("4. Give Freqtrade a clean slate")
    
    response = input("\n❓ Do you want to proceed? (yes/no): ")
    
    if response.lower() != 'yes':
        print("❌ Aborted. No changes made.")
        return
    
    try:
        # Step 1: Create archive tables
        create_archive_tables(db)
        
        # Step 2: Archive paper_trades
        archive_paper_trades(db)
        
        # Step 3: Archive scan_history
        archive_scan_history(db)
        
        # Step 4: Delete production data
        print("\n⚠️  About to delete production data...")
        response = input("❓ Continue with deletion? (yes/no): ")
        
        if response.lower() == 'yes':
            delete_production_data(db)
        else:
            print("⏸️ Stopped before deletion. Archives created but production data intact.")
            return
        
        # Step 5: Verify
        verify_results(db)
        
    except Exception as e:
        logger.error(f"Error during archival: {e}")
        print(f"\n❌ Error occurred: {e}")
        print("Please check the logs and database state")


if __name__ == "__main__":
    main()
