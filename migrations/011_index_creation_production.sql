-- Production-Safe Index Creation with CONCURRENTLY
-- Run these scripts in order, monitoring progress between each

-- ============================================================
-- STEP 1: TEST THE WATERS (Run First)
-- ============================================================
-- This tests if CONCURRENTLY works with extended timeout
SET statement_timeout = '300000';  -- 5 minutes

-- Create a tiny test index first
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_test
ON ohlc_data(timestamp DESC)
WHERE timestamp > CURRENT_DATE - INTERVAL '1 day';

-- Verify it worked
SELECT indexname, pg_size_pretty(pg_relation_size(indexname::regclass)) as size
FROM pg_indexes
WHERE tablename = 'ohlc_data' AND indexname = 'idx_ohlc_test';

-- If successful, drop the test and proceed
-- DROP INDEX CONCURRENTLY IF EXISTS idx_ohlc_test;

-- ============================================================
-- STEP 2: CREATE CRITICAL INDEXES (Run Tonight During Low Traffic)
-- ============================================================
-- Set generous timeout for the session
SET statement_timeout = '3600000';  -- 60 minutes

-- Index 1: Most recent data for real-time trading (will complete quickly)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_recent_7d
ON ohlc_data(symbol, timeframe, timestamp DESC)
WHERE timestamp > CURRENT_DATE - INTERVAL '7 days';

-- Verify Index 1
SELECT indexname, pg_size_pretty(pg_relation_size(indexname::regclass)) as size
FROM pg_indexes
WHERE tablename = 'ohlc_data' AND indexname = 'idx_ohlc_recent_7d';

-- Index 2: ML window (medium duration)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_ml_30d
ON ohlc_data(symbol, timestamp DESC)
WHERE timestamp > CURRENT_DATE - INTERVAL '30 days';

-- Verify Index 2
SELECT indexname, pg_size_pretty(pg_relation_size(indexname::regclass)) as size
FROM pg_indexes
WHERE tablename = 'ohlc_data' AND indexname = 'idx_ohlc_ml_30d';

-- Index 3: BRIN for time-series (very fast to create, extremely efficient)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_timestamp_brin
ON ohlc_data USING BRIN(timestamp);

-- Verify Index 3
SELECT indexname, pg_size_pretty(pg_relation_size(indexname::regclass)) as size
FROM pg_indexes
WHERE tablename = 'ohlc_data' AND indexname = 'idx_ohlc_timestamp_brin';

-- ============================================================
-- STEP 3: CREATE FULL INDEX (Run on Weekend)
-- ============================================================
-- This will take hours - run Friday night or Saturday morning
SET statement_timeout = '7200000';  -- 2 hours

-- The main comprehensive index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_full
ON ohlc_data(symbol, timeframe, timestamp DESC);

-- Verify full index
SELECT indexname, pg_size_pretty(pg_relation_size(indexname::regclass)) as size
FROM pg_indexes
WHERE tablename = 'ohlc_data' AND indexname = 'idx_ohlc_full';

-- Optional: Additional optimization indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_symbol_only
ON ohlc_data(symbol, timestamp DESC);

-- ============================================================
-- FINAL: Analyze table to update statistics
-- ============================================================
ANALYZE ohlc_data;
