-- Migration: Add Scan History Table for ML Learning
-- Date: 2025-01-19
-- Purpose: Capture ALL scan decisions (not just trades) for continuous learning

-- Scan History Table - Logs every decision made during opportunity scanning
CREATE TABLE IF NOT EXISTS scan_history (
    scan_id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol VARCHAR(10) NOT NULL,
    strategy_name VARCHAR(50) NOT NULL,  -- 'DCA', 'SWING', 'CHANNEL'
    
    -- Decision Information
    decision VARCHAR(20) NOT NULL,  -- 'TAKE', 'SKIP', 'NEAR_MISS'
    reason VARCHAR(100),  -- 'confidence_too_low', 'no_setup', 'regime_blocked', etc.
    
    -- Market Conditions
    market_regime VARCHAR(20),  -- 'NORMAL', 'PANIC', 'CAUTION', 'EUPHORIA'
    btc_price DECIMAL(20,8),
    
    -- Features at Decision Time
    features JSONB NOT NULL,  -- All calculated features
    setup_data JSONB,  -- Setup-specific data if detected
    
    -- ML Predictions
    ml_confidence DECIMAL(5,4),  -- 0.0000 to 1.0000
    ml_predictions JSONB,  -- Full ML output (take_profit, stop_loss, etc.)
    
    -- Thresholds Used
    thresholds_used JSONB,  -- What thresholds were active
    
    -- Position Sizing (if calculated)
    proposed_position_size DECIMAL(10,2),
    proposed_capital DECIMAL(10,2),
    
    -- Link to Trade (if taken)
    trade_id INTEGER,  -- Links to actual trade if executed
    
    -- Indexes for fast queries
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for efficient querying
CREATE INDEX idx_scan_history_timestamp ON scan_history(timestamp DESC);
CREATE INDEX idx_scan_history_symbol ON scan_history(symbol);
CREATE INDEX idx_scan_history_strategy ON scan_history(strategy_name);
CREATE INDEX idx_scan_history_decision ON scan_history(decision);
CREATE INDEX idx_scan_history_symbol_strategy ON scan_history(symbol, strategy_name);
CREATE INDEX idx_scan_history_ml_confidence ON scan_history(ml_confidence);

-- Create a summary view for quick analysis
CREATE OR REPLACE VIEW scan_history_summary AS
SELECT 
    DATE_TRUNC('hour', timestamp) as hour,
    strategy_name,
    decision,
    COUNT(*) as count,
    AVG(ml_confidence) as avg_confidence,
    COUNT(DISTINCT symbol) as unique_symbols
FROM scan_history
GROUP BY DATE_TRUNC('hour', timestamp), strategy_name, decision
ORDER BY hour DESC, strategy_name;

-- Create a near-miss analysis view
CREATE OR REPLACE VIEW near_miss_analysis AS
SELECT 
    symbol,
    strategy_name,
    COUNT(*) as near_miss_count,
    AVG(ml_confidence) as avg_confidence,
    MAX(ml_confidence) as max_confidence,
    MIN(ml_confidence) as min_confidence,
    JSONB_AGG(DISTINCT reason) as rejection_reasons
FROM scan_history
WHERE decision = 'NEAR_MISS' 
   OR (decision = 'SKIP' AND ml_confidence > 0.50)
GROUP BY symbol, strategy_name
ORDER BY near_miss_count DESC;

COMMENT ON TABLE scan_history IS 'Captures every scan decision for ML learning and threshold optimization';
COMMENT ON COLUMN scan_history.decision IS 'TAKE=signal generated, SKIP=rejected, NEAR_MISS=almost triggered';
COMMENT ON COLUMN scan_history.features IS 'All features calculated at scan time for ML retraining';
