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
