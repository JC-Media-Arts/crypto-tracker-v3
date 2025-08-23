-- Crypto Tracker Data Retention Policy Implementation (FIXED for PostgreSQL)
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

-- Check scan_history that will be deleted
SELECT 
    COUNT(*) as rows_to_delete,
    MIN(timestamp) as oldest_date,
    MAX(timestamp) as newest_date
FROM scan_history 
WHERE timestamp < NOW() - INTERVAL '7 days';

-- ============================================================================
-- STEP 2: CREATE ARCHIVE TABLES (Optional - if you want to keep old data)
-- ============================================================================

-- Create archive table with same structure
CREATE TABLE IF NOT EXISTS ohlc_data_archive (
    LIKE ohlc_data INCLUDING ALL
);

-- Optional: Archive old data before deletion (run in batches to avoid timeout)
-- Archive old 1-minute data (do this in chunks if needed)
INSERT INTO ohlc_data_archive
SELECT * FROM ohlc_data 
WHERE timeframe IN ('1m', '1min', '1')
AND timestamp < NOW() - INTERVAL '30 days'
AND NOT EXISTS (
    SELECT 1 FROM ohlc_data_archive a 
    WHERE a.timestamp = ohlc_data.timestamp 
    AND a.symbol = ohlc_data.symbol 
    AND a.timeframe = ohlc_data.timeframe
)
LIMIT 100000;  -- Process in chunks if needed

-- ============================================================================
-- STEP 3: DELETE OLD DATA (PostgreSQL compatible batch deletion)
-- ============================================================================

-- METHOD 1: Simple deletion (may timeout on large datasets)
-- Use this for smaller tables or if you're okay with potential timeouts

-- Delete old scan_history (usually smaller, safe to run directly)
DELETE FROM scan_history 
WHERE timestamp < NOW() - INTERVAL '7 days';

-- Delete old ML features
DELETE FROM ml_features 
WHERE timestamp < NOW() - INTERVAL '30 days';

-- Delete old shadow testing scans
DELETE FROM shadow_testing_scans 
WHERE scan_time < NOW() - INTERVAL '30 days';

-- ============================================================================
-- METHOD 2: Batch deletion using ctid (for large tables)
-- This is the PostgreSQL way to delete in chunks
-- ============================================================================

-- Delete old 1-minute data in batches (PostgreSQL compatible)
DO $$
DECLARE
    deleted_count INTEGER;
    total_deleted INTEGER := 0;
    batch_size INTEGER := 10000;
BEGIN
    LOOP
        -- Delete using ctid (physical row identifier)
        WITH batch AS (
            SELECT ctid
            FROM ohlc_data 
            WHERE timeframe IN ('1m', '1min', '1')
            AND timestamp < NOW() - INTERVAL '30 days'
            LIMIT batch_size
        )
        DELETE FROM ohlc_data
        WHERE ctid IN (SELECT ctid FROM batch);
        
        GET DIAGNOSTICS deleted_count = ROW_COUNT;
        total_deleted := total_deleted + deleted_count;
        
        -- Log progress
        RAISE NOTICE 'Deleted % rows (total: %)', deleted_count, total_deleted;
        
        -- Exit when no more rows to delete
        EXIT WHEN deleted_count < batch_size;
        
        -- Brief pause to avoid overload
        PERFORM pg_sleep(0.5);
    END LOOP;
    
    RAISE NOTICE 'Total 1-minute rows deleted: %', total_deleted;
END $$;

-- Delete old 15-minute data in batches
DO $$
DECLARE
    deleted_count INTEGER;
    total_deleted INTEGER := 0;
    batch_size INTEGER := 10000;
BEGIN
    LOOP
        WITH batch AS (
            SELECT ctid
            FROM ohlc_data 
            WHERE timeframe IN ('15m', '15min')
            AND timestamp < NOW() - INTERVAL '1 year'
            LIMIT batch_size
        )
        DELETE FROM ohlc_data
        WHERE ctid IN (SELECT ctid FROM batch);
        
        GET DIAGNOSTICS deleted_count = ROW_COUNT;
        total_deleted := total_deleted + deleted_count;
        
        RAISE NOTICE 'Deleted % rows (total: %)', deleted_count, total_deleted;
        
        EXIT WHEN deleted_count < batch_size;
        
        PERFORM pg_sleep(0.5);
    END LOOP;
    
    RAISE NOTICE 'Total 15-minute rows deleted: %', total_deleted;
