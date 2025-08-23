-- Fix materialized view indexes for concurrent refresh
-- Run this in Supabase SQL Editor

-- First, create unique indexes on the materialized views
-- These are required for CONCURRENTLY refresh to work

-- For ohlc_today
CREATE UNIQUE INDEX IF NOT EXISTS idx_ohlc_today_unique 
ON ohlc_today (symbol, timeframe, timestamp);

-- For ohlc_recent  
CREATE UNIQUE INDEX IF NOT EXISTS idx_ohlc_recent_unique
ON ohlc_recent (symbol, timeframe, timestamp);

-- Now refresh the views (non-concurrent first time)
REFRESH MATERIALIZED VIEW ohlc_today;
REFRESH MATERIALIZED VIEW ohlc_recent;

-- Verify the refresh worked
SELECT 
    'ohlc_today' as view_name,
    COUNT(*) as row_count,
    MAX(timestamp) as latest_data,
    EXTRACT(EPOCH FROM (NOW() - MAX(timestamp)))/60 as minutes_old
FROM ohlc_today
UNION ALL
SELECT 
    'ohlc_recent' as view_name,
    COUNT(*) as row_count,
    MAX(timestamp) as latest_data,
    EXTRACT(EPOCH FROM (NOW() - MAX(timestamp)))/60 as minutes_old
FROM ohlc_recent;
