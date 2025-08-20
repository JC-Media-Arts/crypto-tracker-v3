-- Production-Safe Index Creation for Supabase SQL Editor
-- IMPORTANT: Run each CREATE INDEX command SEPARATELY (one at a time)
-- The SQL Editor wraps commands in transactions, so CONCURRENTLY won't work in a batch

-- ============================================================
-- STEP 1: TEST WITHOUT CONCURRENTLY (Run First)
-- ============================================================
-- Since CONCURRENTLY doesn't work in SQL Editor, create a small partial index
-- This will lock the table briefly but only for recent data

-- Set timeout first (run this alone)
SET statement_timeout = '300000';  -- 5 minutes

-- Then run this separately:
CREATE INDEX IF NOT EXISTS idx_ohlc_test_recent
ON ohlc_data(timestamp DESC)
WHERE timestamp > '2025-01-19'::timestamptz;

-- ============================================================
-- STEP 2: CREATE PARTIAL INDEXES (Run Each Separately)
-- ============================================================

-- First, set a longer timeout (run alone):
SET statement_timeout = '600000';  -- 10 minutes

-- Index 1: Last 7 days (run alone)
CREATE INDEX IF NOT EXISTS idx_ohlc_recent_7d
ON ohlc_data(symbol, timeframe, timestamp DESC)
WHERE timestamp > '2025-01-13'::timestamptz;

-- Index 2: Last 30 days for ML (run alone)
CREATE INDEX IF NOT EXISTS idx_ohlc_ml_30d
ON ohlc_data(symbol, timestamp DESC)
WHERE timestamp > '2024-12-20'::timestamptz;

-- Index 3: BRIN index - very efficient (run alone)
CREATE INDEX IF NOT EXISTS idx_ohlc_timestamp_brin
ON ohlc_data USING BRIN(timestamp);

-- ============================================================
-- ALTERNATIVE: Use Supabase CLI for CONCURRENTLY
-- ============================================================
-- If you have Supabase CLI installed, you can run CONCURRENTLY:
--
-- supabase db execute --sql "CREATE INDEX CONCURRENTLY idx_ohlc_recent_7d ON ohlc_data(symbol, timeframe, timestamp DESC) WHERE timestamp > CURRENT_DATE - INTERVAL '7 days'"
--
-- Or connect directly with psql:
-- psql "postgresql://postgres:[password]@[host]:[port]/postgres" -c "CREATE INDEX CONCURRENTLY ..."

-- ============================================================
-- OPTION B: Create Materialized View (Workaround)
-- ============================================================
-- If indexes still timeout, create a materialized view instead

-- Create view with recent data only
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlc_recent AS
SELECT * FROM ohlc_data
WHERE timestamp > '2025-01-01'::timestamptz;

-- Create indexes on the view (much smaller, will succeed)
CREATE INDEX idx_mv_symbol_time ON ohlc_recent(symbol, timeframe, timestamp DESC);
CREATE INDEX idx_mv_timestamp ON ohlc_recent(timestamp DESC);

-- Refresh the view periodically (run daily)
REFRESH MATERIALIZED VIEW ohlc_recent;
