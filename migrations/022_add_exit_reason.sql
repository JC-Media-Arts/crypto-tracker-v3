-- Add exit_reason column to paper_trades table
ALTER TABLE paper_trades
ADD COLUMN IF NOT EXISTS exit_reason VARCHAR(50);

-- Add comment for documentation
COMMENT ON COLUMN paper_trades.exit_reason IS 'Reason for closing position: stop_loss, take_profit, trailing_stop, time_exit, manual';
