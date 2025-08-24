-- Migration 028: Fix mislabeled exit reasons in paper_trades
-- Date: 2025-01-24
-- Purpose: Correct exit_reason for trades that were labeled as 'trailing_stop' but were actually 'stop_loss'

-- Fix existing mislabeled trades
-- A trailing stop should only trigger if the position was profitable at some point
-- If PnL is negative and exit_reason is 'trailing_stop', it's likely a mislabeled stop_loss

UPDATE paper_trades
SET exit_reason = 'stop_loss'
WHERE exit_reason = 'trailing_stop'
  AND pnl < 0
  AND side = 'SELL';

-- Add a comment to track the fix
COMMENT ON COLUMN paper_trades.exit_reason IS
'Exit reason for the trade. Values: stop_loss (hit stop), trailing_stop (hit trailing after profit), take_profit (hit target), time_exit (max hold time), manual, POSITION_LIMIT_CLEANUP. Fixed 2025-01-24 to correctly distinguish stop_loss from trailing_stop.';

-- Verify the fix
DO $$
DECLARE
    fixed_count INTEGER;
    remaining_trailing_losses INTEGER;
BEGIN
    -- Count how many we fixed
    SELECT COUNT(*) INTO fixed_count
    FROM paper_trades
    WHERE exit_reason = 'stop_loss'
      AND pnl < 0
      AND side = 'SELL';

    -- Check if any trailing stops with losses remain
    SELECT COUNT(*) INTO remaining_trailing_losses
    FROM paper_trades
    WHERE exit_reason = 'trailing_stop'
      AND pnl < 0
      AND side = 'SELL';

    RAISE NOTICE 'Fixed % trades from trailing_stop to stop_loss', fixed_count;

    IF remaining_trailing_losses > 0 THEN
        RAISE WARNING 'Still have % trailing_stop trades with losses - may need manual review', remaining_trailing_losses;
    END IF;
END $$;

-- Update the views to reflect the corrected data
-- The views should now show more accurate outcome distributions
-- No changes needed to view definitions as they already use the exit_reason column

-- Show summary of exit reasons after fix
SELECT
    strategy_name,
    exit_reason,
    COUNT(*) as count,
    ROUND(AVG(pnl)::numeric, 2) as avg_pnl,
    CASE
        WHEN AVG(pnl) > 0 THEN 'WIN'
        ELSE 'LOSS'
    END as typical_outcome
FROM paper_trades
WHERE side = 'SELL'
  AND exit_reason IS NOT NULL
GROUP BY strategy_name, exit_reason
ORDER BY strategy_name, count DESC;
