-- Migration 027: Fix ML view to include outcome_label column
-- Date: 2025-01-24
-- Purpose: Add outcome_label column that ML Retrainer expects

-- Drop and recreate the view with outcome_label
DROP VIEW IF EXISTS completed_trades_for_ml CASCADE;

CREATE VIEW completed_trades_for_ml AS
SELECT
    trade_id,
    symbol,
    strategy_name,
    created_at as opened_at,
    filled_at as closed_at,
    side,
    price as entry_price,
    amount,
    pnl,
    CASE
        WHEN pnl > 0 THEN 'WIN'
        ELSE 'LOSS'
    END as outcome_label,  -- Add this column for ML training
    CASE
        WHEN pnl > 0 THEN 'CLOSED_WIN'
        ELSE 'CLOSED_LOSS'
    END as status,
    exit_reason,
    ml_confidence,
    predicted_take_profit,
    predicted_stop_loss,
    hold_time_hours,
    scan_id  -- Add scan_id for feature retrieval
FROM paper_trades
WHERE side = 'SELL'  -- Completed trades only
  AND exit_reason IS NOT NULL
  AND exit_reason NOT IN ('POSITION_LIMIT_CLEANUP', 'manual', 'MANUAL')
ORDER BY filled_at DESC;

-- Also add scan_features column to ml_training_feedback view
DROP VIEW IF EXISTS ml_training_feedback CASCADE;

CREATE VIEW ml_training_feedback AS
SELECT
    p.trade_id,
    p.symbol,
    p.strategy_name,
    p.scan_id,
    s.features as scan_features,  -- JSON features from scan_history
    p.created_at as opened_at,
    p.filled_at as closed_at,
    p.price as entry_price,
    p.amount,
    p.pnl,
    p.hold_time_hours,
    CAST(
        CASE
            WHEN p.price > 0 AND p.amount > 0 THEN ((p.pnl / (p.price * p.amount)) * 100)
            ELSE 0
        END AS DECIMAL(10,4)
    ) as pnl_percentage,
    CASE
        WHEN p.pnl > 0 THEN 'WIN'
        ELSE 'LOSS'
    END as outcome_label,
    p.exit_reason,
    p.ml_confidence,
    p.predicted_take_profit,
    p.predicted_stop_loss,
    p.predicted_win_probability,
    p.predicted_hold_hours,
    -- Calculate prediction accuracy
    CASE
        WHEN p.predicted_win_probability > 0.5 AND p.pnl > 0 THEN true
        WHEN p.predicted_win_probability <= 0.5 AND p.pnl <= 0 THEN true
        ELSE false
    END as prediction_correct
FROM paper_trades p
LEFT JOIN scan_history s ON p.scan_id = s.scan_id
WHERE p.side = 'SELL'  -- Completed trades only
  AND p.exit_reason IS NOT NULL
  AND p.exit_reason NOT IN ('POSITION_LIMIT_CLEANUP', 'manual', 'MANUAL')
ORDER BY p.filled_at DESC;
