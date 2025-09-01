-- Migration: Fix scan_history symbol field length for longer pairs
-- Date: 2025-09-01
-- Purpose: Increase symbol field from VARCHAR(10) to VARCHAR(20) to support pairs like 'FARTCOIN/USD'

-- Alter the symbol column to support longer pairs
ALTER TABLE scan_history 
ALTER COLUMN symbol TYPE VARCHAR(20);

-- Also update any related views or constraints if needed
COMMENT ON COLUMN scan_history.symbol IS 'Trading pair symbol (e.g., BTC/USD, FARTCOIN/USD)';

-- Log the migration
DO $$
BEGIN
    RAISE NOTICE 'scan_history.symbol column expanded from VARCHAR(10) to VARCHAR(20) to support longer pair names';
END $$;
