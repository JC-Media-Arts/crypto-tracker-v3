-- Migration: Create Strategy Label Tables for ML Training
-- Date: 2024-12-19
-- Purpose: Separate tables for ML training labels distinct from live trading tracking

-- DCA Labels for training
CREATE TABLE IF NOT EXISTS strategy_dca_labels (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    setup_detected BOOLEAN DEFAULT FALSE,
    
    -- Setup conditions
    drop_percentage DECIMAL(10,4),
    rsi DECIMAL(5,2),
    volume_ratio DECIMAL(10,4),
    btc_regime VARCHAR(20),
    
    -- Outcomes for training
    outcome VARCHAR(20), -- 'WIN', 'LOSS', 'BREAKEVEN', 'TIMEOUT'
    optimal_take_profit DECIMAL(5,2),
    optimal_stop_loss DECIMAL(5,2),
    actual_return DECIMAL(10,4),
    hold_time_hours INTEGER,
    
    -- Additional features as JSONB
    features JSONB,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, timestamp)
);

-- Swing Labels for training
CREATE TABLE IF NOT EXISTS strategy_swing_labels (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    breakout_detected BOOLEAN DEFAULT FALSE,
    
    -- Setup conditions
    breakout_strength DECIMAL(10,4),
    volume_surge DECIMAL(10,4),
    momentum_score DECIMAL(10,4),
    trend_alignment VARCHAR(20),
    
    -- Outcomes
    outcome VARCHAR(20),
    optimal_take_profit DECIMAL(5,2),
    optimal_stop_loss DECIMAL(5,2),
    actual_return DECIMAL(10,4),
    hold_time_hours INTEGER,
    
    -- Additional features
    features JSONB,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, timestamp)
);

-- Channel Labels for training
CREATE TABLE IF NOT EXISTS strategy_channel_labels (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    
    -- Setup conditions
    channel_position VARCHAR(20), -- 'TOP', 'BOTTOM', 'MIDDLE'
    channel_strength DECIMAL(10,4),
    channel_width DECIMAL(10,4),
    
    -- Outcomes
    outcome VARCHAR(20),
    optimal_entry DECIMAL(5,2),
    optimal_exit DECIMAL(5,2),
    actual_return DECIMAL(10,4),
    hold_time_hours INTEGER,
    
    -- Additional features
    features JSONB,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, timestamp)
);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_dca_labels_symbol_timestamp ON strategy_dca_labels(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_dca_labels_outcome ON strategy_dca_labels(outcome);
CREATE INDEX IF NOT EXISTS idx_dca_labels_setup ON strategy_dca_labels(setup_detected) WHERE setup_detected = true;

CREATE INDEX IF NOT EXISTS idx_swing_labels_symbol_timestamp ON strategy_swing_labels(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_swing_labels_outcome ON strategy_swing_labels(outcome);
CREATE INDEX IF NOT EXISTS idx_swing_labels_breakout ON strategy_swing_labels(breakout_detected) WHERE breakout_detected = true;

CREATE INDEX IF NOT EXISTS idx_channel_labels_symbol_timestamp ON strategy_channel_labels(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_channel_labels_outcome ON strategy_channel_labels(outcome);
CREATE INDEX IF NOT EXISTS idx_channel_labels_position ON strategy_channel_labels(channel_position);

-- Add comments for documentation
COMMENT ON TABLE strategy_dca_labels IS 'Training labels for DCA strategy ML model';
COMMENT ON TABLE strategy_swing_labels IS 'Training labels for Swing strategy ML model';
COMMENT ON TABLE strategy_channel_labels IS 'Training labels for Channel strategy ML model';

COMMENT ON COLUMN strategy_dca_labels.drop_percentage IS 'Percentage drop from recent high that triggered setup';
COMMENT ON COLUMN strategy_dca_labels.rsi IS 'RSI value at setup time';
COMMENT ON COLUMN strategy_dca_labels.volume_ratio IS 'Volume compared to average';
COMMENT ON COLUMN strategy_dca_labels.btc_regime IS 'Bitcoin market regime: BULL, BEAR, NEUTRAL';
COMMENT ON COLUMN strategy_dca_labels.outcome IS 'Trade outcome: WIN, LOSS, BREAKEVEN, TIMEOUT';
COMMENT ON COLUMN strategy_dca_labels.features IS 'Additional features in JSON format for ML flexibility';

COMMENT ON COLUMN strategy_swing_labels.breakout_strength IS 'Strength of price breakout (0-100)';
COMMENT ON COLUMN strategy_swing_labels.volume_surge IS 'Volume increase ratio during breakout';
COMMENT ON COLUMN strategy_swing_labels.momentum_score IS 'Combined momentum indicator score';
COMMENT ON COLUMN strategy_swing_labels.trend_alignment IS 'Trend direction: UPTREND, DOWNTREND, SIDEWAYS';

COMMENT ON COLUMN strategy_channel_labels.channel_position IS 'Price position in channel: TOP, BOTTOM, MIDDLE';
COMMENT ON COLUMN strategy_channel_labels.channel_strength IS 'Strength/reliability of channel (0-100)';
COMMENT ON COLUMN strategy_channel_labels.channel_width IS 'Width of channel as percentage';

-- Create a view for quick stats
CREATE OR REPLACE VIEW strategy_labels_summary AS
SELECT 
    'DCA' as strategy,
    COUNT(*) as total_labels,
    COUNT(CASE WHEN outcome = 'WIN' THEN 1 END) as wins,
    COUNT(CASE WHEN outcome = 'LOSS' THEN 1 END) as losses,
    ROUND(AVG(actual_return), 2) as avg_return,
    ROUND(AVG(hold_time_hours), 1) as avg_hold_hours
FROM strategy_dca_labels
WHERE outcome IS NOT NULL
UNION ALL
SELECT 
    'SWING' as strategy,
    COUNT(*) as total_labels,
    COUNT(CASE WHEN outcome = 'WIN' THEN 1 END) as wins,
    COUNT(CASE WHEN outcome = 'LOSS' THEN 1 END) as losses,
    ROUND(AVG(actual_return), 2) as avg_return,
    ROUND(AVG(hold_time_hours), 1) as avg_hold_hours
FROM strategy_swing_labels
WHERE outcome IS NOT NULL
UNION ALL
SELECT 
    'CHANNEL' as strategy,
    COUNT(*) as total_labels,
    COUNT(CASE WHEN outcome = 'WIN' THEN 1 END) as wins,
    COUNT(CASE WHEN outcome = 'LOSS' THEN 1 END) as losses,
    ROUND(AVG(actual_return), 2) as avg_return,
    ROUND(AVG(hold_time_hours), 1) as avg_hold_hours
FROM strategy_channel_labels
WHERE outcome IS NOT NULL;

COMMENT ON VIEW strategy_labels_summary IS 'Summary statistics for all strategy training labels';
