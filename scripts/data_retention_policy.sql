-- Crypto Tracker Data Retention Policy Implementation
-- Created: 2024-08-21
-- 
-- APPROVED RETENTION POLICY:
-- - Daily data: keep forever
-- - 1 Hour data: keep 2 years  
-- - 15 minute data: keep 1 year
-- - 1 minute data: keep 30 days
--
-- WARNING: Run these queries during low-traffic hours (3 AM PST recommended)
-- IMPORTANT: Create backups before running any DELETE operations

-- ============================================================================
-- STEP 1: VERIFY CURRENT DATA (Run these first to understand impact)
-- ============================================================================

-- Check 1-minute data that will be deleted
SELECT 
    COUNT(*) as rows_to_delete,
    MIN(timestamp) as oldest_date,
    MAX(timestamp) as newest_date
FROM ohlc_data 
WHERE timeframe IN ('1m', '1min', '1')
AND timestamp < NOW() - INTERVAL '30 days';

-- Check 15-minute data that will be deleted
SELECT 
    COUNT(*) as rows_to_delete,
    MIN(timestamp) as oldest_date,
    MAX(timestamp) as newest_date
FROM ohlc_data 
WHERE timeframe IN ('15m', '15min')
AND timestamp < NOW() - INTERVAL '1 year';

-- Check 1-hour data that will be deleted
SELECT 
    COUNT(*) as rows_to_delete,
    MIN(timestamp) as oldest_date,
    MAX(timestamp) as newest_date
FROM ohlc_data 
WHERE timeframe IN ('1h', '1hour')
AND timestamp < NOW() - INTERVAL '2 years';

-- ============================================================================
-- STEP 2: CREATE ARCHIVE TABLES (Optional - if you want to keep old data)
-- ============================================================================

-- Create archive table with same structure
CREATE TABLE IF NOT EXISTS ohlc_data_archive (
    LIKE ohlc_data INCLUDING ALL
);

-- Optional: Archive old data before deletion (run in batches to avoid timeout)
-- Archive old 1-minute data
INSERT INTO ohlc_data_archive
SELECT * FROM ohlc_data 
WHERE timeframe IN ('1m', '1min', '1')
AND timestamp < NOW() - INTERVAL '30 days'
LIMIT 100000;  -- Process in chunks

-- ============================================================================
-- STEP 3: DELETE OLD DATA (Run in batches to avoid timeout)
-- ============================================================================

-- Delete old 1-minute data (RUN IN BATCHES)
-- This is the most critical cleanup - will free the most space
DO $$
DECLARE
    deleted_count INTEGER;
    total_deleted INTEGER := 0;
BEGIN
    LOOP
        DELETE FROM ohlc_data 
        WHERE timeframe IN ('1m', '1min', '1')
        AND timestamp < NOW() - INTERVAL '30 days'
        LIMIT 10000;  -- Delete in chunks of 10K rows
        
        GET DIAGNOSTICS deleted_count = ROW_COUNT;
        total_deleted := total_deleted + deleted_count;
        
        -- Log progress
        RAISE NOTICE 'Deleted % rows (total: %)', deleted_count, total_deleted;
        
        EXIT WHEN deleted_count = 0;
        
        -- Brief pause to avoid overload
        PERFORM pg_sleep(0.5);
    END LOOP;
    
    RAISE NOTICE 'Total 1-minute rows deleted: %', total_deleted;
END $$;

-- Delete old 15-minute data (RUN IN BATCHES)
DO $$
DECLARE
    deleted_count INTEGER;
    total_deleted INTEGER := 0;
BEGIN
    LOOP
        DELETE FROM ohlc_data 
        WHERE timeframe IN ('15m', '15min')
        AND timestamp < NOW() - INTERVAL '1 year'
        LIMIT 10000;
        
        GET DIAGNOSTICS deleted_count = ROW_COUNT;
        total_deleted := total_deleted + deleted_count;
        
        RAISE NOTICE 'Deleted % rows (total: %)', deleted_count, total_deleted;
        
        EXIT WHEN deleted_count = 0;
        
        PERFORM pg_sleep(0.5);
    END LOOP;
    
    RAISE NOTICE 'Total 15-minute rows deleted: %', total_deleted;
END $$;

-- Delete old 1-hour data (RUN IN BATCHES)
DO $$
DECLARE
    deleted_count INTEGER;
    total_deleted INTEGER := 0;
BEGIN
    LOOP
        DELETE FROM ohlc_data 
        WHERE timeframe IN ('1h', '1hour')
        AND timestamp < NOW() - INTERVAL '2 years'
        LIMIT 10000;
        
        GET DIAGNOSTICS deleted_count = ROW_COUNT;
        total_deleted := total_deleted + deleted_count;
        
        RAISE NOTICE 'Deleted % rows (total: %)', deleted_count, total_deleted;
        
        EXIT WHEN deleted_count = 0;
        
        PERFORM pg_sleep(0.5);
    END LOOP;
    
    RAISE NOTICE 'Total 1-hour rows deleted: %', total_deleted;
END $$;

-- ============================================================================
-- STEP 4: CLEAN OTHER TABLES
-- ============================================================================

-- Clean scan_history (keep 7 days only)
DELETE FROM scan_history 
WHERE timestamp < NOW() - INTERVAL '7 days';

-- Clean ML features (keep 30 days)
DELETE FROM ml_features 
WHERE timestamp < NOW() - INTERVAL '30 days';

-- Clean shadow testing scans (keep 30 days)
DELETE FROM shadow_testing_scans 
WHERE scan_time < NOW() - INTERVAL '30 days';

-- Clean shadow testing trades (keep 30 days)
DELETE FROM shadow_testing_trades 
WHERE created_at < NOW() - INTERVAL '30 days';

-- ============================================================================
-- STEP 5: OPTIMIZE TABLES AFTER CLEANUP
-- ============================================================================

-- Reclaim space and update statistics
VACUUM ANALYZE ohlc_data;
VACUUM ANALYZE scan_history;
VACUUM ANALYZE ml_features;

-- ============================================================================
-- STEP 6: CREATE INDEXES FOR BETTER PERFORMANCE
-- ============================================================================

-- Create optimized indexes if they don't exist
CREATE INDEX IF NOT EXISTS idx_ohlc_timeframe_timestamp 
ON ohlc_data(timeframe, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_ohlc_symbol_timeframe_timestamp 
ON ohlc_data(symbol, timeframe, timestamp DESC);

-- ============================================================================
-- STEP 7: VERIFY RESULTS
-- ============================================================================

-- Check final row counts
SELECT 
    timeframe,
    COUNT(*) as row_count,
    MIN(timestamp) as oldest,
    MAX(timestamp) as newest,
    MAX(timestamp) - MIN(timestamp) as retention_period
FROM ohlc_data
GROUP BY timeframe
ORDER BY timeframe;

-- Check space usage (approximate)
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE tablename IN ('ohlc_data', 'scan_history', 'ml_features')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
