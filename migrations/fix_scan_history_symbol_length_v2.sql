-- Migration: Fix scan_history symbol field length for longer pairs
-- Date: 2025-09-01
-- Purpose: Increase symbol field from VARCHAR(10) to VARCHAR(20) to support pairs like 'FARTCOIN/USD'

-- Step 1: Drop dependent views
DROP VIEW IF EXISTS scan_history_summary CASCADE;
DROP VIEW IF EXISTS near_miss_analysis CASCADE;

-- Step 2: Alter the symbol column to support longer pairs
ALTER TABLE scan_history 
ALTER COLUMN symbol TYPE VARCHAR(20);

-- Step 3: Recreate the views with the updated column
CREATE OR REPLACE VIEW scan_history_summary AS
SELECT 
    DATE_TRUNC('hour', timestamp) as hour,
    strategy_name,
    decision,
    COUNT(*) as count,
    AVG(ml_confidence) as avg_confidence,
    COUNT(DISTINCT symbol) as unique_symbols
FROM scan_history
GROUP BY DATE_TRUNC('hour', timestamp), strategy_name, decision
ORDER BY hour DESC, strategy_name;

CREATE OR REPLACE VIEW near_miss_analysis AS
SELECT 
    symbol,
    strategy_name,
    COUNT(*) as near_miss_count,
    AVG(ml_confidence) as avg_confidence,
    MAX(ml_confidence) as max_confidence,
    MIN(ml_confidence) as min_confidence,
    JSONB_AGG(DISTINCT reason) as rejection_reasons
FROM scan_history
WHERE decision = 'NEAR_MISS' 
   OR (decision = 'SKIP' AND ml_confidence > 0.50)
GROUP BY symbol, strategy_name
ORDER BY near_miss_count DESC;

-- Update comment
COMMENT ON COLUMN scan_history.symbol IS 'Trading pair symbol (e.g., BTC/USD, FARTCOIN/USD)';

-- Log the migration
DO $$
BEGIN
    RAISE NOTICE 'scan_history.symbol column expanded from VARCHAR(10) to VARCHAR(20) to support longer pair names';
END $$;
