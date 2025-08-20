-- Immediate Relief: Partial Indexes for Critical Queries
-- Run these one at a time in Supabase SQL Editor
-- These should succeed because they process <1% of your data

-- Index 1: Recent data for real-time trading (last 7 days)
-- This is the most important for active trading
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_recent_7d
ON ohlc_data(symbol, timeframe, timestamp DESC)
WHERE timestamp > CURRENT_DATE - INTERVAL '7 days';

-- Index 2: Last 30 days for ML features
-- Critical for feature calculation and model predictions
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_recent_30d
ON ohlc_data(symbol, timestamp DESC)
WHERE timestamp > CURRENT_DATE - INTERVAL '30 days';

-- Index 3: Specific timeframe optimization for 1-minute data
-- Most granular data, limited to 3 days to keep index small
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_1m_recent
ON ohlc_data(symbol, timestamp DESC)
WHERE timeframe = '1m' AND timestamp > CURRENT_DATE - INTERVAL '3 days';

-- Optional: Add index for 15m data (commonly used for signals)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_15m_recent
ON ohlc_data(symbol, timestamp DESC)
WHERE timeframe = '15m' AND timestamp > CURRENT_DATE - INTERVAL '14 days';

-- Analyze table to update statistics after index creation
ANALYZE ohlc_data;
