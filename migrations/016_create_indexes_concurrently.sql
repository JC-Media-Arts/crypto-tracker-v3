-- ============================================================
-- CREATE INDEXES WITH CONCURRENTLY (No Table Locks)
-- Run this during low-traffic period for best performance
-- Estimated time: 1-3 hours total
-- ============================================================

-- Step 1: Set a very long timeout for your session
SET statement_timeout = '14400000';  -- 4 hours

-- Step 2: Create the most important index first (might take 1-2 hours)
-- This covers the most common query pattern: symbol + timeframe + time ordering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_symbol_time
ON ohlc_data(symbol, timeframe, timestamp DESC);

-- Step 3: Create BRIN index for time-series (fast, ~5-10 minutes)
-- BRIN is extremely efficient for timestamp columns with natural ordering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_timestamp_brin
ON ohlc_data USING BRIN(timestamp);

-- Step 4: Create partial index for recent data (faster queries for last 90 days)
-- Using a fixed date to avoid the IMMUTABLE function requirement
-- You'll need to recreate this periodically (e.g., monthly) with a new date
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_recent_90d
ON ohlc_data(symbol, timeframe, timestamp DESC)
WHERE timestamp > '2024-10-22'::timestamptz;  -- 90 days before today (Jan 20, 2025)

-- ============================================================
-- MONITORING QUERIES (Run in separate session)
-- ============================================================

-- Check index creation progress
-- SELECT
--     pid,
--     now() - pg_stat_activity.query_start AS duration,
--     query
-- FROM pg_stat_activity
-- WHERE query LIKE '%CREATE INDEX%'
-- AND state = 'active';

-- Check index sizes after creation
-- SELECT
--     schemaname,
--     tablename,
--     indexname,
--     pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size
-- FROM pg_indexes
-- WHERE tablename = 'ohlc_data'
-- ORDER BY pg_relation_size(indexname::regclass) DESC;

-- ============================================================
-- NOTES
-- ============================================================
-- 1. CONCURRENTLY prevents table locks but takes longer
-- 2. You can monitor progress in pg_stat_activity
-- 3. If any index fails, you can retry just that one
-- 4. These indexes complement your materialized views:
--    - Views handle recent data (fast)
--    - These indexes help with historical queries
-- 5. The partial index date needs periodic updates
