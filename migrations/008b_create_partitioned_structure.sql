-- Create partitioned table structure for future use
-- This creates empty tables, so it should run quickly
-- Run this AFTER the indexes are created

-- Create the partitioned table structure (empty, no data)
CREATE TABLE IF NOT EXISTS ohlc_data_partitioned (
    id BIGSERIAL,
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    open DECIMAL(20,8) NOT NULL,
    high DECIMAL(20,8) NOT NULL,
    low DECIMAL(20,8) NOT NULL,
    close DECIMAL(20,8) NOT NULL,
    volume DECIMAL(30,8),
    trades INTEGER,
    vwap DECIMAL(20,8),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Create monthly partitions (these are empty tables, very fast to create)
CREATE TABLE IF NOT EXISTS ohlc_data_2024_07 PARTITION OF ohlc_data_partitioned
    FOR VALUES FROM ('2024-07-01 00:00:00+00') TO ('2024-08-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS ohlc_data_2024_08 PARTITION OF ohlc_data_partitioned
    FOR VALUES FROM ('2024-08-01 00:00:00+00') TO ('2024-09-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS ohlc_data_2024_09 PARTITION OF ohlc_data_partitioned
    FOR VALUES FROM ('2024-09-01 00:00:00+00') TO ('2024-10-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS ohlc_data_2024_10 PARTITION OF ohlc_data_partitioned
    FOR VALUES FROM ('2024-10-01 00:00:00+00') TO ('2024-11-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS ohlc_data_2024_11 PARTITION OF ohlc_data_partitioned
    FOR VALUES FROM ('2024-11-01 00:00:00+00') TO ('2024-12-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS ohlc_data_2024_12 PARTITION OF ohlc_data_partitioned
    FOR VALUES FROM ('2024-12-01 00:00:00+00') TO ('2025-01-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS ohlc_data_2025_01 PARTITION OF ohlc_data_partitioned
    FOR VALUES FROM ('2025-01-01 00:00:00+00') TO ('2025-02-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS ohlc_data_2025_02 PARTITION OF ohlc_data_partitioned
    FOR VALUES FROM ('2025-02-01 00:00:00+00') TO ('2025-03-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS ohlc_data_2025_03 PARTITION OF ohlc_data_partitioned
    FOR VALUES FROM ('2025-03-01 00:00:00+00') TO ('2025-04-01 00:00:00+00');
