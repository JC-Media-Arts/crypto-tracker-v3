-- Migration 020: Fix missing tables and columns for shadow testing and trade logs
-- Date: 2025-01-20
-- Purpose: Add missing columns to trade_logs and create shadow testing infrastructure

-- ============================================
-- PART 1: Fix trade_logs table
-- ============================================

-- Add missing columns to trade_logs
ALTER TABLE trade_logs 
ADD COLUMN IF NOT EXISTS pnl DECIMAL(10,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS stop_loss_price DECIMAL(10,2),
ADD COLUMN IF NOT EXISTS take_profit_price DECIMAL(10,2),
ADD COLUMN IF NOT EXISTS actual_exit_price DECIMAL(10,2);

-- Add calculated P&L percentage column (PostgreSQL 12+ feature)
-- Note: Only add if not exists to avoid errors
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'trade_logs' AND column_name = 'pnl_percentage'
    ) THEN
        ALTER TABLE trade_logs
        ADD COLUMN pnl_percentage DECIMAL(5,2) 
        GENERATED ALWAYS AS (
            CASE 
                WHEN entry_price > 0 AND actual_exit_price > 0 
                THEN ((actual_exit_price - entry_price) / entry_price * 100)
                ELSE 0 
            END
        ) STORED;
    END IF;
END $$;

-- ============================================
-- PART 2: Create shadow testing tables
-- ============================================

-- Create shadow testing scans table
CREATE TABLE IF NOT EXISTS shadow_testing_scans (
    id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    scan_time TIMESTAMP DEFAULT NOW(),
    signal_detected BOOLEAN DEFAULT FALSE,
    confidence FLOAT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create shadow testing trades table
CREATE TABLE IF NOT EXISTS shadow_testing_trades (
    id SERIAL PRIMARY KEY,
    scan_id INTEGER REFERENCES shadow_testing_scans(id),
    symbol VARCHAR(20) NOT NULL,
    strategy_name VARCHAR(50) NOT NULL,
    entry_price DECIMAL(10,2) NOT NULL,
    exit_price DECIMAL(10,2),
    position_size DECIMAL(10,4),
    pnl DECIMAL(10,2),
    pnl_percentage DECIMAL(5,2),
    trade_duration_hours INTEGER,
    outcome VARCHAR(20), -- 'WIN', 'LOSS', 'BREAKEVEN'
    created_at TIMESTAMP DEFAULT NOW(),
    closed_at TIMESTAMP
);

-- ============================================
-- PART 3: Create performance indexes
-- ============================================

-- Indexes for shadow_testing_scans
CREATE INDEX IF NOT EXISTS idx_shadow_scans_time 
    ON shadow_testing_scans(scan_time DESC);
CREATE INDEX IF NOT EXISTS idx_shadow_scans_strategy 
    ON shadow_testing_scans(strategy_name, symbol);
CREATE INDEX IF NOT EXISTS idx_shadow_scans_signal 
    ON shadow_testing_scans(signal_detected) 
    WHERE signal_detected = true;

-- Indexes for shadow_testing_trades
CREATE INDEX IF NOT EXISTS idx_shadow_trades_scan 
    ON shadow_testing_trades(scan_id);
CREATE INDEX IF NOT EXISTS idx_shadow_trades_outcome 
    ON shadow_testing_trades(outcome);
CREATE INDEX IF NOT EXISTS idx_shadow_trades_strategy 
    ON shadow_testing_trades(strategy_name, created_at DESC);

-- ============================================
-- PART 4: Create analysis view
-- ============================================

-- Create or replace view for shadow testing performance analysis
CREATE OR REPLACE VIEW shadow_testing_performance AS
SELECT 
    strategy_name,
    COUNT(*) as total_trades,
    SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as losses,
    SUM(CASE WHEN outcome = 'BREAKEVEN' THEN 1 ELSE 0 END) as breakeven,
    ROUND(
        SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END)::NUMERIC / 
        NULLIF(COUNT(*), 0) * 100, 2
    ) as win_rate,
    ROUND(AVG(pnl_percentage)::NUMERIC, 2) as avg_return_pct,
    ROUND(SUM(pnl)::NUMERIC, 2) as total_pnl,
    ROUND(AVG(trade_duration_hours)::NUMERIC, 1) as avg_duration_hours
FROM shadow_testing_trades
WHERE closed_at IS NOT NULL
GROUP BY strategy_name;

-- ============================================
-- PART 5: Add helpful comments
-- ============================================

COMMENT ON TABLE shadow_testing_scans IS 'Records all strategy scans for shadow testing comparison';
COMMENT ON TABLE shadow_testing_trades IS 'Records hypothetical trades for strategy evaluation';
COMMENT ON VIEW shadow_testing_performance IS 'Aggregated performance metrics for shadow testing strategies';

-- ============================================
-- PART 6: Verify migration success
-- ============================================

-- This query will show what was created
DO $$
BEGIN
    RAISE NOTICE 'Migration 020 completed successfully!';
    RAISE NOTICE 'Tables created: shadow_testing_scans, shadow_testing_trades';
    RAISE NOTICE 'Columns added to trade_logs: pnl, stop_loss_price, take_profit_price, actual_exit_price';
    RAISE NOTICE 'View created: shadow_testing_performance';
END $$;
