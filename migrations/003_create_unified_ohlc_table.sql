-- Create unified OHLC table for all timeframes
-- This stores all candlestick data: 1m, 15m, 1h, 1d
-- Designed for complete backtesting capability

-- Drop old table if exists (from previous attempt)
DROP TABLE IF EXISTS ohlc_data;

-- Create the unified OHLC table
CREATE TABLE ohlc_data (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    timeframe VARCHAR(10) NOT NULL, -- '1m', '15m', '1h', '1d'
    open DECIMAL(20,8) NOT NULL,
    high DECIMAL(20,8) NOT NULL,
    low DECIMAL(20,8) NOT NULL,
    close DECIMAL(20,8) NOT NULL,
    volume DECIMAL(20,4),
    vwap DECIMAL(20,8),  -- Volume-weighted average price
    trades INTEGER,      -- Number of trades in period
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Composite primary key prevents duplicates
    PRIMARY KEY (symbol, timeframe, timestamp)
);

-- Indexes for fast queries
CREATE INDEX idx_ohlc_symbol_tf_time ON ohlc_data(symbol, timeframe, timestamp DESC);
CREATE INDEX idx_ohlc_time ON ohlc_data(timestamp DESC);
CREATE INDEX idx_ohlc_symbol ON ohlc_data(symbol);
CREATE INDEX idx_ohlc_timeframe ON ohlc_data(timeframe);

-- Add comments for documentation
COMMENT ON TABLE ohlc_data IS 'Unified OHLC data for all timeframes - supports complete backtesting';
COMMENT ON COLUMN ohlc_data.timeframe IS 'Timeframe: 1m, 15m, 1h, or 1d';
COMMENT ON COLUMN ohlc_data.open IS 'Opening price at start of period';
COMMENT ON COLUMN ohlc_data.high IS 'Highest price during period';
COMMENT ON COLUMN ohlc_data.low IS 'Lowest price during period';
COMMENT ON COLUMN ohlc_data.close IS 'Closing price at end of period';
COMMENT ON COLUMN ohlc_data.volume IS 'Total volume traded during period';
COMMENT ON COLUMN ohlc_data.vwap IS 'Volume-weighted average price';
COMMENT ON COLUMN ohlc_data.trades IS 'Number of trades during period';

-- Create a view for easy access to latest data per symbol/timeframe
CREATE OR REPLACE VIEW latest_ohlc AS
SELECT DISTINCT ON (symbol, timeframe) 
    symbol,
    timeframe,
    timestamp,
    close as latest_price,
    volume as latest_volume
FROM ohlc_data
ORDER BY symbol, timeframe, timestamp DESC;

-- Create a function to check for data gaps
CREATE OR REPLACE FUNCTION check_ohlc_gaps(
    p_symbol VARCHAR,
    p_timeframe VARCHAR,
    p_start_date TIMESTAMPTZ,
    p_end_date TIMESTAMPTZ
) RETURNS TABLE(gap_start TIMESTAMPTZ, gap_end TIMESTAMPTZ, missing_bars INTEGER)
LANGUAGE plpgsql
AS $$
DECLARE
    interval_minutes INTEGER;
BEGIN
    -- Determine interval based on timeframe
    CASE p_timeframe
        WHEN '1m' THEN interval_minutes := 1;
        WHEN '15m' THEN interval_minutes := 15;
        WHEN '1h' THEN interval_minutes := 60;
        WHEN '1d' THEN interval_minutes := 1440;
        ELSE interval_minutes := 60; -- Default to hourly
    END CASE;
    
    -- Find gaps in the data
    RETURN QUERY
    WITH ordered_data AS (
        SELECT 
            timestamp,
            LEAD(timestamp) OVER (ORDER BY timestamp) as next_timestamp
        FROM ohlc_data
        WHERE symbol = p_symbol 
        AND timeframe = p_timeframe
        AND timestamp BETWEEN p_start_date AND p_end_date
    )
    SELECT 
        timestamp as gap_start,
        next_timestamp as gap_end,
        EXTRACT(EPOCH FROM (next_timestamp - timestamp))::INTEGER / (interval_minutes * 60) - 1 as missing_bars
    FROM ordered_data
    WHERE next_timestamp - timestamp > INTERVAL '1 minute' * interval_minutes
    ORDER BY timestamp;
END;
$$;
