-- Create Cache Tables ONLY (no indexes on ohlc_data)
-- This should run quickly without timeout

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

-- 2. Create market summary cache table
CREATE TABLE IF NOT EXISTS market_summary_cache (
    id SERIAL PRIMARY KEY,
    condition VARCHAR(50),
    best_strategy VARCHAR(50),
    notes TEXT,
    calculated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Add indexes ONLY to the new cache tables (these are empty so it's fast)
CREATE INDEX IF NOT EXISTS idx_strategy_cache_lookup
ON strategy_status_cache(strategy_name, readiness DESC);

CREATE INDEX IF NOT EXISTS idx_strategy_cache_symbol
ON strategy_status_cache(symbol, strategy_name);

-- 4. Add unique constraint
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

-- Done! Cache tables created
SELECT 'Cache tables created successfully!' as status;
