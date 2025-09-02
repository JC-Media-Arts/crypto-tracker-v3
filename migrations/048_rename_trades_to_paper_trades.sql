-- Migration: Rename Freqtrade's trades table to paper_trades
-- Date: 2025-09-01
-- Purpose: Consolidate Freqtrade trades into paper_trades table for dashboard compatibility

-- First, drop the old paper_trades table if it exists
-- This table was used by SimplePaperTraderV2 which is now deprecated
DROP TABLE IF EXISTS paper_trades CASCADE;

-- Now rename Freqtrade's trades table to paper_trades
ALTER TABLE IF EXISTS trades RENAME TO paper_trades;

-- Add columns to match what the dashboard expects
-- Map Freqtrade columns to dashboard expectations
ALTER TABLE paper_trades
ADD COLUMN IF NOT EXISTS symbol VARCHAR(20),
ADD COLUMN IF NOT EXISTS side VARCHAR(10),
ADD COLUMN IF NOT EXISTS price DECIMAL(20,8),
ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS trade_group_id VARCHAR(50),
ADD COLUMN IF NOT EXISTS strategy_name VARCHAR(50),
ADD COLUMN IF NOT EXISTS trading_engine VARCHAR(50) DEFAULT 'freqtrade',
ADD COLUMN IF NOT EXISTS exit_reason VARCHAR(100),
ADD COLUMN IF NOT EXISTS pnl DECIMAL(20,8),
ADD COLUMN IF NOT EXISTS scan_id INTEGER,
ADD COLUMN IF NOT EXISTS predicted_take_profit DECIMAL(10,4),
ADD COLUMN IF NOT EXISTS predicted_stop_loss DECIMAL(10,4),
ADD COLUMN IF NOT EXISTS predicted_hold_hours DECIMAL(10,2),
ADD COLUMN IF NOT EXISTS predicted_win_probability DECIMAL(5,4),
ADD COLUMN IF NOT EXISTS hold_time_hours DECIMAL(10,2),
ADD COLUMN IF NOT EXISTS prediction_accuracy JSONB,
ADD COLUMN IF NOT EXISTS market_regime_at_close VARCHAR(20),
ADD COLUMN IF NOT EXISTS btc_price_at_close DECIMAL(20,8);

-- Update the mapped columns from Freqtrade's column names
UPDATE paper_trades SET 
    symbol = SPLIT_PART(pair, '/', 1),  -- Extract symbol from pair (e.g., BTC from BTC/USD)
    side = CASE WHEN is_open = true THEN 'BUY' ELSE 'SELL' END,
    price = CASE WHEN is_open = true THEN open_rate ELSE close_rate END,
    created_at = CASE WHEN is_open = true THEN open_date ELSE close_date END,
    trade_group_id = CAST(id AS VARCHAR),  -- Use id as trade_group_id for Freqtrade
    strategy_name = strategy,
    pnl = close_profit_abs
WHERE true;

-- Handle exit_reason - check if column exists (newer Freqtrade versions)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'paper_trades' 
               AND column_name = 'exit_reason' 
               AND table_schema = 'public') THEN
        -- exit_reason already exists, no need to update
        NULL;
    ELSIF EXISTS (SELECT 1 FROM information_schema.columns 
                  WHERE table_name = 'paper_trades' 
                  AND column_name = 'sell_reason' 
                  AND table_schema = 'public') THEN
        -- Old version with sell_reason, copy to exit_reason
        UPDATE paper_trades SET exit_reason = sell_reason WHERE sell_reason IS NOT NULL;
    END IF;
END $$;

-- Ensure we have the necessary indexes
CREATE INDEX IF NOT EXISTS idx_paper_trades_is_open ON paper_trades(is_open);
CREATE INDEX IF NOT EXISTS idx_paper_trades_pair ON paper_trades(pair);
CREATE INDEX IF NOT EXISTS idx_paper_trades_symbol ON paper_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_paper_trades_open_date ON paper_trades(open_date);
CREATE INDEX IF NOT EXISTS idx_paper_trades_close_date ON paper_trades(close_date);
CREATE INDEX IF NOT EXISTS idx_paper_trades_created_at ON paper_trades(created_at);
CREATE INDEX IF NOT EXISTS idx_paper_trades_trade_group_id ON paper_trades(trade_group_id);

-- Add a comment to track the migration
COMMENT ON TABLE paper_trades IS 'Unified paper trading table - migrated from Freqtrade trades table on 2025-09-01';

-- Grant permissions
GRANT ALL ON paper_trades TO authenticated;
GRANT ALL ON paper_trades TO service_role;

-- Log the migration
DO $$
DECLARE
    row_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO row_count FROM paper_trades;
    RAISE NOTICE 'Successfully renamed trades to paper_trades with % existing trades', row_count;
END $$;
