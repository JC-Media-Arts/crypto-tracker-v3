-- Fix Dashboard Performance Issues
-- Run this ENTIRE script in Supabase SQL Editor

-- 1. Create optimal composite index for dashboard queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_dashboard
ON ohlc_data(symbol, timeframe, timestamp DESC);

-- 2. Create partial index for recent data (most queries)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_recent_30d
ON ohlc_data(symbol, timeframe, timestamp DESC)
WHERE timestamp > CURRENT_DATE - INTERVAL '30 days';

-- 3. Create index for the exact query pattern used by dashboard
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_symbol_batch
ON ohlc_data(timeframe, timestamp DESC, symbol)
WHERE timeframe = '15m';

-- 4. Create a strategy status cache table for pre-calculated data
CREATE TABLE IF NOT EXISTS strategy_status_cache (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    strategy_name VARCHAR(50) NOT NULL,
    readiness DECIMAL(5,2),
    current_price DECIMAL(20,8),
    details TEXT,
    status VARCHAR(50),
    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, strategy_name)
);

-- 5. Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_strategy_cache_lookup
ON strategy_status_cache(strategy_name, readiness DESC);

-- 6. Create market summary cache
CREATE TABLE IF NOT EXISTS market_summary_cache (
    id SERIAL PRIMARY KEY,
    condition VARCHAR(50),
    best_strategy VARCHAR(50),
    notes TEXT,
    calculated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Analyze tables to update statistics
ANALYZE ohlc_data;
ANALYZE strategy_status_cache;
ANALYZE market_summary_cache;

-- Done! Your cache tables are ready.
