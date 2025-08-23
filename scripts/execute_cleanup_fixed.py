#!/usr/bin/env python3
"""
Execute data cleanup according to approved retention policy.
FIXED VERSION - Works with Supabase client limitations.

APPROVED POLICY:
- 1-minute: Keep 30 days
- 15-minute: Keep 1 year  
- 1-hour: Keep 2 years
- Daily: Keep forever
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
import time

sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from loguru import logger


def cleanup_by_date_ranges(supabase, table, timeframe_list, cutoff_date, days_per_batch=30):
    """
    Clean up data by deleting in date range chunks to avoid timeouts.
    """
    total_deleted = 0
    current_date = datetime.now(timezone.utc)
    
    for tf in timeframe_list:
        logger.info(f"Cleaning {table} where timeframe='{tf}' before {cutoff_date[:10]}")
        batch_deleted = 0
        
        # Parse cutoff date
        cutoff_dt = datetime.fromisoformat(cutoff_date.replace('Z', '+00:00'))
        
        # Start from cutoff and work backwards in chunks
        end_date = cutoff_dt
        
        while end_date > cutoff_dt - timedelta(days=365*10):  # Don't go back more than 10 years
            start_date = end_date - timedelta(days=days_per_batch)
            
            try:
                # Delete data in this date range
                logger.info(f"  Deleting {tf} from {start_date.date()} to {end_date.date()}")
                
                result = supabase.client.table(table)\
                    .delete()\
                    .eq("timeframe", tf)\
                    .gte("timestamp", start_date.isoformat())\
                    .lt("timestamp", end_date.isoformat())\
                    .execute()
                
                deleted_count = len(result.data) if result.data else 0
                batch_deleted += deleted_count
                total_deleted += deleted_count
                
                logger.info(f"    Deleted {deleted_count:,} rows")
                
                if deleted_count == 0:
                    # No more data in this range, try going further back
                    logger.info(f"  No data found in range, checking older...")
                
                # Move to next batch (older data)
                end_date = start_date
                
                # Brief pause between batches
                time.sleep(0.5)
                
                # Stop if we've deleted enough or gone back far enough
                if batch_deleted > 1000000:  # Stop after 1M rows per timeframe
                    logger.info(f"  Reached 1M row limit for {tf}")
                    break
                    
            except Exception as e:
                error_msg = str(e)
                if "timeout" in error_msg.lower():
                    logger.warning(f"  Timeout on range, reducing batch size...")
                    days_per_batch = max(7, days_per_batch // 2)
                elif "does not exist" in error_msg:
                    logger.info(f"  No data found for {tf}")
                    break
                else:
                    logger.error(f"  Error: {error_msg[:100]}")
                    # Try to continue with next range
                    end_date = start_date
                    time.sleep(1)
        
        logger.info(f"  Completed {tf}: {batch_deleted:,} total rows deleted")
    
    return total_deleted


def cleanup_simple_tables(supabase):
    """Clean up smaller tables that don't need batching."""
    
    cleanup_summary = []
    
    # Clean scan_history (>7 days)
    try:
        seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        result = supabase.client.table("scan_history")\
            .delete()\
            .lt("timestamp", seven_days_ago)\
            .execute()
        
        deleted = len(result.data) if result.data else 0
        cleanup_summary.append(("scan_history (>7 days)", deleted))
        logger.info(f"Deleted {deleted:,} rows from scan_history")
    except Exception as e:
        if "timeout" not in str(e).lower():
            logger.error(f"Error cleaning scan_history: {e}")
        cleanup_summary.append(("scan_history (>7 days)", 0))
    
    # Clean ML features (>30 days)
    try:
        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        result = supabase.client.table("ml_features")\
            .delete()\
            .lt("timestamp", thirty_days_ago)\
            .execute()
        
        deleted = len(result.data) if result.data else 0
        cleanup_summary.append(("ml_features (>30 days)", deleted))
        logger.info(f"Deleted {deleted:,} rows from ml_features")
    except Exception as e:
        if "does not exist" not in str(e):
            logger.error(f"Error cleaning ml_features: {e}")
        cleanup_summary.append(("ml_features (>30 days)", 0))
    
    # Clean shadow testing tables
    try:
        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        result = supabase.client.table("shadow_testing_scans")\
            .delete()\
            .lt("scan_time", thirty_days_ago)\
            .execute()
        
        deleted = len(result.data) if result.data else 0
        cleanup_summary.append(("shadow_testing_scans (>30 days)", deleted))
        logger.info(f"Deleted {deleted:,} rows from shadow_testing_scans")
    except Exception as e:
        if "does not exist" not in str(e):
            logger.error(f"Error cleaning shadow_testing_scans: {e}")
        cleanup_summary.append(("shadow_testing_scans (>30 days)", 0))
    
    return cleanup_summary


