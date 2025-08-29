-- Archive and Clean Data for Fresh Freqtrade Start (CHUNKED VERSION)
-- Run each section separately in Supabase SQL Editor
-- Date: August 29, 2025

-- ============================================================
-- SECTION 1: Create Archive Tables (Run First)
-- ============================================================
CREATE TABLE IF NOT EXISTS scan_history_archive AS 
SELECT * FROM scan_history
LIMIT 0; -- Create empty table with same structure

CREATE TABLE IF NOT EXISTS paper_trades_archive AS 
SELECT * FROM paper_trades
LIMIT 0; -- Create empty table with same structure

-- Add archive timestamp columns
ALTER TABLE scan_history_archive 
ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP DEFAULT NOW();

ALTER TABLE paper_trades_archive 
ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP DEFAULT NOW();

-- ============================================================
-- SECTION 2: Archive paper_trades (Run Second)
-- This is smaller table (5,176 records) so should work
-- ============================================================
INSERT INTO paper_trades_archive 
SELECT *, NOW() as archived_at FROM paper_trades;

-- Verify archive
SELECT COUNT(*) as archived_trades FROM paper_trades_archive;

-- ============================================================
-- SECTION 3: Archive scan_history in chunks (Run Third)
-- Break into smaller chunks to avoid timeout
-- ============================================================

-- Chunk 1: Archive first 200k records
INSERT INTO scan_history_archive 
SELECT *, NOW() as archived_at 
FROM scan_history 
ORDER BY id
LIMIT 200000;

-- Wait a moment, then run Chunk 2: Next 200k records
INSERT INTO scan_history_archive 
SELECT *, NOW() as archived_at 
FROM scan_history 
WHERE id > (SELECT MAX(id) FROM scan_history_archive)
ORDER BY id
LIMIT 200000;

-- Repeat for remaining chunks...
-- Continue until all records are archived

-- Check progress
SELECT 
    (SELECT COUNT(*) FROM scan_history) as original_count,
    (SELECT COUNT(*) FROM scan_history_archive) as archived_count;

-- ============================================================
-- SECTION 4: Delete Production Data (Run Fourth)
-- After confirming archives are complete
-- ============================================================

-- Delete paper_trades first (foreign key constraint)
DELETE FROM paper_trades;

-- Delete scan_history in chunks to avoid timeout
DELETE FROM scan_history 
WHERE id IN (
    SELECT id FROM scan_history 
    ORDER BY id 
    LIMIT 100000
);

-- Repeat DELETE until all records are gone
-- Or use TRUNCATE if supported:
-- TRUNCATE TABLE paper_trades CASCADE;
-- TRUNCATE TABLE scan_history CASCADE;

-- ============================================================
-- SECTION 5: Reset Sequences (Run Fifth)
-- ============================================================
ALTER SEQUENCE IF EXISTS scan_history_id_seq RESTART WITH 1;
ALTER SEQUENCE IF EXISTS paper_trades_id_seq RESTART WITH 1;

-- ============================================================
-- SECTION 6: Final Verification (Run Last)
-- ============================================================
SELECT 
    (SELECT COUNT(*) FROM scan_history) as scan_history_after,
    (SELECT COUNT(*) FROM paper_trades) as paper_trades_after,
    (SELECT COUNT(*) FROM scan_history_archive) as archived_scans,
    (SELECT COUNT(*) FROM paper_trades_archive) as archived_trades;

-- Add documentation
COMMENT ON TABLE scan_history IS 'Fresh start with Freqtrade integration - August 29, 2025. Old data archived in scan_history_archive';
COMMENT ON TABLE paper_trades IS 'Legacy table - Freqtrade uses its own database. Old data archived in paper_trades_archive';
