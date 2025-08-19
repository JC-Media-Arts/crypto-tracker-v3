-- 001_create_tables.sql
-- Migration: 001_create_tables.sql
-- Description: Create all tables for crypto ML trading system
-- Date: 2025-01-14

-- 1. Price data table (partitioned by month for performance)
CREATE TABLE IF NOT EXISTS price_data (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    price DECIMAL(20,8) NOT NULL,
    volume DECIMAL(20,2),
    PRIMARY KEY (symbol, timestamp)
);

-- Create index for efficient queries
CREATE INDEX IF NOT EXISTS idx_symbol_time ON price_data(symbol, timestamp DESC);

-- Enable partitioning by timestamp (monthly)
-- Note: Supabase may handle this differently, adjust as needed
-- CREATE TABLE price_data_2025_01 PARTITION OF price_data
-- FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

-- 2. ML Features table (pre-calculated technical indicators)
CREATE TABLE IF NOT EXISTS ml_features (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    price_change_5m DECIMAL(10,4),
    price_change_1h DECIMAL(10,4),
    volume_ratio DECIMAL(10,4),
    rsi_14 DECIMAL(10,2),
    distance_from_support DECIMAL(10,4),
    returns_5m DECIMAL(10,4),
    returns_1h DECIMAL(10,4),
    distance_from_sma20 DECIMAL(10,4),
    support_distance DECIMAL(10,4),
    PRIMARY KEY (symbol, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_ml_features_symbol_time ON ml_features(symbol, timestamp DESC);

-- 3. ML Predictions table
CREATE TABLE IF NOT EXISTS ml_predictions (
    prediction_id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    prediction VARCHAR(10) NOT NULL CHECK (prediction IN ('UP', 'DOWN')),
    confidence DECIMAL(3,2) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    actual_move DECIMAL(10,4),
    correct BOOLEAN,
    model_version VARCHAR(50)
);

CREATE INDEX IF NOT EXISTS idx_predictions_symbol_time ON ml_predictions(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_confidence ON ml_predictions(confidence DESC);

-- 4. Hummingbot Paper Trades table
CREATE TABLE IF NOT EXISTS hummingbot_trades (
    trade_id SERIAL PRIMARY KEY,
    hummingbot_order_id VARCHAR(100) UNIQUE,
    symbol VARCHAR(10) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    order_type VARCHAR(20) NOT NULL,
    price DECIMAL(20,8) NOT NULL,
    amount DECIMAL(20,8) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    filled_at TIMESTAMPTZ,
    ml_prediction_id INTEGER REFERENCES ml_predictions(prediction_id),
    ml_confidence DECIMAL(3,2),
    fees DECIMAL(10,4) DEFAULT 0,
    slippage DECIMAL(10,4) DEFAULT 0,
    pnl DECIMAL(10,2)
);

CREATE INDEX IF NOT EXISTS idx_hummingbot_trades_symbol ON hummingbot_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_hummingbot_trades_status ON hummingbot_trades(status);
CREATE INDEX IF NOT EXISTS idx_hummingbot_trades_created ON hummingbot_trades(created_at DESC);

-- 5. Hummingbot Performance metrics
CREATE TABLE IF NOT EXISTS hummingbot_performance (
    timestamp TIMESTAMPTZ PRIMARY KEY,
    total_trades INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    losing_trades INTEGER NOT NULL DEFAULT 0,
    total_pnl DECIMAL(10,2) NOT NULL DEFAULT 0,
    win_rate DECIMAL(5,2),
    sharpe_ratio DECIMAL(5,2),
    max_drawdown DECIMAL(5,2),
    best_trade JSONB,
    worst_trade JSONB,
    avg_trade_duration_minutes INTEGER
);

-- 6. Daily Performance summary
CREATE TABLE IF NOT EXISTS daily_performance (
    date DATE PRIMARY KEY,
    trades_count INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    net_pnl DECIMAL(10,2) NOT NULL DEFAULT 0,
    ml_accuracy DECIMAL(5,2),
    avg_slippage DECIMAL(10,4),
    avg_fees DECIMAL(10,4),
    total_volume DECIMAL(20,2)
);

-- 7. Health Metrics for monitoring
CREATE TABLE IF NOT EXISTS health_metrics (
    timestamp TIMESTAMPTZ PRIMARY KEY,
    metric_name VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('healthy', 'warning', 'critical')),
    value DECIMAL(10,2),
    details JSONB,
    alert_sent BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_health_metrics_name ON health_metrics(metric_name, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_health_metrics_status ON health_metrics(status);

-- 8. System Configuration (for storing ML model info, etc.)
CREATE TABLE IF NOT EXISTS system_config (
    config_key VARCHAR(100) PRIMARY KEY,
    config_value JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    description TEXT
);

-- Insert default configurations
INSERT INTO system_config (config_key, config_value, description) VALUES
    ('ml_model_version', '"1.0.0"', 'Current ML model version'),
    ('trading_enabled', 'true', 'Global trading enable/disable flag'),
    ('supported_symbols', '["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "AVAX", "DOGE", "DOT", "POL"]', 'List of supported trading symbols')
ON CONFLICT (config_key) DO NOTHING;

-- 9. Model Training History
CREATE TABLE IF NOT EXISTS model_training_history (
    training_id SERIAL PRIMARY KEY,
    model_version VARCHAR(50) NOT NULL,
    trained_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    training_data_start DATE NOT NULL,
    training_data_end DATE NOT NULL,
    features_used JSONB NOT NULL,
    hyperparameters JSONB NOT NULL,
    validation_accuracy DECIMAL(5,4),
    test_accuracy DECIMAL(5,4),
    model_path VARCHAR(255),
    notes TEXT
);

-- Create views for easier querying

-- View for recent predictions with accuracy
CREATE OR REPLACE VIEW v_recent_predictions AS
SELECT 
    p.prediction_id,
    p.timestamp,
    p.symbol,
    p.prediction,
    p.confidence,
    p.actual_move,
    p.correct,
    CASE 
        WHEN p.correct IS TRUE THEN 'Correct'
        WHEN p.correct IS FALSE THEN 'Incorrect'
        ELSE 'Pending'
    END as result_status
FROM ml_predictions p
WHERE p.timestamp > NOW() - INTERVAL '24 hours'
ORDER BY p.timestamp DESC;

-- View for daily trading summary
CREATE OR REPLACE VIEW v_daily_trading_summary AS
SELECT 
    DATE(created_at) as trading_date,
    symbol,
    COUNT(*) as total_trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
    SUM(pnl) as total_pnl,
    AVG(fees) as avg_fees,
    AVG(slippage) as avg_slippage
FROM hummingbot_trades
WHERE status = 'FILLED'
GROUP BY DATE(created_at), symbol
ORDER BY trading_date DESC, symbol;

-- Grant permissions (adjust based on your Supabase setup)
-- GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
-- GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated;

-- Add comments for documentation
COMMENT ON TABLE price_data IS 'Stores real-time price data from Polygon.io';
COMMENT ON TABLE ml_features IS 'Pre-calculated technical indicators for ML model';
COMMENT ON TABLE ml_predictions IS 'ML model predictions and their outcomes';
COMMENT ON TABLE hummingbot_trades IS 'Paper trading records from Hummingbot';
COMMENT ON TABLE daily_performance IS 'Daily aggregated performance metrics';
COMMENT ON TABLE health_metrics IS 'System health monitoring data';


-- 002_strategy_tables.sql
-- Migration: Add Strategy-First Tables
-- Date: 2025-08-16
-- Purpose: Support DCA and Swing trading strategies with ML optimization

-- 1. Strategy Configurations
CREATE TABLE IF NOT EXISTS strategy_configs (
    strategy_id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(50) NOT NULL,  -- 'DCA' or 'SWING'
    parameters JSONB NOT NULL,  -- Strategy-specific parameters
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Strategy Setups (Detected Opportunities)
CREATE TABLE IF NOT EXISTS strategy_setups (
    setup_id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(50) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL,
    setup_price DECIMAL(20,8) NOT NULL,
    setup_data JSONB,  -- Setup-specific data (support levels, resistance, etc.)
    ml_confidence DECIMAL(3,2),
    is_executed BOOLEAN DEFAULT FALSE,
    executed_at TIMESTAMPTZ,
    outcome VARCHAR(20),  -- 'WIN', 'LOSS', 'BREAKEVEN', 'EXPIRED'
    pnl DECIMAL(10,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. DCA Grids (For DCA Strategy Execution)
CREATE TABLE IF NOT EXISTS dca_grids (
    grid_id SERIAL PRIMARY KEY,
    setup_id INTEGER REFERENCES strategy_setups(setup_id),
    symbol VARCHAR(10) NOT NULL,
    grid_levels JSONB NOT NULL,  -- Array of {price, size, status}
    total_invested DECIMAL(10,2),
    average_price DECIMAL(20,8),
    status VARCHAR(20) NOT NULL,  -- 'PENDING', 'ACTIVE', 'COMPLETED', 'STOPPED'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    final_pnl DECIMAL(10,2)
);

-- 4. Market Regimes (BTC Market Conditions)
CREATE TABLE IF NOT EXISTS market_regimes (
    timestamp TIMESTAMPTZ PRIMARY KEY,
    btc_regime VARCHAR(20) NOT NULL,  -- 'BULL', 'BEAR', 'NEUTRAL', 'CRASH'
    btc_price DECIMAL(20,8) NOT NULL,
    btc_trend_strength DECIMAL(10,4),
    market_fear_greed INTEGER CHECK (market_fear_greed >= 0 AND market_fear_greed <= 100),  -- 0-100 scale
    total_market_cap DECIMAL(20,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_strategy_setups_symbol ON strategy_setups(symbol);
CREATE INDEX IF NOT EXISTS idx_strategy_setups_detected ON strategy_setups(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_strategy_setups_executed ON strategy_setups(is_executed);
CREATE INDEX IF NOT EXISTS idx_dca_grids_status ON dca_grids(status);
CREATE INDEX IF NOT EXISTS idx_market_regimes_timestamp ON market_regimes(timestamp DESC);

-- Add strategy_name column to ml_predictions if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='ml_predictions' AND column_name='strategy_name') THEN
        ALTER TABLE ml_predictions ADD COLUMN strategy_name VARCHAR(50);
    END IF;
END $$;

-- Add setup_id reference to ml_predictions if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='ml_predictions' AND column_name='setup_id') THEN
        ALTER TABLE ml_predictions ADD COLUMN setup_id INTEGER REFERENCES strategy_setups(setup_id);
    END IF;
END $$;

-- Add strategy_name to hummingbot_trades if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='hummingbot_trades' AND column_name='strategy_name') THEN
        ALTER TABLE hummingbot_trades ADD COLUMN strategy_name VARCHAR(50);
    END IF;
END $$;

-- Add setup_id reference to hummingbot_trades if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='hummingbot_trades' AND column_name='setup_id') THEN
        ALTER TABLE hummingbot_trades ADD COLUMN setup_id INTEGER REFERENCES strategy_setups(setup_id);
    END IF;
END $$;

-- Insert default strategy configurations
INSERT INTO strategy_configs (strategy_name, parameters, is_active) VALUES
('DCA', '{
    "price_drop_threshold": -5.0,
    "timeframe": "4h",
    "volume_filter": "above_average",
    "btc_regime_filter": ["BULL", "NEUTRAL"],
    "grid_levels": 5,
    "grid_spacing": 1.0,
    "base_size": 100,
    "take_profit": 10.0,
    "stop_loss": -8.0,
    "time_exit_hours": 72,
    "ml_confidence_threshold": 0.60
}'::jsonb, true),
('SWING', '{
    "breakout_threshold": 3.0,
    "volume_surge": 2.0,
    "momentum_confirmation": "rsi > 60",
    "trend_alignment": "uptrend_on_4h",
    "position_size": 200,
    "entry_type": "market",
    "max_slippage": 0.5,
    "take_profit": 15.0,
    "stop_loss": -5.0,
    "trailing_stop": 7.0,
    "time_exit_hours": 48,
    "ml_confidence_threshold": 0.65
}'::jsonb, true)
ON CONFLICT DO NOTHING;

-- Create a view for strategy performance
CREATE OR REPLACE VIEW strategy_performance AS
SELECT 
    s.strategy_name,
    COUNT(*) as total_setups,
    COUNT(CASE WHEN s.is_executed THEN 1 END) as executed_setups,
    COUNT(CASE WHEN s.outcome = 'WIN' THEN 1 END) as wins,
    COUNT(CASE WHEN s.outcome = 'LOSS' THEN 1 END) as losses,
    ROUND(COUNT(CASE WHEN s.outcome = 'WIN' THEN 1 END)::numeric / 
          NULLIF(COUNT(CASE WHEN s.outcome IN ('WIN', 'LOSS') THEN 1 END), 0) * 100, 2) as win_rate,
    ROUND(AVG(CASE WHEN s.outcome = 'WIN' THEN s.pnl END), 2) as avg_win,
    ROUND(AVG(CASE WHEN s.outcome = 'LOSS' THEN s.pnl END), 2) as avg_loss,
    ROUND(SUM(s.pnl), 2) as total_pnl
FROM strategy_setups s
GROUP BY s.strategy_name;

COMMENT ON TABLE strategy_configs IS 'Configuration parameters for each trading strategy';
COMMENT ON TABLE strategy_setups IS 'Detected trading opportunities for each strategy';
COMMENT ON TABLE dca_grids IS 'DCA grid orders and execution tracking';
COMMENT ON TABLE market_regimes IS 'Market regime classification for strategy filtering';


-- 002_strategy_tables_clean.sql
-- Migration: Add Strategy-First Tables
-- Date: 2025-08-16
-- Purpose: Support DCA and Swing trading strategies with ML optimization

-- 1. Strategy Configurations
CREATE TABLE IF NOT EXISTS strategy_configs (
    strategy_id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(50) NOT NULL,  -- 'DCA' or 'SWING'
    parameters JSONB NOT NULL,  -- Strategy-specific parameters
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Strategy Setups (Detected Opportunities)
CREATE TABLE IF NOT EXISTS strategy_setups (
    setup_id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(50) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL,
    setup_price DECIMAL(20,8) NOT NULL,
    setup_data JSONB,  -- Setup-specific data (support levels, resistance, etc.)
    ml_confidence DECIMAL(3,2),
    is_executed BOOLEAN DEFAULT FALSE,
    executed_at TIMESTAMPTZ,
    outcome VARCHAR(20),  -- 'WIN', 'LOSS', 'BREAKEVEN', 'EXPIRED'
    pnl DECIMAL(10,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. DCA Grids (For DCA Strategy Execution)
CREATE TABLE IF NOT EXISTS dca_grids (
    grid_id SERIAL PRIMARY KEY,
    setup_id INTEGER REFERENCES strategy_setups(setup_id),
    symbol VARCHAR(10) NOT NULL,
    grid_levels JSONB NOT NULL,  -- Array of {price, size, status}
    total_invested DECIMAL(10,2),
    average_price DECIMAL(20,8),
    status VARCHAR(20) NOT NULL,  -- 'PENDING', 'ACTIVE', 'COMPLETED', 'STOPPED'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    final_pnl DECIMAL(10,2)
);

-- 4. Market Regimes (BTC Market Conditions)
CREATE TABLE IF NOT EXISTS market_regimes (
    timestamp TIMESTAMPTZ PRIMARY KEY,
    btc_regime VARCHAR(20) NOT NULL,  -- 'BULL', 'BEAR', 'NEUTRAL', 'CRASH'
    btc_price DECIMAL(20,8) NOT NULL,
    btc_trend_strength DECIMAL(10,4),
    market_fear_greed INTEGER CHECK (market_fear_greed >= 0 AND market_fear_greed <= 100),  -- 0-100 scale
    total_market_cap DECIMAL(20,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_strategy_setups_symbol ON strategy_setups(symbol);
CREATE INDEX IF NOT EXISTS idx_strategy_setups_detected ON strategy_setups(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_strategy_setups_executed ON strategy_setups(is_executed);
CREATE INDEX IF NOT EXISTS idx_dca_grids_status ON dca_grids(status);
CREATE INDEX IF NOT EXISTS idx_market_regimes_timestamp ON market_regimes(timestamp DESC);

-- Add strategy_name column to ml_predictions if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='ml_predictions' AND column_name='strategy_name') THEN
        ALTER TABLE ml_predictions ADD COLUMN strategy_name VARCHAR(50);
    END IF;
END $$;

-- Add setup_id reference to ml_predictions if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='ml_predictions' AND column_name='setup_id') THEN
        ALTER TABLE ml_predictions ADD COLUMN setup_id INTEGER REFERENCES strategy_setups(setup_id);
    END IF;
END $$;

-- Add strategy_name to hummingbot_trades if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='hummingbot_trades' AND column_name='strategy_name') THEN
        ALTER TABLE hummingbot_trades ADD COLUMN strategy_name VARCHAR(50);
    END IF;
END $$;

-- Add setup_id reference to hummingbot_trades if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='hummingbot_trades' AND column_name='setup_id') THEN
        ALTER TABLE hummingbot_trades ADD COLUMN setup_id INTEGER REFERENCES strategy_setups(setup_id);
    END IF;
END $$;

-- Insert default strategy configurations
INSERT INTO strategy_configs (strategy_name, parameters, is_active) VALUES
('DCA', '{
    "price_drop_threshold": -5.0,
    "timeframe": "4h",
    "volume_filter": "above_average",
    "btc_regime_filter": ["BULL", "NEUTRAL"],
    "grid_levels": 5,
    "grid_spacing": 1.0,
    "base_size": 100,
    "take_profit": 10.0,
    "stop_loss": -8.0,
    "time_exit_hours": 72,
    "ml_confidence_threshold": 0.60
}'::jsonb, true),
('SWING', '{
    "breakout_threshold": 3.0,
    "volume_surge": 2.0,
    "momentum_confirmation": "rsi > 60",
    "trend_alignment": "uptrend_on_4h",
    "position_size": 200,
    "entry_type": "market",
    "max_slippage": 0.5,
    "take_profit": 15.0,
    "stop_loss": -5.0,
    "trailing_stop": 7.0,
    "time_exit_hours": 48,
    "ml_confidence_threshold": 0.65
}'::jsonb, true)
ON CONFLICT DO NOTHING;

-- Create a view for strategy performance
CREATE OR REPLACE VIEW strategy_performance AS
SELECT 
    s.strategy_name,
    COUNT(*) as total_setups,
    COUNT(CASE WHEN s.is_executed THEN 1 END) as executed_setups,
    COUNT(CASE WHEN s.outcome = 'WIN' THEN 1 END) as wins,
    COUNT(CASE WHEN s.outcome = 'LOSS' THEN 1 END) as losses,
    ROUND(COUNT(CASE WHEN s.outcome = 'WIN' THEN 1 END)::numeric / 
          NULLIF(COUNT(CASE WHEN s.outcome IN ('WIN', 'LOSS') THEN 1 END), 0) * 100, 2) as win_rate,
    ROUND(AVG(CASE WHEN s.outcome = 'WIN' THEN s.pnl END), 2) as avg_win,
    ROUND(AVG(CASE WHEN s.outcome = 'LOSS' THEN s.pnl END), 2) as avg_loss,
    ROUND(SUM(s.pnl), 2) as total_pnl
FROM strategy_setups s
GROUP BY s.strategy_name;

-- Add comments for documentation
COMMENT ON TABLE strategy_configs IS 'Configuration parameters for each trading strategy';
COMMENT ON TABLE strategy_setups IS 'Detected trading opportunities for each strategy';
COMMENT ON TABLE dca_grids IS 'DCA grid orders and execution tracking';
COMMENT ON TABLE market_regimes IS 'Market regime classification for strategy filtering';


-- 003_create_ohlc_table.sql
-- Create OHLC (Open, High, Low, Close) data table
-- This stores aggregated candlestick data from Polygon

CREATE TABLE IF NOT EXISTS ohlc_data (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    open DECIMAL(20,8) NOT NULL,
    high DECIMAL(20,8) NOT NULL,
    low DECIMAL(20,8) NOT NULL,
    close DECIMAL(20,8) NOT NULL,
    volume DECIMAL(20,4),
    num_trades INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Primary key on timestamp + symbol
    PRIMARY KEY (timestamp, symbol)
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_ohlc_symbol ON ohlc_data(symbol);
CREATE INDEX IF NOT EXISTS idx_ohlc_timestamp ON ohlc_data(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_ohlc_symbol_timestamp ON ohlc_data(symbol, timestamp DESC);

-- Add comment
COMMENT ON TABLE ohlc_data IS 'Hourly OHLC candlestick data for crypto symbols';
COMMENT ON COLUMN ohlc_data.open IS 'Opening price at start of period';
COMMENT ON COLUMN ohlc_data.high IS 'Highest price during period';
COMMENT ON COLUMN ohlc_data.low IS 'Lowest price during period';
COMMENT ON COLUMN ohlc_data.close IS 'Closing price at end of period';
COMMENT ON COLUMN ohlc_data.volume IS 'Total volume traded during period';
COMMENT ON COLUMN ohlc_data.num_trades IS 'Number of trades during period';


-- 003_create_unified_ohlc_table.sql
-- Create unified OHLC table for all timeframes
-- This stores all candlestick data: 1m, 15m, 1h, 1d
-- Designed for complete backtesting capability

-- Drop old table if exists (from previous attempt)
DROP TABLE IF EXISTS ohlc_data;

-- Create the unified OHLC table
CREATE TABLE ohlc_data (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    timeframe VARCHAR(10) NOT NULL, -- '1m', '15m', '1h', '1d'
    open DECIMAL(20,8) NOT NULL,
    high DECIMAL(20,8) NOT NULL,
    low DECIMAL(20,8) NOT NULL,
    close DECIMAL(20,8) NOT NULL,
    volume DECIMAL(20,4),
    vwap DECIMAL(20,8),  -- Volume-weighted average price
    trades INTEGER,      -- Number of trades in period
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Composite primary key prevents duplicates
    PRIMARY KEY (symbol, timeframe, timestamp)
);

-- Indexes for fast queries
CREATE INDEX idx_ohlc_symbol_tf_time ON ohlc_data(symbol, timeframe, timestamp DESC);
CREATE INDEX idx_ohlc_time ON ohlc_data(timestamp DESC);
CREATE INDEX idx_ohlc_symbol ON ohlc_data(symbol);
CREATE INDEX idx_ohlc_timeframe ON ohlc_data(timeframe);

-- Add comments for documentation
COMMENT ON TABLE ohlc_data IS 'Unified OHLC data for all timeframes - supports complete backtesting';
COMMENT ON COLUMN ohlc_data.timeframe IS 'Timeframe: 1m, 15m, 1h, or 1d';
COMMENT ON COLUMN ohlc_data.open IS 'Opening price at start of period';
COMMENT ON COLUMN ohlc_data.high IS 'Highest price during period';
COMMENT ON COLUMN ohlc_data.low IS 'Lowest price during period';
COMMENT ON COLUMN ohlc_data.close IS 'Closing price at end of period';
COMMENT ON COLUMN ohlc_data.volume IS 'Total volume traded during period';
COMMENT ON COLUMN ohlc_data.vwap IS 'Volume-weighted average price';
COMMENT ON COLUMN ohlc_data.trades IS 'Number of trades during period';

-- Create a view for easy access to latest data per symbol/timeframe
CREATE OR REPLACE VIEW latest_ohlc AS
SELECT DISTINCT ON (symbol, timeframe) 
    symbol,
    timeframe,
    timestamp,
    close as latest_price,
    volume as latest_volume
FROM ohlc_data
ORDER BY symbol, timeframe, timestamp DESC;

-- Create a function to check for data gaps
CREATE OR REPLACE FUNCTION check_ohlc_gaps(
    p_symbol VARCHAR,
    p_timeframe VARCHAR,
    p_start_date TIMESTAMPTZ,
    p_end_date TIMESTAMPTZ
) RETURNS TABLE(gap_start TIMESTAMPTZ, gap_end TIMESTAMPTZ, missing_bars INTEGER)
LANGUAGE plpgsql
AS $$
DECLARE
    interval_minutes INTEGER;
BEGIN
    -- Determine interval based on timeframe
    CASE p_timeframe
        WHEN '1m' THEN interval_minutes := 1;
        WHEN '15m' THEN interval_minutes := 15;
        WHEN '1h' THEN interval_minutes := 60;
        WHEN '1d' THEN interval_minutes := 1440;
        ELSE interval_minutes := 60; -- Default to hourly
    END CASE;
    
    -- Find gaps in the data
    RETURN QUERY
    WITH ordered_data AS (
        SELECT 
            timestamp,
            LEAD(timestamp) OVER (ORDER BY timestamp) as next_timestamp
        FROM ohlc_data
        WHERE symbol = p_symbol 
        AND timeframe = p_timeframe
        AND timestamp BETWEEN p_start_date AND p_end_date
    )
    SELECT 
        timestamp as gap_start,
        next_timestamp as gap_end,
        EXTRACT(EPOCH FROM (next_timestamp - timestamp))::INTEGER / (interval_minutes * 60) - 1 as missing_bars
    FROM ordered_data
    WHERE next_timestamp - timestamp > INTERVAL '1 minute' * interval_minutes
    ORDER BY timestamp;
END;
$$;


-- 004_create_scan_history.sql
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


-- combined_migration.sql
-- 001_create_tables.sql
-- Migration: 001_create_tables.sql
-- Description: Create all tables for crypto ML trading system
-- Date: 2025-01-14

-- 1. Price data table (partitioned by month for performance)
CREATE TABLE IF NOT EXISTS price_data (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    price DECIMAL(20,8) NOT NULL,
    volume DECIMAL(20,2),
    PRIMARY KEY (symbol, timestamp)
);

-- Create index for efficient queries
CREATE INDEX IF NOT EXISTS idx_symbol_time ON price_data(symbol, timestamp DESC);

-- Enable partitioning by timestamp (monthly)
-- Note: Supabase may handle this differently, adjust as needed
-- CREATE TABLE price_data_2025_01 PARTITION OF price_data
-- FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

-- 2. ML Features table (pre-calculated technical indicators)
CREATE TABLE IF NOT EXISTS ml_features (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    price_change_5m DECIMAL(10,4),
    price_change_1h DECIMAL(10,4),
    volume_ratio DECIMAL(10,4),
    rsi_14 DECIMAL(10,2),
    distance_from_support DECIMAL(10,4),
    returns_5m DECIMAL(10,4),
    returns_1h DECIMAL(10,4),
    distance_from_sma20 DECIMAL(10,4),
    support_distance DECIMAL(10,4),
    PRIMARY KEY (symbol, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_ml_features_symbol_time ON ml_features(symbol, timestamp DESC);

-- 3. ML Predictions table
CREATE TABLE IF NOT EXISTS ml_predictions (
    prediction_id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    prediction VARCHAR(10) NOT NULL CHECK (prediction IN ('UP', 'DOWN')),
    confidence DECIMAL(3,2) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    actual_move DECIMAL(10,4),
    correct BOOLEAN,
    model_version VARCHAR(50)
);

CREATE INDEX IF NOT EXISTS idx_predictions_symbol_time ON ml_predictions(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_confidence ON ml_predictions(confidence DESC);

-- 4. Hummingbot Paper Trades table
CREATE TABLE IF NOT EXISTS hummingbot_trades (
    trade_id SERIAL PRIMARY KEY,
    hummingbot_order_id VARCHAR(100) UNIQUE,
    symbol VARCHAR(10) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    order_type VARCHAR(20) NOT NULL,
    price DECIMAL(20,8) NOT NULL,
    amount DECIMAL(20,8) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    filled_at TIMESTAMPTZ,
    ml_prediction_id INTEGER REFERENCES ml_predictions(prediction_id),
    ml_confidence DECIMAL(3,2),
    fees DECIMAL(10,4) DEFAULT 0,
    slippage DECIMAL(10,4) DEFAULT 0,
    pnl DECIMAL(10,2)
);

CREATE INDEX IF NOT EXISTS idx_hummingbot_trades_symbol ON hummingbot_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_hummingbot_trades_status ON hummingbot_trades(status);
CREATE INDEX IF NOT EXISTS idx_hummingbot_trades_created ON hummingbot_trades(created_at DESC);

-- 5. Hummingbot Performance metrics
CREATE TABLE IF NOT EXISTS hummingbot_performance (
    timestamp TIMESTAMPTZ PRIMARY KEY,
    total_trades INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    losing_trades INTEGER NOT NULL DEFAULT 0,
    total_pnl DECIMAL(10,2) NOT NULL DEFAULT 0,
    win_rate DECIMAL(5,2),
    sharpe_ratio DECIMAL(5,2),
    max_drawdown DECIMAL(5,2),
    best_trade JSONB,
    worst_trade JSONB,
    avg_trade_duration_minutes INTEGER
);

-- 6. Daily Performance summary
CREATE TABLE IF NOT EXISTS daily_performance (
    date DATE PRIMARY KEY,
    trades_count INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    net_pnl DECIMAL(10,2) NOT NULL DEFAULT 0,
    ml_accuracy DECIMAL(5,2),
    avg_slippage DECIMAL(10,4),
    avg_fees DECIMAL(10,4),
    total_volume DECIMAL(20,2)
);

-- 7. Health Metrics for monitoring
CREATE TABLE IF NOT EXISTS health_metrics (
    timestamp TIMESTAMPTZ PRIMARY KEY,
    metric_name VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('healthy', 'warning', 'critical')),
    value DECIMAL(10,2),
    details JSONB,
    alert_sent BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_health_metrics_name ON health_metrics(metric_name, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_health_metrics_status ON health_metrics(status);

-- 8. System Configuration (for storing ML model info, etc.)
CREATE TABLE IF NOT EXISTS system_config (
    config_key VARCHAR(100) PRIMARY KEY,
    config_value JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    description TEXT
);

-- Insert default configurations
INSERT INTO system_config (config_key, config_value, description) VALUES
    ('ml_model_version', '"1.0.0"', 'Current ML model version'),
    ('trading_enabled', 'true', 'Global trading enable/disable flag'),
    ('supported_symbols', '["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "AVAX", "DOGE", "DOT", "POL"]', 'List of supported trading symbols')
ON CONFLICT (config_key) DO NOTHING;

-- 9. Model Training History
CREATE TABLE IF NOT EXISTS model_training_history (
    training_id SERIAL PRIMARY KEY,
    model_version VARCHAR(50) NOT NULL,
    trained_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    training_data_start DATE NOT NULL,
    training_data_end DATE NOT NULL,
    features_used JSONB NOT NULL,
    hyperparameters JSONB NOT NULL,
    validation_accuracy DECIMAL(5,4),
    test_accuracy DECIMAL(5,4),
    model_path VARCHAR(255),
    notes TEXT
);

-- Create views for easier querying

-- View for recent predictions with accuracy
CREATE OR REPLACE VIEW v_recent_predictions AS
SELECT 
    p.prediction_id,
    p.timestamp,
    p.symbol,
    p.prediction,
    p.confidence,
    p.actual_move,
    p.correct,
    CASE 
        WHEN p.correct IS TRUE THEN 'Correct'
        WHEN p.correct IS FALSE THEN 'Incorrect'
        ELSE 'Pending'
    END as result_status
FROM ml_predictions p
WHERE p.timestamp > NOW() - INTERVAL '24 hours'
ORDER BY p.timestamp DESC;

-- View for daily trading summary
CREATE OR REPLACE VIEW v_daily_trading_summary AS
SELECT 
    DATE(created_at) as trading_date,
    symbol,
    COUNT(*) as total_trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
    SUM(pnl) as total_pnl,
    AVG(fees) as avg_fees,
    AVG(slippage) as avg_slippage
FROM hummingbot_trades
WHERE status = 'FILLED'
GROUP BY DATE(created_at), symbol
ORDER BY trading_date DESC, symbol;

-- Grant permissions (adjust based on your Supabase setup)
-- GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
-- GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated;

-- Add comments for documentation
COMMENT ON TABLE price_data IS 'Stores real-time price data from Polygon.io';
COMMENT ON TABLE ml_features IS 'Pre-calculated technical indicators for ML model';
COMMENT ON TABLE ml_predictions IS 'ML model predictions and their outcomes';
COMMENT ON TABLE hummingbot_trades IS 'Paper trading records from Hummingbot';
COMMENT ON TABLE daily_performance IS 'Daily aggregated performance metrics';
COMMENT ON TABLE health_metrics IS 'System health monitoring data';


-- 002_strategy_tables.sql
-- Migration: Add Strategy-First Tables
-- Date: 2025-08-16
-- Purpose: Support DCA and Swing trading strategies with ML optimization

-- 1. Strategy Configurations
CREATE TABLE IF NOT EXISTS strategy_configs (
    strategy_id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(50) NOT NULL,  -- 'DCA' or 'SWING'
    parameters JSONB NOT NULL,  -- Strategy-specific parameters
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Strategy Setups (Detected Opportunities)
CREATE TABLE IF NOT EXISTS strategy_setups (
    setup_id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(50) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL,
    setup_price DECIMAL(20,8) NOT NULL,
    setup_data JSONB,  -- Setup-specific data (support levels, resistance, etc.)
    ml_confidence DECIMAL(3,2),
    is_executed BOOLEAN DEFAULT FALSE,
    executed_at TIMESTAMPTZ,
    outcome VARCHAR(20),  -- 'WIN', 'LOSS', 'BREAKEVEN', 'EXPIRED'
    pnl DECIMAL(10,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. DCA Grids (For DCA Strategy Execution)
CREATE TABLE IF NOT EXISTS dca_grids (
    grid_id SERIAL PRIMARY KEY,
    setup_id INTEGER REFERENCES strategy_setups(setup_id),
    symbol VARCHAR(10) NOT NULL,
    grid_levels JSONB NOT NULL,  -- Array of {price, size, status}
    total_invested DECIMAL(10,2),
    average_price DECIMAL(20,8),
    status VARCHAR(20) NOT NULL,  -- 'PENDING', 'ACTIVE', 'COMPLETED', 'STOPPED'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    final_pnl DECIMAL(10,2)
);

-- 4. Market Regimes (BTC Market Conditions)
CREATE TABLE IF NOT EXISTS market_regimes (
    timestamp TIMESTAMPTZ PRIMARY KEY,
    btc_regime VARCHAR(20) NOT NULL,  -- 'BULL', 'BEAR', 'NEUTRAL', 'CRASH'
    btc_price DECIMAL(20,8) NOT NULL,
    btc_trend_strength DECIMAL(10,4),
    market_fear_greed INTEGER CHECK (market_fear_greed >= 0 AND market_fear_greed <= 100),  -- 0-100 scale
    total_market_cap DECIMAL(20,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_strategy_setups_symbol ON strategy_setups(symbol);
CREATE INDEX IF NOT EXISTS idx_strategy_setups_detected ON strategy_setups(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_strategy_setups_executed ON strategy_setups(is_executed);
CREATE INDEX IF NOT EXISTS idx_dca_grids_status ON dca_grids(status);
CREATE INDEX IF NOT EXISTS idx_market_regimes_timestamp ON market_regimes(timestamp DESC);

-- Add strategy_name column to ml_predictions if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='ml_predictions' AND column_name='strategy_name') THEN
        ALTER TABLE ml_predictions ADD COLUMN strategy_name VARCHAR(50);
    END IF;
END $$;

-- Add setup_id reference to ml_predictions if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='ml_predictions' AND column_name='setup_id') THEN
        ALTER TABLE ml_predictions ADD COLUMN setup_id INTEGER REFERENCES strategy_setups(setup_id);
    END IF;
END $$;

-- Add strategy_name to hummingbot_trades if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='hummingbot_trades' AND column_name='strategy_name') THEN
        ALTER TABLE hummingbot_trades ADD COLUMN strategy_name VARCHAR(50);
    END IF;
END $$;

-- Add setup_id reference to hummingbot_trades if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='hummingbot_trades' AND column_name='setup_id') THEN
        ALTER TABLE hummingbot_trades ADD COLUMN setup_id INTEGER REFERENCES strategy_setups(setup_id);
    END IF;
END $$;

-- Insert default strategy configurations
INSERT INTO strategy_configs (strategy_name, parameters, is_active) VALUES
('DCA', '{
    "price_drop_threshold": -5.0,
    "timeframe": "4h",
    "volume_filter": "above_average",
    "btc_regime_filter": ["BULL", "NEUTRAL"],
    "grid_levels": 5,
    "grid_spacing": 1.0,
    "base_size": 100,
    "take_profit": 10.0,
    "stop_loss": -8.0,
    "time_exit_hours": 72,
    "ml_confidence_threshold": 0.60
}'::jsonb, true),
('SWING', '{
    "breakout_threshold": 3.0,
    "volume_surge": 2.0,
    "momentum_confirmation": "rsi > 60",
    "trend_alignment": "uptrend_on_4h",
    "position_size": 200,
    "entry_type": "market",
    "max_slippage": 0.5,
    "take_profit": 15.0,
    "stop_loss": -5.0,
    "trailing_stop": 7.0,
    "time_exit_hours": 48,
    "ml_confidence_threshold": 0.65
}'::jsonb, true)
ON CONFLICT DO NOTHING;

-- Create a view for strategy performance
CREATE OR REPLACE VIEW strategy_performance AS
SELECT 
    s.strategy_name,
    COUNT(*) as total_setups,
    COUNT(CASE WHEN s.is_executed THEN 1 END) as executed_setups,
    COUNT(CASE WHEN s.outcome = 'WIN' THEN 1 END) as wins,
    COUNT(CASE WHEN s.outcome = 'LOSS' THEN 1 END) as losses,
    ROUND(COUNT(CASE WHEN s.outcome = 'WIN' THEN 1 END)::numeric / 
          NULLIF(COUNT(CASE WHEN s.outcome IN ('WIN', 'LOSS') THEN 1 END), 0) * 100, 2) as win_rate,
    ROUND(AVG(CASE WHEN s.outcome = 'WIN' THEN s.pnl END), 2) as avg_win,
    ROUND(AVG(CASE WHEN s.outcome = 'LOSS' THEN s.pnl END), 2) as avg_loss,
    ROUND(SUM(s.pnl), 2) as total_pnl
FROM strategy_setups s
GROUP BY s.strategy_name;

COMMENT ON TABLE strategy_configs IS 'Configuration parameters for each trading strategy';
COMMENT ON TABLE strategy_setups IS 'Detected trading opportunities for each strategy';
COMMENT ON TABLE dca_grids IS 'DCA grid orders and execution tracking';
COMMENT ON TABLE market_regimes IS 'Market regime classification for strategy filtering';


-- 002_strategy_tables_clean.sql
-- Migration: Add Strategy-First Tables
-- Date: 2025-08-16
-- Purpose: Support DCA and Swing trading strategies with ML optimization

-- 1. Strategy Configurations
CREATE TABLE IF NOT EXISTS strategy_configs (
    strategy_id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(50) NOT NULL,  -- 'DCA' or 'SWING'
    parameters JSONB NOT NULL,  -- Strategy-specific parameters
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Strategy Setups (Detected Opportunities)
CREATE TABLE IF NOT EXISTS strategy_setups (
    setup_id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(50) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL,
    setup_price DECIMAL(20,8) NOT NULL,
    setup_data JSONB,  -- Setup-specific data (support levels, resistance, etc.)
    ml_confidence DECIMAL(3,2),
    is_executed BOOLEAN DEFAULT FALSE,
    executed_at TIMESTAMPTZ,
    outcome VARCHAR(20),  -- 'WIN', 'LOSS', 'BREAKEVEN', 'EXPIRED'
    pnl DECIMAL(10,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. DCA Grids (For DCA Strategy Execution)
CREATE TABLE IF NOT EXISTS dca_grids (
    grid_id SERIAL PRIMARY KEY,
    setup_id INTEGER REFERENCES strategy_setups(setup_id),
    symbol VARCHAR(10) NOT NULL,
    grid_levels JSONB NOT NULL,  -- Array of {price, size, status}
    total_invested DECIMAL(10,2),
    average_price DECIMAL(20,8),
    status VARCHAR(20) NOT NULL,  -- 'PENDING', 'ACTIVE', 'COMPLETED', 'STOPPED'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    final_pnl DECIMAL(10,2)
);

-- 4. Market Regimes (BTC Market Conditions)
CREATE TABLE IF NOT EXISTS market_regimes (
    timestamp TIMESTAMPTZ PRIMARY KEY,
    btc_regime VARCHAR(20) NOT NULL,  -- 'BULL', 'BEAR', 'NEUTRAL', 'CRASH'
    btc_price DECIMAL(20,8) NOT NULL,
    btc_trend_strength DECIMAL(10,4),
    market_fear_greed INTEGER CHECK (market_fear_greed >= 0 AND market_fear_greed <= 100),  -- 0-100 scale
    total_market_cap DECIMAL(20,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_strategy_setups_symbol ON strategy_setups(symbol);
CREATE INDEX IF NOT EXISTS idx_strategy_setups_detected ON strategy_setups(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_strategy_setups_executed ON strategy_setups(is_executed);
CREATE INDEX IF NOT EXISTS idx_dca_grids_status ON dca_grids(status);
CREATE INDEX IF NOT EXISTS idx_market_regimes_timestamp ON market_regimes(timestamp DESC);

-- Add strategy_name column to ml_predictions if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='ml_predictions' AND column_name='strategy_name') THEN
        ALTER TABLE ml_predictions ADD COLUMN strategy_name VARCHAR(50);
    END IF;
END $$;

-- Add setup_id reference to ml_predictions if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='ml_predictions' AND column_name='setup_id') THEN
        ALTER TABLE ml_predictions ADD COLUMN setup_id INTEGER REFERENCES strategy_setups(setup_id);
    END IF;
END $$;

-- Add strategy_name to hummingbot_trades if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='hummingbot_trades' AND column_name='strategy_name') THEN
        ALTER TABLE hummingbot_trades ADD COLUMN strategy_name VARCHAR(50);
    END IF;
END $$;

-- Add setup_id reference to hummingbot_trades if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='hummingbot_trades' AND column_name='setup_id') THEN
        ALTER TABLE hummingbot_trades ADD COLUMN setup_id INTEGER REFERENCES strategy_setups(setup_id);
    END IF;
END $$;

-- Insert default strategy configurations
INSERT INTO strategy_configs (strategy_name, parameters, is_active) VALUES
('DCA', '{
    "price_drop_threshold": -5.0,
    "timeframe": "4h",
    "volume_filter": "above_average",
    "btc_regime_filter": ["BULL", "NEUTRAL"],
    "grid_levels": 5,
    "grid_spacing": 1.0,
    "base_size": 100,
    "take_profit": 10.0,
    "stop_loss": -8.0,
    "time_exit_hours": 72,
    "ml_confidence_threshold": 0.60
}'::jsonb, true),
('SWING', '{
    "breakout_threshold": 3.0,
    "volume_surge": 2.0,
    "momentum_confirmation": "rsi > 60",
    "trend_alignment": "uptrend_on_4h",
    "position_size": 200,
    "entry_type": "market",
    "max_slippage": 0.5,
    "take_profit": 15.0,
    "stop_loss": -5.0,
    "trailing_stop": 7.0,
    "time_exit_hours": 48,
    "ml_confidence_threshold": 0.65
}'::jsonb, true)
ON CONFLICT DO NOTHING;

-- Create a view for strategy performance
CREATE OR REPLACE VIEW strategy_performance AS
SELECT 
    s.strategy_name,
    COUNT(*) as total_setups,
    COUNT(CASE WHEN s.is_executed THEN 1 END) as executed_setups,
    COUNT(CASE WHEN s.outcome = 'WIN' THEN 1 END) as wins,
    COUNT(CASE WHEN s.outcome = 'LOSS' THEN 1 END) as losses,
    ROUND(COUNT(CASE WHEN s.outcome = 'WIN' THEN 1 END)::numeric / 
          NULLIF(COUNT(CASE WHEN s.outcome IN ('WIN', 'LOSS') THEN 1 END), 0) * 100, 2) as win_rate,
    ROUND(AVG(CASE WHEN s.outcome = 'WIN' THEN s.pnl END), 2) as avg_win,
    ROUND(AVG(CASE WHEN s.outcome = 'LOSS' THEN s.pnl END), 2) as avg_loss,
    ROUND(SUM(s.pnl), 2) as total_pnl
FROM strategy_setups s
GROUP BY s.strategy_name;

-- Add comments for documentation
COMMENT ON TABLE strategy_configs IS 'Configuration parameters for each trading strategy';
COMMENT ON TABLE strategy_setups IS 'Detected trading opportunities for each strategy';
COMMENT ON TABLE dca_grids IS 'DCA grid orders and execution tracking';
COMMENT ON TABLE market_regimes IS 'Market regime classification for strategy filtering';


-- 003_create_ohlc_table.sql
-- Create OHLC (Open, High, Low, Close) data table
-- This stores aggregated candlestick data from Polygon

CREATE TABLE IF NOT EXISTS ohlc_data (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    open DECIMAL(20,8) NOT NULL,
    high DECIMAL(20,8) NOT NULL,
    low DECIMAL(20,8) NOT NULL,
    close DECIMAL(20,8) NOT NULL,
    volume DECIMAL(20,4),
    num_trades INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Primary key on timestamp + symbol
    PRIMARY KEY (timestamp, symbol)
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_ohlc_symbol ON ohlc_data(symbol);
CREATE INDEX IF NOT EXISTS idx_ohlc_timestamp ON ohlc_data(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_ohlc_symbol_timestamp ON ohlc_data(symbol, timestamp DESC);

-- Add comment
COMMENT ON TABLE ohlc_data IS 'Hourly OHLC candlestick data for crypto symbols';
COMMENT ON COLUMN ohlc_data.open IS 'Opening price at start of period';
COMMENT ON COLUMN ohlc_data.high IS 'Highest price during period';
COMMENT ON COLUMN ohlc_data.low IS 'Lowest price during period';
COMMENT ON COLUMN ohlc_data.close IS 'Closing price at end of period';
COMMENT ON COLUMN ohlc_data.volume IS 'Total volume traded during period';
COMMENT ON COLUMN ohlc_data.num_trades IS 'Number of trades during period';


-- 003_create_unified_ohlc_table.sql
-- Create unified OHLC table for all timeframes
-- This stores all candlestick data: 1m, 15m, 1h, 1d
-- Designed for complete backtesting capability

-- Drop old table if exists (from previous attempt)
DROP TABLE IF EXISTS ohlc_data;

-- Create the unified OHLC table
CREATE TABLE ohlc_data (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    timeframe VARCHAR(10) NOT NULL, -- '1m', '15m', '1h', '1d'
    open DECIMAL(20,8) NOT NULL,
    high DECIMAL(20,8) NOT NULL,
    low DECIMAL(20,8) NOT NULL,
    close DECIMAL(20,8) NOT NULL,
    volume DECIMAL(20,4),
    vwap DECIMAL(20,8),  -- Volume-weighted average price
    trades INTEGER,      -- Number of trades in period
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Composite primary key prevents duplicates
    PRIMARY KEY (symbol, timeframe, timestamp)
);

-- Indexes for fast queries
CREATE INDEX idx_ohlc_symbol_tf_time ON ohlc_data(symbol, timeframe, timestamp DESC);
CREATE INDEX idx_ohlc_time ON ohlc_data(timestamp DESC);
CREATE INDEX idx_ohlc_symbol ON ohlc_data(symbol);
CREATE INDEX idx_ohlc_timeframe ON ohlc_data(timeframe);

-- Add comments for documentation
COMMENT ON TABLE ohlc_data IS 'Unified OHLC data for all timeframes - supports complete backtesting';
COMMENT ON COLUMN ohlc_data.timeframe IS 'Timeframe: 1m, 15m, 1h, or 1d';
COMMENT ON COLUMN ohlc_data.open IS 'Opening price at start of period';
COMMENT ON COLUMN ohlc_data.high IS 'Highest price during period';
COMMENT ON COLUMN ohlc_data.low IS 'Lowest price during period';
COMMENT ON COLUMN ohlc_data.close IS 'Closing price at end of period';
COMMENT ON COLUMN ohlc_data.volume IS 'Total volume traded during period';
COMMENT ON COLUMN ohlc_data.vwap IS 'Volume-weighted average price';
COMMENT ON COLUMN ohlc_data.trades IS 'Number of trades during period';

-- Create a view for easy access to latest data per symbol/timeframe
CREATE OR REPLACE VIEW latest_ohlc AS
SELECT DISTINCT ON (symbol, timeframe) 
    symbol,
    timeframe,
    timestamp,
    close as latest_price,
    volume as latest_volume
FROM ohlc_data
ORDER BY symbol, timeframe, timestamp DESC;

-- Create a function to check for data gaps
CREATE OR REPLACE FUNCTION check_ohlc_gaps(
    p_symbol VARCHAR,
    p_timeframe VARCHAR,
    p_start_date TIMESTAMPTZ,
    p_end_date TIMESTAMPTZ
) RETURNS TABLE(gap_start TIMESTAMPTZ, gap_end TIMESTAMPTZ, missing_bars INTEGER)
LANGUAGE plpgsql
AS $$
DECLARE
    interval_minutes INTEGER;
BEGIN
    -- Determine interval based on timeframe
    CASE p_timeframe
        WHEN '1m' THEN interval_minutes := 1;
        WHEN '15m' THEN interval_minutes := 15;
        WHEN '1h' THEN interval_minutes := 60;
        WHEN '1d' THEN interval_minutes := 1440;
        ELSE interval_minutes := 60; -- Default to hourly
    END CASE;
    
    -- Find gaps in the data
    RETURN QUERY
    WITH ordered_data AS (
        SELECT 
            timestamp,
            LEAD(timestamp) OVER (ORDER BY timestamp) as next_timestamp
        FROM ohlc_data
        WHERE symbol = p_symbol 
        AND timeframe = p_timeframe
        AND timestamp BETWEEN p_start_date AND p_end_date
    )
    SELECT 
        timestamp as gap_start,
        next_timestamp as gap_end,
        EXTRACT(EPOCH FROM (next_timestamp - timestamp))::INTEGER / (interval_minutes * 60) - 1 as missing_bars
    FROM ordered_data
    WHERE next_timestamp - timestamp > INTERVAL '1 minute' * interval_minutes
    ORDER BY timestamp;
END;
$$;


-- verify_strategy_tables.sql
-- Verification Query - Run this after creating tables

-- Check all new tables exist
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('strategy_configs', 'strategy_setups', 'dca_grids', 'market_regimes')
ORDER BY table_name;

-- Check strategy configurations were inserted
SELECT * FROM strategy_configs;

-- Check the performance view works
SELECT * FROM strategy_performance;


