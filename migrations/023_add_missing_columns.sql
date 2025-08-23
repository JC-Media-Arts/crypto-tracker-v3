-- Add missing columns to paper_trades and paper_performance tables

-- Add stop_loss and take_profit columns to paper_trades
ALTER TABLE paper_trades
ADD COLUMN IF NOT EXISTS stop_loss DECIMAL(20,8),
ADD COLUMN IF NOT EXISTS take_profit DECIMAL(20,8);

-- Fix paper_performance table (it seems to be missing date column or has wrong structure)
-- First check if we need to rename a column or add it
ALTER TABLE paper_performance
ADD COLUMN IF NOT EXISTS date DATE;

-- Add comments for documentation
COMMENT ON COLUMN paper_trades.stop_loss IS 'Stop loss price for the position';
COMMENT ON COLUMN paper_trades.take_profit IS 'Take profit price for the position';
COMMENT ON COLUMN paper_performance.date IS 'Date of the performance record';