def main():
    """Execute the cleanup."""
    
    logger.info("Starting data cleanup (fixed version)...")
    supabase = SupabaseClient()
    
    print("\n" + "="*80)
    print("🧹 DATA CLEANUP EXECUTION (FIXED)")
    print("="*80)
    print("\nThis will delete old data according to your retention policy.")
    print("Using date-range batching to avoid timeouts.\n")
    
    start_time = time.time()
    
    # Track all deletions
    cleanup_summary = []
    
    # 1. Clean 1-hour data (>2 years)
    print("📊 Cleaning 1-hour data older than 2 years...")
    print("-"*60)
    
    two_years_ago = (datetime.now(timezone.utc) - timedelta(days=730)).isoformat()
    deleted = cleanup_by_date_ranges(
        supabase, 
        "ohlc_data", 
        ["1h", "1hour"], 
        two_years_ago,
        days_per_batch=60  # 2-month chunks
    )
    cleanup_summary.append(("1-hour data (>2 years)", deleted))
    print(f"✅ Deleted {deleted:,} rows\n")
    
    # 2. Clean 15-minute data (>1 year) 
    print("📈 Cleaning 15-minute data older than 1 year...")
    print("-"*60)
    
    one_year_ago = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
    deleted = cleanup_by_date_ranges(
        supabase,
        "ohlc_data",
        ["15m", "15min"],
        one_year_ago,
        days_per_batch=30  # 1-month chunks
    )
    cleanup_summary.append(("15-minute data (>1 year)", deleted))
    print(f"✅ Deleted {deleted:,} rows\n")
    
    # 3. Clean 1-minute data (>30 days)
    print("🕐 Cleaning 1-minute data older than 30 days...")
    print("-"*60)
    
    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    deleted = cleanup_by_date_ranges(
        supabase,
        "ohlc_data",
        ["1m", "1min", "1"],
        thirty_days_ago,
        days_per_batch=7  # 1-week chunks for large dataset
    )
    cleanup_summary.append(("1-minute data (>30 days)", deleted))
    print(f"✅ Deleted {deleted:,} rows\n")
    
    # 4. Clean other tables
    print("📋 Cleaning other tables...")
    print("-"*60)
    
    other_results = cleanup_simple_tables(supabase)
    cleanup_summary.extend(other_results)
    print("✅ Other tables cleaned\n")
    
    # Calculate totals
    duration = time.time() - start_time
    total_deleted = sum(count for _, count in cleanup_summary)
    
    # Print summary
    print("\n" + "="*80)
    print("✨ CLEANUP COMPLETE")
    print("="*80)
    print(f"\nDuration: {duration:.1f} seconds")
    print(f"Total rows deleted: {total_deleted:,}\n")
    
    print("Summary by table:")
    for target, count in cleanup_summary:
        if count > 0:
            print(f"  ✅ {target}: {count:,} rows")
        else:
            print(f"  ⏭️  {target}: No rows to delete")
    
    print("\n" + "="*80)
    print("\n⚠️  IMPORTANT NEXT STEPS:")
    print("\n1. Run VACUUM in Supabase SQL Editor to reclaim disk space:")
    print("   VACUUM ANALYZE ohlc_data;")
    print("\n2. Verify the cleanup worked:")
    print("   python3 scripts/analyze_current_data.py")
    print("\n3. Set up daily cleanup cron:")
    print("   ./scripts/setup_data_retention_cron.sh")
    print("\n" + "="*80)
    

if __name__ == "__main__":
    response = input("⚠️  This will DELETE old data. Continue? (yes/no): ")
    if response.lower() == 'yes':
        main()
    else:
        print("Cleanup cancelled.")
