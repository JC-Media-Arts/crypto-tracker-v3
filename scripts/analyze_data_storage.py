#!/usr/bin/env python3
"""
Analyze current data storage usage in Supabase and recommend retention policies.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict

sys.path.append(str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from src.data.supabase_client import SupabaseClient
from loguru import logger


def analyze_storage():
    """Analyze current storage usage and recommend retention policies."""
    
    logger.info("Starting data storage analysis...")
    supabase = SupabaseClient()
    
    print("\n" + "="*80)
    print("📊 CRYPTO DATA STORAGE ANALYSIS")
    print("="*80)
    
    # Tables to analyze
    tables_to_check = [
        ("ohlc_data", "Main OHLC data"),
        ("unified_ohlc", "Unified OHLC (if exists)"),
        ("ml_features", "ML Features"),
        ("strategy_setups", "Strategy Setups"),
        ("scan_history", "Scan History"),
        ("shadow_testing_scans", "Shadow Testing Scans"),
        ("shadow_testing_trades", "Shadow Testing Trades"),
        ("hummingbot_trades", "Hummingbot Trades"),
        ("positions", "Positions"),
        ("trades", "Trades")
    ]
    
    total_rows = 0
    storage_by_table = {}
    
    print("\n📋 TABLE ANALYSIS:")
    print("-"*60)
    
    for table_name, description in tables_to_check:
        try:
            # Get row count with timeout handling
            result = supabase.client.table(table_name).select("*", count="exact", head=True).execute()
            row_count = result.count if hasattr(result, 'count') else 0
            
            if row_count > 0:
                # Get date range
                oldest = supabase.client.table(table_name).select("created_at,timestamp").order("created_at").limit(1).execute()
                newest = supabase.client.table(table_name).select("created_at,timestamp").order("created_at", desc=True).limit(1).execute()
                
                oldest_date = "Unknown"
                newest_date = "Unknown"
                
                if oldest.data and len(oldest.data) > 0:
                    # Try different date field names
                    if 'timestamp' in oldest.data[0]:
                        oldest_date = oldest.data[0]['timestamp']
                    elif 'created_at' in oldest.data[0]:
                        oldest_date = oldest.data[0]['created_at']
                
                if newest.data and len(newest.data) > 0:
                    if 'timestamp' in newest.data[0]:
                        newest_date = newest.data[0]['timestamp']
                    elif 'created_at' in newest.data[0]:
                        newest_date = newest.data[0]['created_at']
                
                # Estimate storage (rough approximation)
                avg_row_size = 100  # bytes, conservative estimate
                if 'ohlc' in table_name.lower():
                    avg_row_size = 150  # OHLC data is larger
                elif 'features' in table_name.lower():
                    avg_row_size = 300  # ML features are largest
                
                estimated_size_mb = (row_count * avg_row_size) / (1024 * 1024)
                
                print(f"\n✅ {description} ({table_name}):")
                print(f"   Rows: {row_count:,}")
                print(f"   Date range: {oldest_date[:10] if oldest_date != 'Unknown' else 'Unknown'} to {newest_date[:10] if newest_date != 'Unknown' else 'Unknown'}")
                print(f"   Est. size: {estimated_size_mb:.2f} MB")
                
                storage_by_table[table_name] = {
                    'rows': row_count,
                    'size_mb': estimated_size_mb,
                    'oldest': oldest_date,
                    'newest': newest_date
                }
                total_rows += row_count
                
        except Exception as e:
            if "does not exist" not in str(e):
                print(f"\n⚠️  {description} ({table_name}): Error - {str(e)[:50]}...")
    
    # Analyze OHLC data specifically
    print("\n" + "="*80)
    print("🕐 OHLC DATA BREAKDOWN BY TIMEFRAME:")
    print("-"*60)
    
    try:
        # Check different timeframes
        timeframes = ['1min', '1m', '15min', '15m', '1h', '1hour', '1d', '1day']
        
        for tf in timeframes:
            try:
                result = supabase.client.table("ohlc_data")\
                    .select("*", count="exact", head=True)\
                    .eq("timeframe", tf)\
                    .execute()
                
                count = result.count if hasattr(result, 'count') else 0
                if count > 0:
                    # Calculate storage impact
                    days_of_data = count / (90 * 1440) if tf in ['1min', '1m'] else \
                                  count / (90 * 96) if tf in ['15min', '15m'] else \
                                  count / (90 * 24) if tf in ['1h', '1hour'] else \
                                  count / 90
                    
                    size_mb = (count * 150) / (1024 * 1024)
                    
                    print(f"\n  {tf:6s}: {count:10,} rows | ~{days_of_data:.1f} days | ~{size_mb:.1f} MB")
                    
            except:
                pass
                
    except Exception as e:
        print(f"Could not analyze OHLC timeframes: {e}")
    
    # Calculate total estimated storage
    total_storage_mb = sum(t['size_mb'] for t in storage_by_table.values())
    total_storage_gb = total_storage_mb / 1024
    
    print("\n" + "="*80)
    print("💾 STORAGE SUMMARY:")
    print("-"*60)
    print(f"\n  Total rows across all tables: {total_rows:,}")
    print(f"  Estimated total storage: {total_storage_gb:.2f} GB")
    
    # Provide recommendations
    print("\n" + "="*80)
    print("📝 RECOMMENDED RETENTION POLICIES:")
    print("="*80)
    
    print("""
