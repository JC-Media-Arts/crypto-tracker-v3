-- Run these ONE AT A TIME in Supabase SQL Editor
-- Each should complete quickly since the views are small

-- ============================================================
-- INDEX 1: Already completed ✅
-- ============================================================
-- CREATE INDEX IF NOT EXISTS idx_recent_symbol_time
-- ON ohlc_recent(symbol, timeframe, timestamp DESC);

-- ============================================================
-- INDEX 2: Symbol-only index for ohlc_recent
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_recent_symbol
ON ohlc_recent(symbol, timestamp DESC);

-- ============================================================
-- INDEX 3: Timeframe index for ohlc_recent
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_recent_timeframe
ON ohlc_recent(timeframe, timestamp DESC);

-- ============================================================
-- INDEX 4: BRIN index for ohlc_recent (very small/fast)
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_recent_timestamp_brin
ON ohlc_recent USING BRIN(timestamp);

-- ============================================================
-- INDEX 5: Primary index for ohlc_today
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_today_symbol_time
ON ohlc_today(symbol, timeframe, timestamp DESC);

-- ============================================================
-- INDEX 6: Symbol index for ohlc_today
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_today_symbol
ON ohlc_today(symbol, timestamp DESC);

-- ============================================================
-- AFTER ALL INDEXES: Grant permissions
-- ============================================================
GRANT SELECT ON ohlc_recent TO authenticated;
GRANT SELECT ON ohlc_recent TO anon;
GRANT SELECT ON ohlc_today TO authenticated;
GRANT SELECT ON ohlc_today TO anon;

-- ============================================================
-- VERIFY: Check what indexes exist
-- ============================================================
SELECT
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size
FROM pg_indexes
WHERE tablename IN ('ohlc_recent', 'ohlc_today')
ORDER BY tablename, indexname;
