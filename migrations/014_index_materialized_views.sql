-- Create Indexes on Materialized Views
-- These should be FAST since the views are small

-- ============================================================
-- INDEXES FOR ohlc_recent (7 days of data)
-- ============================================================

-- Primary composite index
CREATE INDEX IF NOT EXISTS idx_recent_symbol_time
ON ohlc_recent(symbol, timeframe, timestamp DESC);

-- Symbol-only index for quick lookups
CREATE INDEX IF NOT EXISTS idx_recent_symbol
ON ohlc_recent(symbol, timestamp DESC);

-- Timeframe index
CREATE INDEX IF NOT EXISTS idx_recent_timeframe
ON ohlc_recent(timeframe, timestamp DESC);

-- BRIN index for time queries (very efficient)
CREATE INDEX IF NOT EXISTS idx_recent_timestamp_brin
ON ohlc_recent USING BRIN(timestamp);

-- ============================================================
-- INDEXES FOR ohlc_today (24 hours of data)
-- ============================================================

-- Primary composite index
CREATE INDEX IF NOT EXISTS idx_today_symbol_time
ON ohlc_today(symbol, timeframe, timestamp DESC);

-- Symbol-only index
CREATE INDEX IF NOT EXISTS idx_today_symbol
ON ohlc_today(symbol, timestamp DESC);

-- ============================================================
-- GRANT PERMISSIONS
-- ============================================================

-- Grant read access to the views
GRANT SELECT ON ohlc_recent TO authenticated;
GRANT SELECT ON ohlc_recent TO anon;
GRANT SELECT ON ohlc_today TO authenticated;
GRANT SELECT ON ohlc_today TO anon;

-- ============================================================
-- VERIFY EVERYTHING WORKED
-- ============================================================

-- Check view sizes
SELECT
    'ohlc_recent' as view_name,
    pg_size_pretty(pg_relation_size('ohlc_recent')) as size,
    COUNT(*) as row_count
FROM ohlc_recent
UNION ALL
SELECT
    'ohlc_today' as view_name,
    pg_size_pretty(pg_relation_size('ohlc_today')) as size,
    COUNT(*) as row_count
FROM ohlc_today;

-- Check indexes were created
SELECT
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size
FROM pg_indexes
WHERE tablename IN ('ohlc_recent', 'ohlc_today')
ORDER BY tablename, indexname;

-- ============================================================
-- SET UP REFRESH SCHEDULE (Run these separately)
-- ============================================================

-- Option 1: Manual refresh (run this daily via cron job)
REFRESH MATERIALIZED VIEW CONCURRENTLY ohlc_recent;
REFRESH MATERIALIZED VIEW CONCURRENTLY ohlc_today;

-- Option 2: Create a function to refresh both
CREATE OR REPLACE FUNCTION refresh_ohlc_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY ohlc_recent;
    REFRESH MATERIALIZED VIEW CONCURRENTLY ohlc_today;
END;
$$ LANGUAGE plpgsql;

-- Call the function to refresh
-- SELECT refresh_ohlc_views();
