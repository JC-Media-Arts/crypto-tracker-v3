-- Ultra-minimal indexes - try these one at a time
-- These are so small they should complete in seconds

-- Option 1: Index ONLY Bitcoin recent data (single symbol)
CREATE INDEX IF NOT EXISTS idx_btc_only
ON ohlc_data(timestamp DESC)
WHERE symbol = 'BTC' AND timestamp > '2025-01-15'::timestamptz;

-- Option 2: Index only today's data
CREATE INDEX IF NOT EXISTS idx_today_only
ON ohlc_data(symbol, timestamp DESC)
WHERE timestamp > '2025-01-20'::timestamptz;

-- Option 3: Create a materialized view instead (alternative approach)
-- This creates a separate small table with just recent data
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlc_recent AS
SELECT * FROM ohlc_data
WHERE timestamp > '2025-01-15'::timestamptz;

-- Then create index on the materialized view (much smaller, will succeed)
CREATE INDEX idx_mv_recent ON ohlc_recent(symbol, timestamp DESC);

-- Option 4: Create covering index on just the primary key subset
CREATE INDEX IF NOT EXISTS idx_minimal_coverage
ON ohlc_data(timestamp)
WHERE timestamp > '2025-01-19'::timestamptz;
