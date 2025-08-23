-- Add trailing stop column to paper_trades table
ALTER TABLE paper_trades
ADD COLUMN IF NOT EXISTS trailing_stop_pct DECIMAL(10,4);

-- Add comment for documentation
COMMENT ON COLUMN paper_trades.trailing_stop_pct IS 'Trailing stop percentage for the position (e.g., 0.06 for 6%)';
