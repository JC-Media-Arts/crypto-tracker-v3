-- Migration 026: Unify Trading Tables - Add ML tracking to paper_trades
-- Date: 2025-01-24
-- Purpose: Consolidate to single paper_trades table with ML tracking capabilities

-- ============================================
-- PART 1: Add ML tracking columns to paper_trades
-- ============================================

-- Add scan_id to link back to scan_history (for ML feedback loop)
ALTER TABLE paper_trades
ADD COLUMN IF NOT EXISTS scan_id INTEGER REFERENCES scan_history(scan_id);

-- Add ML prediction tracking fields
ALTER TABLE paper_trades
ADD COLUMN IF NOT EXISTS predicted_take_profit DECIMAL(10,4),
ADD COLUMN IF NOT EXISTS predicted_stop_loss DECIMAL(10,4),
ADD COLUMN IF NOT EXISTS predicted_hold_hours DECIMAL(10,2),
ADD COLUMN IF NOT EXISTS predicted_win_probability DECIMAL(5,4);

-- Add outcome tracking for completed trades
ALTER TABLE paper_trades
ADD COLUMN IF NOT EXISTS hold_time_hours DECIMAL(10,2),
ADD COLUMN IF NOT EXISTS prediction_accuracy JSONB;

-- Add market context at close
ALTER TABLE paper_trades
ADD COLUMN IF NOT EXISTS market_regime_at_close VARCHAR(20),
ADD COLUMN IF NOT EXISTS btc_price_at_close DECIMAL(20,8);

-- Create index for ML training queries
CREATE INDEX IF NOT EXISTS idx_paper_trades_scan_id ON paper_trades(scan_id);
CREATE INDEX IF NOT EXISTS idx_paper_trades_exit_reason ON paper_trades(exit_reason);
CREATE INDEX IF NOT EXISTS idx_paper_trades_strategy ON paper_trades(strategy_name);

-- ============================================
-- PART 2: Create view for ML training (similar to ml_training_feedback)
-- ============================================

-- Drop existing view first to avoid data type conflicts
DROP VIEW IF EXISTS ml_training_feedback CASCADE;

-- Create fresh view with correct data types
CREATE VIEW ml_training_feedback AS
SELECT
    s.scan_id,
    s.timestamp as scan_time,
    s.symbol,
    s.strategy_name,
    s.features as scan_features,
    s.ml_predictions as original_predictions,
    s.ml_confidence,
    p.trade_id,
    p.created_at as opened_at,
    p.filled_at as closed_at,
    p.hold_time_hours,
    CAST(
        CASE
            WHEN p.price > 0 AND p.amount > 0 THEN ((p.pnl / (p.price * p.amount)) * 100)
            ELSE 0
        END AS DECIMAL(10,4)
    ) as pnl_percentage,
    CASE
        WHEN p.exit_reason IN ('take_profit', 'trailing_stop') AND p.pnl > 0 THEN 'CLOSED_WIN'
        WHEN p.exit_reason IN ('stop_loss', 'timeout') OR p.pnl < 0 THEN 'CLOSED_LOSS'
        ELSE 'OPEN'
    END as status,
    p.exit_reason,
    CASE
        WHEN p.exit_reason IN ('take_profit', 'trailing_stop') AND p.pnl > 0 THEN 1
        WHEN p.exit_reason IN ('stop_loss', 'timeout') OR p.pnl < 0 THEN 0
        ELSE NULL
    END as outcome_label
FROM scan_history s
LEFT JOIN paper_trades p ON s.scan_id = p.scan_id
WHERE p.side = 'SELL'  -- Only completed trades
  AND p.exit_reason NOT IN ('POSITION_LIMIT_CLEANUP', 'manual', 'MANUAL')  -- Exclude manual closes
  AND p.exit_reason IS NOT NULL;

-- ============================================
-- PART 3: Clean up manually closed trades
-- ============================================

-- Delete trades that were manually closed during position cleanup
-- These would confuse ML training
DELETE FROM paper_trades
WHERE exit_reason = 'POSITION_LIMIT_CLEANUP';

-- Log the cleanup
DO $$
DECLARE
    deleted_count INTEGER;
BEGIN
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE 'Deleted % manually closed trades (POSITION_LIMIT_CLEANUP)', deleted_count;
END $$;

-- ============================================
-- PART 4: Drop the redundant trade_logs table
-- ============================================

-- Drop dependent views first
DROP VIEW IF EXISTS prediction_accuracy_analysis CASCADE;

-- Drop the trade_logs table
DROP TABLE IF EXISTS trade_logs CASCADE;

-- Log the table removal
DO $$
BEGIN
    RAISE NOTICE 'Dropped redundant trade_logs table - all ML tracking now in paper_trades';
END $$;

-- ============================================
-- PART 5: Create helper view for ML retrainer
-- ============================================

-- Drop existing view first if it exists
DROP VIEW IF EXISTS completed_trades_for_ml CASCADE;

-- Create fresh view
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
        WHEN pnl > 0 THEN 'CLOSED_WIN'
        ELSE 'CLOSED_LOSS'
    END as status,
    exit_reason,
    ml_confidence,
    predicted_take_profit,
    predicted_stop_loss
FROM paper_trades
WHERE side = 'SELL'  -- Completed trades only
  AND exit_reason IS NOT NULL
  AND exit_reason NOT IN ('POSITION_LIMIT_CLEANUP', 'manual', 'MANUAL')
ORDER BY filled_at DESC;

-- ============================================
-- Summary
-- ============================================
-- 1. Added ML tracking columns to paper_trades
-- 2. Created views for ML training
-- 3. Deleted manually closed trades that would confuse ML
-- 4. Dropped redundant trade_logs table
-- 5. System now uses single unified paper_trades table
