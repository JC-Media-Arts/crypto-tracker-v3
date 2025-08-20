-- Monitoring Queries for Index Creation
-- Run these in a SEPARATE SQL session while indexes are being created

-- ============================================================
-- 1. CHECK INDEX CREATION PROGRESS
-- ============================================================
-- See if index creation is still running
SELECT
    pid,
    state,
    wait_event_type,
    wait_event,
    query,
    now() - query_start AS duration,
    pg_size_pretty(pg_database_size(datname)) as database_size
FROM pg_stat_activity
WHERE query LIKE '%CREATE INDEX CONCURRENTLY%'
   OR query LIKE '%CREATE INDEX%'
ORDER BY query_start;

-- ============================================================
-- 2. VIEW ALL INDEXES ON OHLC TABLE
-- ============================================================
-- See all indexes and their sizes
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size,
    idx_scan as times_used,
    idx_tup_read as tuples_read
FROM pg_stat_user_indexes
WHERE tablename = 'ohlc_data'
ORDER BY pg_relation_size(indexname::regclass) DESC;

-- ============================================================
-- 3. CHECK FOR INVALID INDEXES
-- ============================================================
-- CONCURRENTLY can leave invalid indexes if interrupted
SELECT
    n.nspname as schema,
    c.relname as index_name,
    i.indisvalid as is_valid,
    pg_get_indexdef(i.indexrelid) as index_definition
FROM pg_index i
JOIN pg_class c ON c.oid = i.indexrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE i.indisvalid = false
  AND c.relname LIKE '%ohlc%';

-- ============================================================
-- 4. CHECK TABLE AND INDEX STATISTICS
-- ============================================================
SELECT
    relname,
    n_live_tup as live_rows,
    n_dead_tup as dead_rows,
    last_vacuum,
    last_autovacuum,
    last_analyze,
    last_autoanalyze
FROM pg_stat_user_tables
WHERE relname = 'ohlc_data';

-- ============================================================
-- 5. ESTIMATE COMPLETION TIME
-- ============================================================
-- Check blocks processed (rough estimate of progress)
SELECT
    pid,
    query,
    now() - query_start as elapsed,
    CASE
        WHEN query LIKE '%CONCURRENTLY%' THEN 'Creating index without locking'
        ELSE 'Creating index with lock'
    END as index_type
FROM pg_stat_activity
WHERE query LIKE '%CREATE INDEX%'
  AND state = 'active';

-- ============================================================
-- 6. CHECK DATABASE LOCKS
-- ============================================================
-- Ensure CONCURRENTLY isn't causing lock issues
SELECT
    locktype,
    relation::regclass as table_name,
    mode,
    granted,
    pid,
    query
FROM pg_locks l
JOIN pg_stat_activity a ON l.pid = a.pid
WHERE relation::regclass::text LIKE '%ohlc%'
ORDER BY granted DESC, pid;

-- ============================================================
-- 7. CLEANUP INVALID INDEXES (If Needed)
-- ============================================================
-- List commands to drop invalid indexes
SELECT
    'DROP INDEX CONCURRENTLY IF EXISTS ' || c.relname || ';' as drop_command
FROM pg_index i
JOIN pg_class c ON c.oid = i.indexrelid
WHERE i.indisvalid = false
  AND c.relname LIKE '%ohlc%';
