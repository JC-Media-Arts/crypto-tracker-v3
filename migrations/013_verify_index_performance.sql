-- Verify Index Performance After Creation
-- Run these queries to confirm indexes are working

-- ============================================================
-- 1. TEST QUERY PERFORMANCE WITH EXPLAIN
-- ============================================================

-- Test 1: Recent data query (should use idx_ohlc_recent_7d)
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM ohlc_data
WHERE symbol = 'BTC'
  AND timeframe = '1h'
  AND timestamp > CURRENT_DATE - INTERVAL '3 days'
ORDER BY timestamp DESC
LIMIT 100;

-- Test 2: ML feature query (should use idx_ohlc_ml_30d)
EXPLAIN (ANALYZE, BUFFERS)
SELECT symbol, timestamp, close, volume
FROM ohlc_data
WHERE symbol IN ('BTC', 'ETH', 'SOL')
  AND timestamp > CURRENT_DATE - INTERVAL '14 days'
ORDER BY symbol, timestamp DESC;

-- Test 3: Time range query (should use BRIN index)
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*), MIN(timestamp), MAX(timestamp)
FROM ohlc_data
WHERE timestamp BETWEEN '2024-12-01' AND '2024-12-31';

-- ============================================================
-- 2. COMPARE QUERY TIMES (Before vs After Indexes)
-- ============================================================

-- Quick performance test
DO $$
DECLARE
    start_time timestamp;
    end_time timestamp;
    query_time interval;
BEGIN
    -- Test 1: Point lookup
    start_time := clock_timestamp();
    PERFORM * FROM ohlc_data
    WHERE symbol = 'BTC' AND timeframe = '1m'
    ORDER BY timestamp DESC LIMIT 1;
    end_time := clock_timestamp();
    query_time := end_time - start_time;
    RAISE NOTICE 'Latest price query: %', query_time;

    -- Test 2: Range scan
    start_time := clock_timestamp();
    PERFORM COUNT(*) FROM ohlc_data
    WHERE symbol = 'ETH'
      AND timestamp > CURRENT_DATE - INTERVAL '7 days';
    end_time := clock_timestamp();
    query_time := end_time - start_time;
    RAISE NOTICE '7-day range query: %', query_time;

    -- Test 3: Multi-symbol aggregation
    start_time := clock_timestamp();
    PERFORM symbol, MAX(close) FROM ohlc_data
    WHERE timestamp > CURRENT_DATE - INTERVAL '1 day'
    GROUP BY symbol;
    end_time := clock_timestamp();
    query_time := end_time - start_time;
    RAISE NOTICE 'Multi-symbol aggregation: %', query_time;
END $$;

-- ============================================================
-- 3. INDEX USAGE STATISTICS
-- ============================================================

-- Which indexes are being used?
SELECT
    indexname,
    idx_scan as times_used,
    idx_tup_read as rows_read,
    idx_tup_fetch as rows_fetched,
    pg_size_pretty(pg_relation_size(indexname::regclass)) as size,
    CASE
        WHEN idx_scan = 0 THEN 'UNUSED'
        WHEN idx_scan < 100 THEN 'RARELY USED'
        WHEN idx_scan < 1000 THEN 'OCCASIONALLY USED'
        ELSE 'FREQUENTLY USED'
    END as usage_category
FROM pg_stat_user_indexes
WHERE tablename = 'ohlc_data'
ORDER BY idx_scan DESC;

-- ============================================================
-- 4. QUERY PLANNER STATISTICS
-- ============================================================

-- Reset statistics (optional - do this to get fresh stats)
-- SELECT pg_stat_reset();

-- Check cache hit ratio (should be > 90% for good performance)
SELECT
    sum(heap_blks_read) as heap_read,
    sum(heap_blks_hit) as heap_hit,
    CASE
        WHEN sum(heap_blks_hit) + sum(heap_blks_read) = 0 THEN 0
        ELSE round(sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read))::numeric * 100, 2)
    END as cache_hit_ratio
FROM pg_statio_user_tables
WHERE relname = 'ohlc_data';

-- ============================================================
-- 5. RECOMMENDED QUERY PATTERNS
-- ============================================================

-- These queries are optimized for your new indexes:

-- Pattern 1: Get latest prices (uses recent index)
-- Good:
SELECT * FROM ohlc_data
WHERE symbol = 'BTC'
  AND timestamp > CURRENT_DATE - INTERVAL '7 days'
ORDER BY timestamp DESC
LIMIT 1;

-- Pattern 2: Get ML features (uses 30-day index)
-- Good:
SELECT timestamp, close, volume
FROM ohlc_data
WHERE symbol = 'ETH'
  AND timestamp > CURRENT_DATE - INTERVAL '30 days'
  AND timeframe = '1h'
ORDER BY timestamp DESC;

-- Pattern 3: Historical analysis (uses BRIN)
-- Good:
SELECT DATE(timestamp) as day, AVG(close) as avg_price
FROM ohlc_data
WHERE symbol = 'SOL'
  AND timestamp BETWEEN '2024-01-01' AND '2024-12-31'
GROUP BY DATE(timestamp)
ORDER BY day;
