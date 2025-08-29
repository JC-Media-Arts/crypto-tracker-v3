-- Archive and Clean Data for Fresh Freqtrade Start
-- Run this in Supabase SQL Editor
-- Date: August 29, 2025

-- Step 1: Create archive tables (backup everything first)
CREATE TABLE IF NOT EXISTS scan_history_archive AS 
SELECT * FROM scan_history;

CREATE TABLE IF NOT EXISTS paper_trades_archive AS 
SELECT * FROM paper_trades;

-- Add timestamp to archives
ALTER TABLE scan_history_archive 
ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP DEFAULT NOW();

ALTER TABLE paper_trades_archive 
ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP DEFAULT NOW();

-- Step 2: Count records before deletion (for verification)
SELECT 
    (SELECT COUNT(*) FROM scan_history) as scan_history_count,
    (SELECT COUNT(*) FROM paper_trades) as paper_trades_count,
    (SELECT COUNT(*) FROM scan_history_archive) as scan_archive_count,
    (SELECT COUNT(*) FROM paper_trades_archive) as trades_archive_count;

-- Step 3: Clear tables in correct order (handle foreign key constraints)
-- Must delete paper_trades first due to foreign key reference to scan_history
DELETE FROM paper_trades;
DELETE FROM scan_history;

-- Alternative: If DELETE is too slow, use TRUNCATE with CASCADE
-- TRUNCATE TABLE paper_trades CASCADE;
-- TRUNCATE TABLE scan_history CASCADE;

-- Step 4: Reset sequences (auto-increment counters)
ALTER SEQUENCE IF EXISTS scan_history_id_seq RESTART WITH 1;
ALTER SEQUENCE IF EXISTS paper_trades_id_seq RESTART WITH 1;

-- Step 5: Verify clean slate
SELECT 
    (SELECT COUNT(*) FROM scan_history) as scan_history_after,
    (SELECT COUNT(*) FROM paper_trades) as paper_trades_after,
    (SELECT COUNT(*) FROM scan_history_archive) as archived_scans,
    (SELECT COUNT(*) FROM paper_trades_archive) as archived_trades;

-- Step 6: Add a comment to track when we started fresh with Freqtrade
COMMENT ON TABLE scan_history IS 'Fresh start with Freqtrade integration - August 29, 2025. Old data archived in scan_history_archive';
COMMENT ON TABLE paper_trades IS 'Legacy table - Freqtrade uses its own database. Old data archived in paper_trades_archive';
