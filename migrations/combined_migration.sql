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


