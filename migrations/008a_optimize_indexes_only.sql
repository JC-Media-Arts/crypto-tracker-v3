-- Optimized indexes for OHLC table - Run these one at a time if needed
-- Each CREATE INDEX can be run separately to avoid timeouts

-- 1. BRIN index for timestamp - VERY efficient for time-series data
-- This should be created FIRST as it's the most important
CREATE INDEX IF NOT EXISTS idx_ohlc_timestamp_brin
    ON ohlc_data USING BRIN(timestamp);

-- 2. Composite index for most common query pattern
-- Run this AFTER the BRIN index
CREATE INDEX IF NOT EXISTS idx_ohlc_composite
    ON ohlc_data(symbol, timeframe, timestamp DESC);

-- 3. Index for symbol-based queries
CREATE INDEX IF NOT EXISTS idx_ohlc_symbol_timestamp
    ON ohlc_data(symbol, timestamp DESC);

-- 4. Index for timeframe-based analysis
CREATE INDEX IF NOT EXISTS idx_ohlc_timeframe_timestamp
    ON ohlc_data(timeframe, timestamp DESC);

-- 5. Partial index for recent data (last 30 days) - most queries are for recent data
-- This one might take longer, run it last
CREATE INDEX IF NOT EXISTS idx_ohlc_recent
    ON ohlc_data(symbol, timeframe, timestamp DESC)
    WHERE timestamp > NOW() - INTERVAL '30 days';

-- Optional: Update table statistics for better query planning
-- Run these after indexes are created
ANALYZE ohlc_data;