1. **1-MINUTE DATA** (Highest storage impact)
   - KEEP: Last 30 days for active trading
   - ARCHIVE: 30-90 days to cold storage
   - DELETE: Older than 90 days
   - Rationale: Recent data needed for backtesting, older data rarely accessed
   
2. **15-MINUTE DATA**
   - KEEP: Last 6 months for ML training
   - ARCHIVE: 6-12 months
   - DELETE: Older than 1 year
   - Rationale: Primary timeframe for strategies, needed for ML
   
3. **1-HOUR DATA**
   - KEEP: Last 1 year for trend analysis
   - ARCHIVE: 1-2 years
   - KEEP SUMMARY: 2+ years (daily high/low/close only)
   - Rationale: Useful for longer-term patterns
   
4. **ML FEATURES**
   - KEEP: Last 3 months (regenerate as needed)
   - DELETE: Older than 3 months
   - Rationale: Can be recalculated from OHLC data
   
5. **SCAN HISTORY / SHADOW DATA**
   - KEEP: Last 30 days for analysis
   - AGGREGATE: 30-90 days (daily summaries)
   - DELETE: Raw data older than 90 days
   - Rationale: Recent data most relevant for optimization
    """)
    
    # Implementation steps
    print("\n" + "="*80)
    print("🚀 IMPLEMENTATION STEPS:")
    print("="*80)
    
    print("""
1. **IMMEDIATE ACTIONS** (Reduce storage now):
   ```sql
   -- Delete old scan history (>30 days)
   DELETE FROM scan_history WHERE timestamp < NOW() - INTERVAL '30 days';
   
   -- Delete old shadow testing scans (>30 days)
   DELETE FROM shadow_testing_scans WHERE scan_time < NOW() - INTERVAL '30 days';
   
   -- Delete old ML features (>90 days)
   DELETE FROM ml_features WHERE timestamp < NOW() - INTERVAL '90 days';
   ```

2. **CREATE ARCHIVE TABLES**:
   ```sql
   -- Create archive for old OHLC data
   CREATE TABLE ohlc_data_archive (LIKE ohlc_data INCLUDING ALL);
   
   -- Move old 1-minute data to archive
   INSERT INTO ohlc_data_archive 
   SELECT * FROM ohlc_data 
   WHERE timeframe = '1min' AND timestamp < NOW() - INTERVAL '30 days';
   
   DELETE FROM ohlc_data 
   WHERE timeframe = '1min' AND timestamp < NOW() - INTERVAL '30 days';
   ```

3. **SET UP AUTOMATED CLEANUP**:
   - Create a daily cron job to move/delete old data
   - Run during low-traffic hours (3 AM PST)
   - Monitor storage usage weekly

4. **OPTIMIZE EXISTING DATA**:
   - Create materialized views for frequently accessed aggregations
   - Use BRIN indexes for time-series data
   - Partition large tables by month
    """)
    
    # Cost analysis
    print("\n" + "="*80)
    print("💰 COST IMPACT:")
    print("="*80)
    
    if total_storage_gb > 8:
        extra_gb = total_storage_gb - 8
        monthly_cost = extra_gb * 0.125
        
        print(f"\n  Current storage: {total_storage_gb:.2f} GB")
        print(f"  Supabase Pro includes: 8 GB")
        print(f"  Extra storage: {extra_gb:.2f} GB")
        print(f"  Additional monthly cost: ${monthly_cost:.2f}")
        
        # After cleanup estimate
        cleanup_reduction = 0.4  # Assume 40% reduction
        new_storage = total_storage_gb * (1 - cleanup_reduction)
        new_extra = max(0, new_storage - 8)
        new_cost = new_extra * 0.125
        
        print(f"\n  After cleanup (40% reduction):")
        print(f"  New storage: {new_storage:.2f} GB")
        print(f"  New monthly cost: ${new_cost:.2f}")
        print(f"  Monthly savings: ${monthly_cost - new_cost:.2f}")
    else:
        print(f"\n  Current storage ({total_storage_gb:.2f} GB) fits within Supabase Pro tier (8 GB)")
    
    print("\n" + "="*80)
    

if __name__ == "__main__":
    analyze_storage()
