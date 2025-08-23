-- Migration: Add trading_engine column to paper_trades and paper_performance tables
-- Purpose: Track which trading engine generated each trade for future compatibility
-- Date: 2025-08-21

-- Add trading_engine column to paper_trades table
ALTER TABLE paper_trades
ADD COLUMN IF NOT EXISTS trading_engine VARCHAR(50) DEFAULT 'simple_paper_trader';

-- Add index for querying by trading engine
CREATE INDEX IF NOT EXISTS idx_paper_trades_engine
ON paper_trades(trading_engine);

-- Add trading_engine column to paper_performance table
ALTER TABLE paper_performance
ADD COLUMN IF NOT EXISTS trading_engine VARCHAR(50) DEFAULT 'simple_paper_trader';

-- Add index for performance queries by engine
CREATE INDEX IF NOT EXISTS idx_paper_performance_engine
ON paper_performance(trading_engine);

-- Update any existing records (if needed)
UPDATE paper_trades
SET trading_engine = 'simple_paper_trader'
WHERE trading_engine IS NULL;

UPDATE paper_performance
SET trading_engine = 'simple_paper_trader'
WHERE trading_engine IS NULL;

-- Add comment for documentation
COMMENT ON COLUMN paper_trades.trading_engine IS 'Trading engine that generated this trade: simple_paper_trader, hummingbot, or other future services';
COMMENT ON COLUMN paper_performance.trading_engine IS 'Trading engine for this performance record: simple_paper_trader, hummingbot, or other future services';
