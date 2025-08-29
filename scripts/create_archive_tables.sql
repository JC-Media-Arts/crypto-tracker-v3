-- Step 1: Create Archive Tables ONLY
-- Run this first in Supabase SQL Editor

-- Create scan_history_archive with same structure
CREATE TABLE IF NOT EXISTS scan_history_archive (
    LIKE scan_history INCLUDING ALL
);

-- Create paper_trades_archive with same structure  
CREATE TABLE IF NOT EXISTS paper_trades_archive (
    LIKE paper_trades INCLUDING ALL
);

-- Add archived_at timestamp columns
ALTER TABLE scan_history_archive 
ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP DEFAULT NOW();

ALTER TABLE paper_trades_archive 
ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP DEFAULT NOW();

-- Verify tables were created
SELECT 
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_name IN ('scan_history_archive', 'paper_trades_archive')
AND table_schema = 'public';
