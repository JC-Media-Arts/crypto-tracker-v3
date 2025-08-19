-- Migration: Shadow Testing System
-- Date: 2025-01-20
-- Purpose: Enable parallel evaluation of alternative trading parameters without risk
-- This system tests multiple threshold variations simultaneously to accelerate learning

-- ============================================
-- SHADOW VARIATIONS TRACKING
-- ============================================
-- Tracks what each shadow variation would have done for every scan
CREATE TABLE IF NOT EXISTS shadow_variations (
    shadow_id SERIAL PRIMARY KEY,
    scan_id INTEGER REFERENCES scan_history(scan_id) ON DELETE CASCADE,
    
    -- Variation Identity
    variation_name VARCHAR(50) NOT NULL,  -- 'CHAMPION', 'BEAR_MARKET', 'DCA_DROP_3%', etc.
    variation_type VARCHAR(30) NOT NULL,  -- 'scenario', 'isolated_param', 'champion'
    
    -- Decision Parameters Used
    confidence_threshold DECIMAL(5,4),     -- The confidence threshold this variation used
    position_size_multiplier DECIMAL(5,2), -- Position size multiplier applied
    stop_loss_percent DECIMAL(5,2),        -- Stop loss percentage
    take_profit_multiplier DECIMAL(5,2),   -- TP multiplier (e.g., 0.8x, 1.2x of ML prediction)
    
    -- Strategy-Specific Parameters
    dca_drop_threshold DECIMAL(5,2),       -- For DCA: entry drop percentage
    dca_grid_levels INTEGER,               -- For DCA: number of grid levels
    dca_grid_spacing DECIMAL(5,2),         -- For DCA: spacing between levels
    swing_breakout_threshold DECIMAL(5,2), -- For Swing: breakout strength required
    swing_volume_multiplier DECIMAL(5,2),  -- For Swing: volume requirement
    channel_boundary_percent DECIMAL(5,2), -- For Channel: how close to boundaries
    
    -- Shadow Decision
    would_take_trade BOOLEAN NOT NULL,     -- Would this variation have taken the trade?
    shadow_confidence DECIMAL(5,4),        -- The confidence this variation calculated
    shadow_position_size DECIMAL(20,8),    -- Position size it would have used
    shadow_entry_price DECIMAL(20,8),      -- Entry price it would have used
    
    -- Predicted Targets (what this variation predicted)
    shadow_take_profit DECIMAL(10,4),
    shadow_stop_loss DECIMAL(10,4),
    shadow_hold_hours DECIMAL(10,2),
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================
-- SHADOW OUTCOMES TRACKING
-- ============================================
-- Records the evaluated outcomes of shadow trades
CREATE TABLE IF NOT EXISTS shadow_outcomes (
    outcome_id SERIAL PRIMARY KEY,
    shadow_id INTEGER REFERENCES shadow_variations(shadow_id) ON DELETE CASCADE,
    
    -- Evaluation Timing
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    evaluation_delay_hours DECIMAL(10,2),  -- How long after entry we evaluated
    
    -- Outcome Details
    outcome_status VARCHAR(20) NOT NULL,   -- 'WIN', 'LOSS', 'TIMEOUT', 'PENDING'
    exit_trigger VARCHAR(30),              -- 'take_profit', 'stop_loss', 'timeout'
    
    -- Performance Metrics
    exit_price DECIMAL(20,8),
    pnl_percentage DECIMAL(10,4),
    pnl_amount DECIMAL(20,8),
    actual_hold_hours DECIMAL(10,2),
    
    -- Grid Execution (for DCA)
    grid_fills INTEGER,                    -- How many grid levels filled
    average_entry_price DECIMAL(20,8),     -- Weighted average entry
    total_position_size DECIMAL(20,8),     -- Total size across all fills
    
    -- Accuracy Metrics
    prediction_accuracy JSONB,             -- Detailed accuracy breakdown
    matched_real_trade BOOLEAN,            -- Did this match what really happened?
    
    -- Market Context
    market_regime_at_exit VARCHAR(20),
    volatility_at_exit DECIMAL(10,4),
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================
-- SHADOW PERFORMANCE AGGREGATION
-- ============================================
-- Aggregated performance metrics by variation and timeframe
CREATE TABLE IF NOT EXISTS shadow_performance (
    variation_name VARCHAR(50) NOT NULL,
    timeframe VARCHAR(20) NOT NULL,        -- '24h', '3d', '7d', '30d'
    strategy_name VARCHAR(50) NOT NULL DEFAULT 'OVERALL',  -- 'OVERALL' for all strategies combined
    
    -- Trade Statistics
    total_opportunities INTEGER NOT NULL,   -- Total trades evaluated
    trades_taken INTEGER NOT NULL,          -- Trades that would have been taken
    trades_completed INTEGER NOT NULL,      -- Trades with known outcomes
    
    -- Performance Metrics
    wins INTEGER NOT NULL,
    losses INTEGER NOT NULL,
    timeouts INTEGER NOT NULL,
    win_rate DECIMAL(5,4),
    
    -- Financial Metrics
    total_pnl_percentage DECIMAL(10,4),
    avg_pnl_percentage DECIMAL(10,4),
    best_trade_pnl DECIMAL(10,4),
    worst_trade_pnl DECIMAL(10,4),
    sharpe_ratio DECIMAL(10,4),
    max_drawdown DECIMAL(10,4),
    
    -- Timing Metrics
    avg_hold_hours DECIMAL(10,2),
    avg_time_to_tp DECIMAL(10,2),
    avg_time_to_sl DECIMAL(10,2),
    
    -- Comparison Metrics
    outperformance_vs_champion DECIMAL(10,4),  -- How much better/worse than champion
    confidence_level VARCHAR(20),               -- 'HIGH', 'MEDIUM', 'LOW'
    statistical_significance DECIMAL(5,4),      -- p-value of outperformance
    
    -- Metadata
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    PRIMARY KEY (variation_name, timeframe, strategy_name)
);

-- ============================================
-- THRESHOLD ADJUSTMENTS HISTORY
-- ============================================
-- Tracks all parameter adjustments made based on shadow testing
CREATE TABLE IF NOT EXISTS threshold_adjustments (
    adjustment_id SERIAL PRIMARY KEY,
    
    -- What was adjusted
    strategy_name VARCHAR(50) NOT NULL,
    parameter_name VARCHAR(50) NOT NULL,
    
    -- The adjustment
    old_value DECIMAL(10,4) NOT NULL,
    new_value DECIMAL(10,4) NOT NULL,
    shadow_recommended_value DECIMAL(10,4),
    adjustment_percentage DECIMAL(10,4),   -- Percentage change
    
    -- Confidence and Evidence
    adjustment_confidence VARCHAR(20),     -- 'HIGH', 'MEDIUM', 'LOW'
    evidence_trades INTEGER,               -- Number of shadow trades supporting this
    evidence_timeframe VARCHAR(20),        -- Timeframe of evidence
    outperformance_percentage DECIMAL(10,4),
    statistical_p_value DECIMAL(5,4),
    
    -- Reasoning
    adjustment_reason TEXT,
    variation_source VARCHAR(50),          -- Which variation suggested this
    
    -- Safety Checks
    within_safety_limits BOOLEAN,
    market_regime_stable BOOLEAN,
    manual_override BOOLEAN DEFAULT FALSE,
    
    -- Outcome Tracking
    rollback_triggered BOOLEAN DEFAULT FALSE,
    rollback_reason TEXT,
    performance_after_24h DECIMAL(10,4),
    performance_after_7d DECIMAL(10,4),
    
    -- Metadata
    adjusted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    adjusted_by VARCHAR(50) DEFAULT 'shadow_system'
);

-- ============================================
-- SHADOW CONFIGURATION
-- ============================================
-- Stores current shadow testing configuration
CREATE TABLE IF NOT EXISTS shadow_configuration (
    config_id SERIAL PRIMARY KEY,
    
    -- Variation Definitions
    variation_name VARCHAR(50) NOT NULL UNIQUE,
    variation_config JSONB NOT NULL,       -- Full configuration for this variation
    is_active BOOLEAN DEFAULT TRUE,
    priority_order INTEGER,                -- Order to evaluate variations
    
    -- Performance Tracking
    total_evaluations INTEGER DEFAULT 0,
    total_wins INTEGER DEFAULT 0,
    lifetime_pnl DECIMAL(10,4),
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert default shadow variations
INSERT INTO shadow_configuration (variation_name, variation_config, priority_order) VALUES
('CHAMPION', '{"type": "champion", "description": "Current production settings"}', 1),
('BEAR_MARKET', '{"type": "scenario", "confidence": 0.55, "position_mult": 1.5, "description": "Aggressive settings for bear markets"}', 2),
('BULL_MARKET', '{"type": "scenario", "confidence": 0.65, "position_mult": 0.5, "description": "Conservative settings for bull markets"}', 3),
('ML_TRUST', '{"type": "scenario", "description": "Follow ML predictions exactly"}', 4),
('QUICK_EXITS', '{"type": "scenario", "tp_mult": 0.8, "description": "Take profits earlier"}', 5),
('DCA_DROPS', '{"type": "isolated", "parameter": "dca_drop", "test_values": [0.03, 0.05], "description": "Test DCA entry thresholds"}', 6),
('CONFIDENCE_TEST', '{"type": "isolated", "parameter": "confidence", "test_values": [0.55, 0.60], "description": "Test confidence thresholds"}', 7),
('VOLATILITY_SIZED', '{"type": "scenario", "description": "Dynamic position sizing based on volatility"}', 8)
ON CONFLICT (variation_name) DO NOTHING;

-- ============================================
-- INDEXES FOR PERFORMANCE
-- ============================================
CREATE INDEX IF NOT EXISTS idx_shadow_variations_scan_id ON shadow_variations(scan_id);
CREATE INDEX IF NOT EXISTS idx_shadow_variations_name ON shadow_variations(variation_name);
CREATE INDEX IF NOT EXISTS idx_shadow_variations_would_take ON shadow_variations(would_take_trade);
CREATE INDEX IF NOT EXISTS idx_shadow_variations_created_at ON shadow_variations(created_at);

CREATE INDEX IF NOT EXISTS idx_shadow_outcomes_shadow_id ON shadow_outcomes(shadow_id);
CREATE INDEX IF NOT EXISTS idx_shadow_outcomes_status ON shadow_outcomes(outcome_status);
CREATE INDEX IF NOT EXISTS idx_shadow_outcomes_evaluated_at ON shadow_outcomes(evaluated_at);

CREATE INDEX IF NOT EXISTS idx_shadow_performance_variation ON shadow_performance(variation_name);
CREATE INDEX IF NOT EXISTS idx_shadow_performance_updated ON shadow_performance(last_updated);

CREATE INDEX IF NOT EXISTS idx_threshold_adjustments_strategy ON threshold_adjustments(strategy_name);
CREATE INDEX IF NOT EXISTS idx_threshold_adjustments_parameter ON threshold_adjustments(parameter_name);
CREATE INDEX IF NOT EXISTS idx_threshold_adjustments_time ON threshold_adjustments(adjusted_at);

-- ============================================
-- VIEWS FOR ANALYSIS
-- ============================================

-- Champion vs Challengers Performance View
CREATE OR REPLACE VIEW champion_vs_challengers AS
WITH champion_performance AS (
    SELECT 
        timeframe,
        strategy_name,
        win_rate as champion_win_rate,
        avg_pnl_percentage as champion_avg_pnl,
        sharpe_ratio as champion_sharpe
    FROM shadow_performance
    WHERE variation_name = 'CHAMPION'
)
SELECT 
    sp.variation_name,
    sp.timeframe,
    sp.strategy_name,
    sp.win_rate,
    sp.avg_pnl_percentage,
    sp.sharpe_ratio,
    sp.win_rate - cp.champion_win_rate as win_rate_delta,
    sp.avg_pnl_percentage - cp.champion_avg_pnl as pnl_delta,
    sp.sharpe_ratio - cp.champion_sharpe as sharpe_delta,
    sp.outperformance_vs_champion,
    sp.confidence_level,
    sp.statistical_significance
FROM shadow_performance sp
LEFT JOIN champion_performance cp 
    ON sp.timeframe = cp.timeframe 
    AND sp.strategy_name = cp.strategy_name
WHERE sp.variation_name != 'CHAMPION'
ORDER BY sp.timeframe, sp.outperformance_vs_champion DESC;

-- Shadow Consensus View - How many shadows agree on each trade
CREATE OR REPLACE VIEW shadow_consensus AS
SELECT 
    scan_id,
    COUNT(*) as total_shadows,
    SUM(CASE WHEN would_take_trade THEN 1 ELSE 0 END) as shadows_taking_trade,
    AVG(CASE WHEN would_take_trade THEN shadow_confidence END) as avg_confidence_takers,
    ARRAY_AGG(CASE WHEN would_take_trade THEN variation_name END) FILTER (WHERE would_take_trade = true) as variations_taking,
    ARRAY_AGG(CASE WHEN NOT would_take_trade THEN variation_name END) FILTER (WHERE would_take_trade = false) as variations_skipping
FROM shadow_variations
GROUP BY scan_id;

-- ML Training Enhancement View - Adds shadow features
CREATE OR REPLACE VIEW ml_training_with_shadows AS
SELECT 
    s.scan_id,
    s.timestamp,
    s.symbol,
    s.strategy_name,
    s.features,
    s.ml_predictions,
    s.ml_confidence,
    -- Shadow consensus features
    sc.shadows_taking_trade::FLOAT / sc.total_shadows as shadow_consensus_score,
    sc.avg_confidence_takers as shadow_avg_confidence,
    -- Shadow performance delta
    COALESCE(sp.outperformance_vs_champion, 0) as shadow_performance_delta,
    -- Original outcome if trade was taken
    t.pnl_percentage as real_pnl,
    t.status as real_status,
    -- Shadow outcomes for comparison
    so.pnl_percentage as best_shadow_pnl,
    so.outcome_status as best_shadow_status
FROM scan_history s
LEFT JOIN shadow_consensus sc ON s.scan_id = sc.scan_id
LEFT JOIN trade_logs t ON s.scan_id = t.scan_id
LEFT JOIN LATERAL (
    SELECT sv.shadow_id, sv.variation_name
    FROM shadow_variations sv
    WHERE sv.scan_id = s.scan_id
    AND sv.would_take_trade = true
    ORDER BY sv.shadow_confidence DESC
    LIMIT 1
) best_shadow ON true
LEFT JOIN shadow_outcomes so ON best_shadow.shadow_id = so.shadow_id
LEFT JOIN shadow_performance sp 
    ON best_shadow.variation_name = sp.variation_name 
    AND sp.timeframe = '24h'
    AND sp.strategy_name = s.strategy_name;

-- Adjustment Impact Analysis View
CREATE OR REPLACE VIEW adjustment_impact AS
SELECT 
    ta.adjustment_id,
    ta.strategy_name,
    ta.parameter_name,
    ta.old_value,
    ta.new_value,
    ta.adjustment_percentage,
    ta.adjustment_confidence,
    ta.adjusted_at,
    -- Performance before (24h prior to adjustment)
    sp_before.win_rate as win_rate_before,
    sp_before.avg_pnl_percentage as avg_pnl_before,
    -- Performance after (24h after adjustment)
    sp_after.win_rate as win_rate_after,
    sp_after.avg_pnl_percentage as avg_pnl_after,
    -- Impact
    sp_after.win_rate - sp_before.win_rate as win_rate_change,
    sp_after.avg_pnl_percentage - sp_before.avg_pnl_percentage as pnl_change,
    ta.rollback_triggered,
    ta.rollback_reason
FROM threshold_adjustments ta
LEFT JOIN shadow_performance sp_before 
    ON sp_before.variation_name = 'CHAMPION'
    AND sp_before.timeframe = '24h'
    AND sp_before.strategy_name = ta.strategy_name
    AND sp_before.last_updated < ta.adjusted_at
LEFT JOIN shadow_performance sp_after
    ON sp_after.variation_name = 'CHAMPION'
    AND sp_after.timeframe = '24h'
    AND sp_after.strategy_name = ta.strategy_name
    AND sp_after.last_updated > ta.adjusted_at + INTERVAL '24 hours';

-- ============================================
-- FUNCTIONS FOR SHADOW EVALUATION
-- ============================================

-- Function to mark shadow trades ready for evaluation
CREATE OR REPLACE FUNCTION get_shadows_ready_for_evaluation()
RETURNS TABLE (
    shadow_id INTEGER,
    scan_id INTEGER,
    variation_name VARCHAR,
    created_at TIMESTAMPTZ,
    hours_since_creation DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        sv.shadow_id,
        sv.scan_id,
        sv.variation_name,
        sv.created_at,
        EXTRACT(EPOCH FROM (NOW() - sv.created_at)) / 3600 as hours_since_creation
    FROM shadow_variations sv
    LEFT JOIN shadow_outcomes so ON sv.shadow_id = so.shadow_id
    WHERE sv.would_take_trade = true
    AND so.outcome_id IS NULL  -- Not yet evaluated
    AND sv.created_at < NOW() - INTERVAL '5 minutes';  -- Give time for price to move
END;
$$ LANGUAGE plpgsql;

-- Function to calculate shadow weight for ML training
CREATE OR REPLACE FUNCTION calculate_shadow_weight(
    shadow_outcome_id INTEGER
) RETURNS DECIMAL AS $$
DECLARE
    base_weight DECIMAL := 0.1;
    outcome_record RECORD;
    variation_stats RECORD;
BEGIN
    -- Get outcome details
    SELECT * INTO outcome_record
    FROM shadow_outcomes
    WHERE outcome_id = shadow_outcome_id;
    
    -- Get variation performance
    SELECT * INTO variation_stats
    FROM shadow_performance
    WHERE variation_name = (
        SELECT variation_name 
        FROM shadow_variations 
        WHERE shadow_id = outcome_record.shadow_id
    )
    AND timeframe = '7d'
    LIMIT 1;
    
    -- Add weight if matched reality
    IF outcome_record.matched_real_trade THEN
        base_weight := base_weight + 0.2;
    END IF;
    
    -- Add weight if variation has good win rate
    IF variation_stats.win_rate > 0.60 THEN
        base_weight := base_weight + 0.1;
    END IF;
    
    -- Add weight if variation is mature (>7 days of data)
    IF variation_stats.trades_completed > 100 THEN
        base_weight := base_weight + 0.1;
    END IF;
    
    -- Add weight for statistical significance
    IF variation_stats.statistical_significance < 0.05 THEN
        base_weight := base_weight + 0.1;
    END IF;
    
    -- Cap at 0.5
    RETURN LEAST(base_weight, 0.5);
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- TRIGGERS FOR AUTOMATIC UPDATES
-- ============================================

-- Trigger to update shadow_configuration updated_at
CREATE OR REPLACE FUNCTION update_shadow_config_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_shadow_config_timestamp ON shadow_configuration;
CREATE TRIGGER trigger_update_shadow_config_timestamp
BEFORE UPDATE ON shadow_configuration
FOR EACH ROW
EXECUTE FUNCTION update_shadow_config_timestamp();

-- ============================================
-- HELPER FUNCTIONS FOR ML INTEGRATION
-- ============================================

-- Function to count shadow trades by strategy
CREATE OR REPLACE FUNCTION count_shadow_trades_by_strategy(p_strategy VARCHAR)
RETURNS TABLE (count BIGINT) AS $$
BEGIN
    RETURN QUERY
    SELECT COUNT(DISTINCT so.outcome_id)::BIGINT
    FROM shadow_outcomes so
    JOIN shadow_variations sv ON so.shadow_id = sv.shadow_id
    JOIN scan_history sh ON sv.scan_id = sh.scan_id
    WHERE sh.strategy_name = p_strategy
    AND so.outcome_status != 'PENDING';
END;
$$ LANGUAGE plpgsql;
