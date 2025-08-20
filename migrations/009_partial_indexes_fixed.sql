-- Fixed Partial Indexes for Immediate Relief
-- Using fixed dates instead of CURRENT_DATE to avoid IMMUTABLE error

-- Index 1: Recent data for real-time trading (data from 2025 onwards)
-- This captures recent and future data
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_recent_2025
ON ohlc_data(symbol, timeframe, timestamp DESC)
WHERE timestamp > '2025-01-01'::timestamptz;

-- Index 2: Last few months for ML features (from Nov 2024)
-- Covers ~3 months of recent data
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_recent_nov2024
ON ohlc_data(symbol, timestamp DESC)
WHERE timestamp > '2024-11-01'::timestamptz;

-- Index 3: Very recent data only (from Jan 15, 2025)
-- Smallest index, most likely to succeed
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_recent_jan2025
ON ohlc_data(symbol, timestamp DESC)
WHERE timestamp > '2025-01-15'::timestamptz;

-- Index 4: Specific timeframe optimization for 1-minute data
-- Only index 1m data from 2025
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_1m_2025
ON ohlc_data(symbol, timestamp DESC)
WHERE timeframe = '1m' AND timestamp > '2025-01-01'::timestamptz;

-- Index 5: 15-minute data from December 2024
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_15m_dec2024
ON ohlc_data(symbol, timestamp DESC)
WHERE timeframe = '15m' AND timestamp > '2024-12-01'::timestamptz;

-- Try the SMALLEST one first (Index 3) as it's most likely to succeed
-- Then try Index 1, then Index 2, etc.

-- After creating indexes, analyze the table
ANALYZE ohlc_data;
