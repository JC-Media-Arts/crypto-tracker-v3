-- Create Cache Tables for Dashboard Performance
-- Run this FIRST in Supabase SQL Editor

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

-- 2. Create unique constraint
ALTER TABLE strategy_status_cache
ADD CONSTRAINT unique_symbol_strategy UNIQUE (symbol, strategy_name);

-- 3. Create market summary cache table
CREATE TABLE IF NOT EXISTS market_summary_cache (
    id SERIAL PRIMARY KEY,
    condition VARCHAR(50),
    best_strategy VARCHAR(50),
    notes TEXT,
    calculated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tables created successfully!
-- Now run the indexes separately if needed
