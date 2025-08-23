#!/usr/bin/env python3
"""
Check current storage usage and data retention status.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from loguru import logger


def main():
    """Check current data storage and retention status."""
    
    logger.info("Checking current data storage policy and usage...")
    supabase = SupabaseClient()
    
    print("\n" + "="*80)
    print("📊 CURRENT DATA STORAGE STATUS")
    print("="*80)
    
    # Check OHLC data timeframes and date ranges
    print("\n📈 OHLC DATA ANALYSIS:")
    print("-"*60)
    
    timeframes = ['1min', '1m', '15min', '15m', '1h', '1hour', '1d', '1day']
    total_ohlc_rows = 0
    
    for tf in timeframes:
        try:
            # Get count for this timeframe
            result = supabase.client.table("ohlc_data")\
                .select("*", count="exact", head=True)\
                .eq("timeframe", tf)\
                .execute()
            
            count = result.count if hasattr(result, 'count') else 0
            
            if count > 0:
                # Get date range
                oldest = supabase.client.table("ohlc_data")\
                    .select("timestamp")\
                    .eq("timeframe", tf)\
                    .order("timestamp")\
                    .limit(1)\
                    .execute()
                
                newest = supabase.client.table("ohlc_data")\
                    .select("timestamp")\
                    .eq("timeframe", tf)\
                    .order("timestamp", desc=True)\
                    .limit(1)\
                    .execute()
                
                oldest_date = oldest.data[0]['timestamp'] if oldest.data else "Unknown"
                newest_date = newest.data[0]['timestamp'] if newest.data else "Unknown"
                
                # Calculate age of oldest data
                if oldest_date != "Unknown":
                    oldest_dt = datetime.fromisoformat(oldest_date.replace('Z', '+00:00'))
                    age_days = (datetime.now(timezone.utc) - oldest_dt).days
                else:
                    age_days = 0
                
                print(f"\n{tf:6s}: {count:,} rows")
                print(f"  Date range: {oldest_date[:10]} to {newest_date[:10]}")
                print(f"  Oldest data: {age_days} days ago")
                
                total_ohlc_rows += count
                
        except Exception as e:
            if "does not exist" not in str(e):
                logger.debug(f"Couldn't check {tf}: {e}")
    
    print(f"\nTotal OHLC rows: {total_ohlc_rows:,}")
    
    # Check other tables
    print("\n📋 OTHER TABLES:")
    print("-"*60)
    
    tables = [
        ("scan_history", "timestamp"),
        ("shadow_testing_scans", "scan_time"),
        ("shadow_testing_trades", "created_at"),
        ("ml_features", "timestamp"),
        ("strategy_setups", "detected_at"),
    ]
    
    for table_name, date_field in tables:
        try:
            # Get row count
            result = supabase.client.table(table_name)\
                .select("*", count="exact", head=True)\
                .execute()
            
            count = result.count if hasattr(result, 'count') else 0
            
            if count > 0:
                # Get oldest entry
                oldest = supabase.client.table(table_name)\
                    .select(date_field)\
                    .order(date_field)\
                    .limit(1)\
                    .execute()
                
                if oldest.data and oldest.data[0][date_field]:
                    oldest_date = oldest.data[0][date_field]
                    oldest_dt = datetime.fromisoformat(oldest_date.replace('Z', '+00:00'))
                    age_days = (datetime.now(timezone.utc) - oldest_dt).days
                    
                    print(f"\n{table_name}: {count:,} rows")
                    print(f"  Oldest: {age_days} days ago ({oldest_date[:10]})")
                    
                    # Calculate growth rate for scan_history
                    if table_name == "scan_history" and age_days > 0:
                        daily_rate = count / age_days
                        print(f"  Growth rate: ~{daily_rate:.0f} rows/day")
                        print(f"  30-day projection: ~{daily_rate * 30:,.0f} rows")
                else:
                    print(f"\n{table_name}: {count:,} rows (no date info)")
                    
        except Exception as e:
            if "does not exist" not in str(e):
                logger.debug(f"Couldn't check {table_name}: {e}")
    
    # Current retention policy
    print("\n" + "="*80)
    print("📝 CURRENT DATA RETENTION POLICY:")
    print("="*80)
    
    print("""
Based on MASTER_PLAN.md and code analysis:

1. **CONFIGURED POLICY**: "FOREVER - All historical data"
   - No automatic deletion
   - No archival process running
   - No data retention limits

2. **ACTUAL IMPLEMENTATION**:
   - ❌ No cleanup scripts scheduled
   - ❌ No archival process active
   - ❌ No retention policies enforced
   - ✅ Archive table structure exists (migration 010)
   - ✅ OHLCManager has archive methods (not used)

3. **GROWTH PROJECTIONS** (at current rates):
   - scan_history: ~1.1 million rows/month
   - OHLC data: Growing continuously with 90 symbols
   - Storage cost: Will exceed free tier soon

4. **IMMEDIATE RISKS**:
   - 🚨 Runaway storage costs
   - 🚨 Query performance degradation
   - 🚨 Supabase timeouts on large tables
    """)
    
    # Recommendations
    print("\n" + "="*80)
    print("⚡ IMMEDIATE ACTIONS NEEDED:")
    print("="*80)
    
    print("""
1. **DELETE OLD SCAN DATA** (Safe, non-critical):
   DELETE FROM scan_history WHERE timestamp < NOW() - INTERVAL '7 days';
   
2. **ARCHIVE OLD OHLC** (Keep recent for trading):
   -- Move 15m data older than 30 days to archive
   -- Delete 1m data older than 7 days (if exists)
   
3. **IMPLEMENT DAILY CLEANUP**:
   -- Schedule via cron or Railway
   -- Run at 3 AM PST daily
   -- Monitor and adjust retention periods
    """)


if __name__ == "__main__":
    main()
