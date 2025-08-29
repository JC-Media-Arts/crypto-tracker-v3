-- Delete All Data for Fresh Freqtrade Start
-- No backup, just clean slate

-- Step 1: Delete paper_trades first (due to foreign key constraint)
TRUNCATE TABLE paper_trades CASCADE;

-- Step 2: Delete scan_history
TRUNCATE TABLE scan_history CASCADE;

-- Step 3: Reset sequences (auto-increment counters)
ALTER SEQUENCE IF EXISTS scan_history_id_seq RESTART WITH 1;
ALTER SEQUENCE IF EXISTS paper_trades_id_seq RESTART WITH 1;

-- Step 4: Verify clean slate
SELECT 
    'scan_history' as table_name,
    COUNT(*) as record_count
FROM scan_history
UNION ALL
SELECT 
    'paper_trades' as table_name,
    COUNT(*) as record_count
FROM paper_trades;

-- Step 5: Add documentation comments
COMMENT ON TABLE scan_history IS 'Fresh start with Freqtrade integration - August 29, 2025';
COMMENT ON TABLE paper_trades IS 'Legacy table - Freqtrade uses its own database';
