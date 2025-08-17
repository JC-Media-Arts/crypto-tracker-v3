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
