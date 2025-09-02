-- Migration: Create paper_trades schema for Freqtrade
-- Date: 2025-09-01
-- Purpose: Create a separate schema for Freqtrade to use

-- Create the paper_trades schema
CREATE SCHEMA IF NOT EXISTS paper_trades;

-- Grant permissions on the new schema
GRANT ALL ON SCHEMA paper_trades TO authenticated;
GRANT ALL ON SCHEMA paper_trades TO service_role;
GRANT CREATE ON SCHEMA paper_trades TO authenticated;
GRANT CREATE ON SCHEMA paper_trades TO service_role;

-- Drop the conflicting indexes from public schema
DROP INDEX IF EXISTS ix_trades_pair;
DROP INDEX IF EXISTS ix_trades_open_date;
DROP INDEX IF EXISTS ix_trades_close_date;
DROP INDEX IF EXISTS ix_trades_is_open;
DROP INDEX IF EXISTS ix_trades_id;
DROP INDEX IF EXISTS ix_trades_stoploss_order_id;

-- Log the migration
DO $$
BEGIN
    RAISE NOTICE 'Created paper_trades schema for Freqtrade';
    RAISE NOTICE 'Freqtrade will create its trades table in paper_trades.trades';
    RAISE NOTICE 'Update DATABASE_URL to include: ?options=-csearch_path%%3Dpaper_trades';
END $$;
