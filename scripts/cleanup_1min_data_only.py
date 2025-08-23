#!/usr/bin/env python3
"""
Clean up only 1-minute data that's older than 30 days.
This is a focused script to handle the problematic 1-minute data cleanup.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
import time

sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from loguru import logger


def cleanup_1min_data_smart(supabase):
    """
    Clean up 1-minute data with smart batching and proper error handling.
    Starts with small batches and increases size when successful.
    """
    table = "ohlc_data"
    timeframes = ["1m", "1min", "1"]
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    
    total_deleted = 0
    
    for tf in timeframes:
        logger.info(f"Cleaning {table} where timeframe='{tf}' before {thirty_days_ago.date()}")
        
        # Start with very small batches (1 day) and increase on success
        batch_days = 1
        max_batch_days = 7
        
        # Start from 30 days ago and work backwards
        end_date = thirty_days_ago
        oldest_date = thirty_days_ago - timedelta(days=365)  # Only go back 1 year max
        
        consecutive_successes = 0
        consecutive_failures = 0
        max_failures = 3
        
        while end_date > oldest_date:
            start_date = end_date - timedelta(days=batch_days)
            
            # Make sure we don't go past our oldest date
            if start_date < oldest_date:
                start_date = oldest_date
            
            try:
                logger.info(f"  Attempting to delete {tf} from {start_date.date()} to {end_date.date()} ({batch_days} day batch)")
                
                # Delete data in this date range (small batches to avoid timeouts)
                result = supabase.client.table(table)\
                    .delete()\
                    .eq("timeframe", tf)\
                    .gte("timestamp", start_date.isoformat())\
                    .lt("timestamp", end_date.isoformat())\
                    .execute()
                
                deleted_count = len(result.data) if result.data else 0
                total_deleted += deleted_count
                
                if deleted_count > 0:
                    logger.success(f"    ✓ Deleted {deleted_count:,} rows")
                else:
                    logger.info(f"    No data found in this range")
                
                # Success! Update counters
                consecutive_successes += 1
                consecutive_failures = 0
                
                # If we've had multiple successes, try increasing batch size
                if consecutive_successes >= 3 and batch_days < max_batch_days:
                    batch_days = min(max_batch_days, batch_days + 1)
                    logger.info(f"    Increasing batch size to {batch_days} days")
                    consecutive_successes = 0
                
                # Move to next batch (older data)
                end_date = start_date
                
                # Brief pause to avoid overwhelming the database
                time.sleep(0.2)
                
            except Exception as e:
                error_msg = str(e)
                consecutive_failures += 1
                consecutive_successes = 0
                
                logger.warning(f"    ⚠ Error (attempt {consecutive_failures}/{max_failures}): {error_msg[:100]}")
                
                if consecutive_failures >= max_failures:
                    if batch_days > 1:
                        # Reduce batch size
                        batch_days = max(1, batch_days // 2)
                        consecutive_failures = 0
                        logger.info(f"    Reducing batch size to {batch_days} days")
                    else:
                        # Already at minimum batch size, skip this range
                        logger.error(f"    ✗ Failed to delete range, skipping to next")
                        end_date = start_date
                        consecutive_failures = 0
                        batch_days = 1  # Reset to minimum for next range
                
                # Longer pause after error
                time.sleep(2)
        
        logger.info(f"  Completed {tf}: {total_deleted:,} total rows deleted so far")
    
    return total_deleted


def main():
    """Execute focused 1-minute data cleanup."""
    
    print("\n" + "="*80)
    print("🕐 1-MINUTE DATA CLEANUP")
    print("="*80)
    print("\nThis script focuses ONLY on cleaning 1-minute data older than 30 days.")
    print("It uses smart batching to handle timeouts and large datasets.\n")
    
    response = input("⚠️  This will DELETE old 1-minute data. Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Cleanup cancelled.")
        return
    
    logger.info("Starting 1-minute data cleanup...")
    supabase = SupabaseClient()
    
    start_time = time.time()
    
    try:
        total_deleted = cleanup_1min_data_smart(supabase)
        
        duration = time.time() - start_time
        
        print("\n" + "="*80)
        print("✨ CLEANUP COMPLETE")
        print("="*80)
        print(f"\nDuration: {duration:.1f} seconds")
        print(f"Total rows deleted: {total_deleted:,}")
        
        if total_deleted > 0:
            print("\n⚠️  Next steps:")
            print("1. Run VACUUM in Supabase SQL Editor:")
            print("   VACUUM ANALYZE ohlc_data;")
            print("\n2. Verify the cleanup:")
            print("   python3 scripts/check_data_coverage.py")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Cleanup interrupted by user")
        print("The cleanup was partially completed. You can run it again to continue.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"\n❌ Cleanup failed: {e}")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    main()
