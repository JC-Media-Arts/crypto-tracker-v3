#!/usr/bin/env python3
"""
Execute data cleanup according to approved retention policy.
Handles timeouts gracefully with batch processing.

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


def cleanup_in_batches(supabase, table, timeframe_list, cutoff_date, batch_size=1000):
    """
    Clean up data in small batches to avoid timeouts.
    """
    total_deleted = 0
    
    for tf in timeframe_list:
        logger.info(f"Cleaning {table} where timeframe='{tf}' before {cutoff_date[:10]}")
        batch_deleted = 0
        attempts = 0
        max_attempts = 100  # Safety limit
        
        while attempts < max_attempts:
            try:
                # Delete a batch
                result = supabase.client.table(table)\
                    .delete()\
                    .eq("timeframe", tf)\
                    .lt("timestamp", cutoff_date)\
                    .limit(batch_size)\
                    .execute()
                
                deleted_count = len(result.data) if result.data else 0
                batch_deleted += deleted_count
                total_deleted += deleted_count
                
                if deleted_count == 0:
                    logger.info(f"  Completed {tf}: {batch_deleted:,} rows deleted")
                    break
                
                if batch_deleted % 10000 == 0:
                    logger.info(f"  Progress: {batch_deleted:,} rows deleted...")
                
                # Brief pause between batches
                time.sleep(0.2)
                attempts += 1
                
            except Exception as e:
                logger.error(f"  Error on batch: {str(e)[:100]}")
                time.sleep(1)
                attempts += 1
                
                if "timeout" in str(e).lower():
                    # Reduce batch size on timeout
                    batch_size = max(100, batch_size // 2)
                    logger.info(f"  Reduced batch size to {batch_size}")
    
    return total_deleted


def main():
    """Execute the cleanup."""
    
    logger.info("Starting data cleanup...")
    supabase = SupabaseClient()
    
    print("\n" + "="*80)
    print("🧹 DATA CLEANUP EXECUTION")
    print("="*80)
    print("\nThis will delete old data according to your retention policy.")
    print("The process may take several minutes.\n")
    
    start_time = time.time()
    
    # Track all deletions
    cleanup_summary = []
    
    # 1. Clean 1-hour data (>2 years)
    print("📊 Cleaning 1-hour data older than 2 years...")
    print("-"*60)
    
    two_years_ago = (datetime.now(timezone.utc) - timedelta(days=730)).isoformat()
    deleted = cleanup_in_batches(
        supabase, 
        "ohlc_data", 
        ["1h", "1hour"], 
        two_years_ago,
        batch_size=5000
    )
    cleanup_summary.append(("1-hour data (>2 years)", deleted))
    print(f"✅ Deleted {deleted:,} rows\n")
    
    # 2. Clean 15-minute data (>1 year)
    print("📈 Cleaning 15-minute data older than 1 year...")
    print("-"*60)
    
    one_year_ago = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
    deleted = cleanup_in_batches(
        supabase,
        "ohlc_data",
        ["15m", "15min"],
        one_year_ago,
        batch_size=2000  # Smaller batches for larger dataset
    )
    cleanup_summary.append(("15-minute data (>1 year)", deleted))
    print(f"✅ Deleted {deleted:,} rows\n")
    
    # 3. Clean 1-minute data (>30 days) - if any exists
    print("🕐 Cleaning 1-minute data older than 30 days...")
    print("-"*60)
    
    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    deleted = cleanup_in_batches(
        supabase,
        "ohlc_data",
        ["1m", "1min", "1"],
        thirty_days_ago,
        batch_size=1000  # Small batches for huge dataset
    )
    cleanup_summary.append(("1-minute data (>30 days)", deleted))
    print(f"✅ Deleted {deleted:,} rows\n")
    
    # 4. Clean scan_history (>7 days)
    print("📋 Cleaning scan_history older than 7 days...")
    print("-"*60)
    
    try:
        seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        result = supabase.client.table("scan_history")\
            .delete()\
            .lt("timestamp", seven_days_ago)\
            .execute()
        
        deleted = len(result.data) if result.data else 0
        cleanup_summary.append(("scan_history (>7 days)", deleted))
        print(f"✅ Deleted {deleted:,} rows\n")
    except Exception as e:
        logger.error(f"Error cleaning scan_history: {e}")
        cleanup_summary.append(("scan_history (>7 days)", 0))
    
    # 5. Clean ML features (>30 days)
    print("🤖 Cleaning ML features older than 30 days...")
    print("-"*60)
    
    try:
        result = supabase.client.table("ml_features")\
            .delete()\
            .lt("timestamp", thirty_days_ago)\
            .execute()
        
        deleted = len(result.data) if result.data else 0
        cleanup_summary.append(("ml_features (>30 days)", deleted))
        print(f"✅ Deleted {deleted:,} rows\n")
    except Exception as e:
        if "does not exist" not in str(e):
            logger.error(f"Error cleaning ml_features: {e}")
        cleanup_summary.append(("ml_features (>30 days)", 0))
    
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
        print(f"  • {target}: {count:,} rows")
    
    print("\n" + "="*80)
    print("\n⚠️  IMPORTANT: Run VACUUM in Supabase to reclaim disk space:")
    print("  VACUUM ANALYZE ohlc_data;")
    print("\nThis will free up the actual disk space from deleted rows.")
    

if __name__ == "__main__":
    response = input("⚠️  This will DELETE old data. Continue? (yes/no): ")
    if response.lower() == 'yes':
        main()
    else:
        print("Cleanup cancelled.")