END $$;

-- Delete old 1-hour data in batches
DO $$
DECLARE
    deleted_count INTEGER;
    total_deleted INTEGER := 0;
    batch_size INTEGER := 10000;
BEGIN
    LOOP
        WITH batch AS (
            SELECT ctid
            FROM ohlc_data 
            WHERE timeframe IN ('1h', '1hour')
            AND timestamp < NOW() - INTERVAL '2 years'
            LIMIT batch_size
        )
        DELETE FROM ohlc_data
        WHERE ctid IN (SELECT ctid FROM batch);
        
        GET DIAGNOSTICS deleted_count = ROW_COUNT;
        total_deleted := total_deleted + deleted_count;
        
        RAISE NOTICE 'Deleted % rows (total: %)', deleted_count, total_deleted;
        
        EXIT WHEN deleted_count < batch_size;
        
        PERFORM pg_sleep(0.5);
    END LOOP;
    
    RAISE NOTICE 'Total 1-hour rows deleted: %', total_deleted;
END $$;

-- ============================================================================
-- METHOD 3: Alternative using temporary table (for very large deletions)
-- Use this if Method 2 is still too slow
-- ============================================================================

-- Example for 1-minute data using temporary table
/*
-- Create temp table with rows to keep
CREATE TEMP TABLE ohlc_data_keep AS
SELECT * FROM ohlc_data 
WHERE NOT (
    timeframe IN ('1m', '1min', '1') 
    AND timestamp < NOW() - INTERVAL '30 days'
);

-- Truncate original table
TRUNCATE TABLE ohlc_data;

-- Re-insert kept data
INSERT INTO ohlc_data
SELECT * FROM ohlc_data_keep;

-- Drop temp table
DROP TABLE ohlc_data_keep;
*/

-- ============================================================================
-- STEP 4: OPTIMIZE TABLES AFTER CLEANUP
-- ============================================================================

-- Reclaim space and update statistics
VACUUM ANALYZE ohlc_data;
VACUUM ANALYZE scan_history;
VACUUM ANALYZE ml_features;

-- ============================================================================
-- STEP 5: CREATE INDEXES FOR BETTER PERFORMANCE
-- ============================================================================

-- Create optimized indexes if they don't exist
CREATE INDEX IF NOT EXISTS idx_ohlc_timeframe_timestamp 
ON ohlc_data(timeframe, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_ohlc_symbol_timeframe_timestamp 
ON ohlc_data(symbol, timeframe, timestamp DESC);

-- ============================================================================
-- STEP 6: VERIFY RESULTS
-- ============================================================================

-- Check final row counts by timeframe
SELECT 
    timeframe,
    COUNT(*) as row_count,
    MIN(timestamp) as oldest,
    MAX(timestamp) as newest,
    EXTRACT(DAY FROM (MAX(timestamp) - MIN(timestamp))) as days_retained
FROM ohlc_data
GROUP BY timeframe
ORDER BY timeframe;

-- Check total rows remaining
SELECT 
    'ohlc_data' as table_name,
    COUNT(*) as total_rows
FROM ohlc_data
UNION ALL
SELECT 
    'scan_history' as table_name,
    COUNT(*) as total_rows
FROM scan_history
UNION ALL
SELECT 
    'ml_features' as table_name,
    COUNT(*) as total_rows
FROM ml_features;

-- ============================================================================
-- QUICK CLEANUP OPTIONS (Choose based on your situation)
-- ============================================================================

-- OPTION A: Quick cleanup of scan_history (safe, fast)
-- This alone can free significant space
DELETE FROM scan_history WHERE timestamp < NOW() - INTERVAL '7 days';

-- OPTION B: Aggressive 1-minute cleanup (if you need space NOW)
-- Only keeps last 7 days of 1-minute data
DELETE FROM ohlc_data 
WHERE timeframe IN ('1m', '1min', '1')
AND timestamp < NOW() - INTERVAL '7 days';

-- OPTION C: Nuclear option - delete ALL 1-minute data
-- Use only if you don't need 1-minute data at all
-- DELETE FROM ohlc_data WHERE timeframe IN ('1m', '1min', '1');
