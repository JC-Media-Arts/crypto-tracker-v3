-- Migration: Add Trade Logs Table for Outcome Tracking
-- Date: 2025-01-19
-- Purpose: Track actual trade outcomes and link them back to scan predictions

-- Trade Logs Table - Records all executed trades and their outcomes
CREATE TABLE IF NOT EXISTS trade_logs (
    trade_id SERIAL PRIMARY KEY,
    scan_id INTEGER REFERENCES scan_history(scan_id),  -- Links back to original scan
    
    -- Trade Identity
    symbol VARCHAR(10) NOT NULL,
    strategy_name VARCHAR(50) NOT NULL,
    
    -- Trade Timing
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    hold_time_hours DECIMAL(10,2),
    
    -- Trade Details
    entry_price DECIMAL(20,8) NOT NULL,
    exit_price DECIMAL(20,8),
    position_size DECIMAL(20,8) NOT NULL,
    capital_used DECIMAL(20,8) NOT NULL,
    
    -- Trade Targets (from ML predictions)
    predicted_take_profit DECIMAL(10,4),
    predicted_stop_loss DECIMAL(10,4),
    predicted_hold_hours DECIMAL(10,2),
    predicted_win_probability DECIMAL(5,4),
    ml_confidence DECIMAL(5,4),
    
    -- Trade Outcome
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN',  -- 'OPEN', 'CLOSED_WIN', 'CLOSED_LOSS', 'CLOSED_TIMEOUT'
    exit_reason VARCHAR(50),  -- 'take_profit', 'stop_loss', 'timeout', 'manual', 'regime_change'
    pnl_amount DECIMAL(20,8),
    pnl_percentage DECIMAL(10,4),
    
    -- Performance vs Prediction
    prediction_accuracy JSONB,  -- Stores how accurate the ML predictions were
    
    -- Market Context at Close
    market_regime_at_close VARCHAR(20),
    btc_price_at_close DECIMAL(20,8),
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_trade_logs_symbol ON trade_logs(symbol);
CREATE INDEX IF NOT EXISTS idx_trade_logs_strategy ON trade_logs(strategy_name);
CREATE INDEX IF NOT EXISTS idx_trade_logs_status ON trade_logs(status);
CREATE INDEX IF NOT EXISTS idx_trade_logs_opened_at ON trade_logs(opened_at);
CREATE INDEX IF NOT EXISTS idx_trade_logs_scan_id ON trade_logs(scan_id);

-- View to analyze prediction accuracy
CREATE OR REPLACE VIEW prediction_accuracy_analysis AS
SELECT 
    strategy_name,
    COUNT(*) as total_trades,
    AVG(ml_confidence) as avg_confidence,
    AVG(predicted_win_probability) as avg_predicted_win_prob,
    SUM(CASE WHEN status = 'CLOSED_WIN' THEN 1 ELSE 0 END)::FLOAT / 
        NULLIF(COUNT(CASE WHEN status LIKE 'CLOSED_%' THEN 1 END), 0) as actual_win_rate,
    AVG(CASE WHEN status LIKE 'CLOSED_%' THEN pnl_percentage END) as avg_pnl_pct,
    AVG(CASE WHEN status LIKE 'CLOSED_%' THEN hold_time_hours END) as avg_hold_hours,
    AVG(predicted_hold_hours) as avg_predicted_hold_hours
FROM trade_logs
GROUP BY strategy_name;

-- View to link trades back to their original scans for ML training
CREATE OR REPLACE VIEW ml_training_feedback AS
SELECT 
    s.scan_id,
    s.timestamp as scan_time,
    s.symbol,
    s.strategy_name,
    s.features as scan_features,
    s.ml_predictions as original_predictions,
    s.ml_confidence,
    t.trade_id,
    t.opened_at,
    t.closed_at,
    t.hold_time_hours,
    t.pnl_percentage,
    t.status,
    t.exit_reason,
    CASE 
        WHEN t.status = 'CLOSED_WIN' THEN 1
        WHEN t.status = 'CLOSED_LOSS' THEN 0
        ELSE NULL
    END as outcome_label
FROM scan_history s
INNER JOIN trade_logs t ON s.scan_id = t.scan_id
WHERE t.status LIKE 'CLOSED_%';
