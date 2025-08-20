-- Minimal index creation for very large tables
-- Try these one at a time, starting with the smallest

-- Option 1: Try creating index on just recent data first (smallest index)
-- This should be MUCH faster
CREATE INDEX IF NOT EXISTS idx_ohlc_recent_only
    ON ohlc_data(timestamp DESC)
    WHERE timestamp > '2025-01-01'::timestamptz;

-- Option 2: If above works, try symbol-specific index for recent data
CREATE INDEX IF NOT EXISTS idx_ohlc_symbol_recent
    ON ohlc_data(symbol, timestamp DESC)
    WHERE timestamp > '2024-12-01'::timestamptz;

-- Option 3: For immediate performance improvement without full index
-- Create a materialized view of recent data (last 30 days)
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlc_data_recent AS
SELECT * FROM ohlc_data
WHERE timestamp > NOW() - INTERVAL '30 days';

-- Create index on the materialized view (much smaller, faster)
CREATE INDEX IF NOT EXISTS idx_mv_ohlc_composite
    ON ohlc_data_recent(symbol, timeframe, timestamp DESC);
