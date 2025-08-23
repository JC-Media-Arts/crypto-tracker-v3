-- Fix Dashboard Performance - WORKING VERSION
-- Run this entire script in Supabase SQL Editor

-- 1. Create strategy status cache table
CREATE TABLE IF NOT EXISTS strategy_status_cache (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    strategy_name VARCHAR(50) NOT NULL,
    readiness DECIMAL(5,2),
    current_price DECIMAL(20,8),
    details TEXT,
    status VARCHAR(50),
    calculated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Add unique constraint (if table already exists, this won't duplicate)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'unique_symbol_strategy'
    ) THEN
        ALTER TABLE strategy_status_cache
        ADD CONSTRAINT unique_symbol_strategy UNIQUE (symbol, strategy_name);
    END IF;
END $$;

-- 3. Create market summary cache table
CREATE TABLE IF NOT EXISTS market_summary_cache (
    id SERIAL PRIMARY KEY,
    condition VARCHAR(50),
    best_strategy VARCHAR(50),
    notes TEXT,
    calculated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Create indexes for cache tables
CREATE INDEX IF NOT EXISTS idx_strategy_cache_lookup
ON strategy_status_cache(strategy_name, readiness DESC);

CREATE INDEX IF NOT EXISTS idx_strategy_cache_symbol
ON strategy_status_cache(symbol, strategy_name);

-- 5. Create basic indexes on ohlc_data (without problematic WHERE clauses)
CREATE INDEX IF NOT EXISTS idx_ohlc_dashboard
ON ohlc_data(symbol, timeframe, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_ohlc_timeframe_15m
ON ohlc_data(symbol, timestamp DESC)
WHERE timeframe = '15m';

-- 6. Done! Tables and indexes created
SELECT 'Cache tables created successfully!' as status;
