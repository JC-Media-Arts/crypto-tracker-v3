-- Migration to optimize OHLC table performance with partitioning and better indexes
-- This migration improves query performance for large datasets

-- First, create the partitioned table structure
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

-- Create monthly partitions for the past 6 months and next 3 months
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

-- Create optimized indexes on the existing table (if not migrating data immediately)
-- Composite index for most common query pattern
CREATE INDEX IF NOT EXISTS idx_ohlc_composite
    ON ohlc_data(symbol, timeframe, timestamp DESC);

-- BRIN index for timestamp - very efficient for time-series data
CREATE INDEX IF NOT EXISTS idx_ohlc_timestamp_brin
    ON ohlc_data USING BRIN(timestamp);

-- Index for symbol-based queries
CREATE INDEX IF NOT EXISTS idx_ohlc_symbol_timestamp
    ON ohlc_data(symbol, timestamp DESC);

-- Index for timeframe-based analysis
CREATE INDEX IF NOT EXISTS idx_ohlc_timeframe_timestamp
    ON ohlc_data(timeframe, timestamp DESC);

-- Partial index for recent data (last 30 days) - most queries are for recent data
CREATE INDEX IF NOT EXISTS idx_ohlc_recent
    ON ohlc_data(symbol, timeframe, timestamp DESC)
    WHERE timestamp > NOW() - INTERVAL '30 days';

-- Create the same indexes on partitioned table
CREATE INDEX idx_ohlc_part_composite
    ON ohlc_data_partitioned(symbol, timeframe, timestamp DESC);

CREATE INDEX idx_ohlc_part_timestamp_brin
    ON ohlc_data_partitioned USING BRIN(timestamp);

CREATE INDEX idx_ohlc_part_symbol_timestamp
    ON ohlc_data_partitioned(symbol, timestamp DESC);

-- Add table statistics for better query planning
ALTER TABLE ohlc_data SET (autovacuum_analyze_scale_factor = 0.01);
ALTER TABLE ohlc_data SET (autovacuum_vacuum_scale_factor = 0.05);

-- Set statement timeout for the database (30 seconds)
-- Note: This needs to be run as a superuser or configured at the database level
-- ALTER DATABASE your_database_name SET statement_timeout = '30s';

-- Add comment for documentation
COMMENT ON TABLE ohlc_data_partitioned IS 'Partitioned OHLC data table for improved query performance on large datasets';

-- Create a function to automatically create new partitions
CREATE OR REPLACE FUNCTION create_monthly_partition()
RETURNS void AS $$
DECLARE
    start_date date;
    end_date date;
    partition_name text;
BEGIN
    -- Get the date for next month
    start_date := date_trunc('month', CURRENT_DATE + interval '1 month');
    end_date := start_date + interval '1 month';
    partition_name := 'ohlc_data_' || to_char(start_date, 'YYYY_MM');

    -- Check if partition already exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_class
        WHERE relname = partition_name
    ) THEN
        -- Create the partition
        EXECUTE format(
            'CREATE TABLE %I PARTITION OF ohlc_data_partitioned FOR VALUES FROM (%L) TO (%L)',
            partition_name,
            start_date,
            end_date
        );

        RAISE NOTICE 'Created partition %', partition_name;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Create a scheduled job to create partitions (requires pg_cron extension)
-- This would need to be set up separately if pg_cron is available:
-- SELECT cron.schedule('create-ohlc-partitions', '0 0 1 * *', 'SELECT create_monthly_partition();');

-- Migration script to move data from old table to partitioned table (optional)
-- This should be run during a maintenance window as it can be resource-intensive
/*
-- Step 1: Copy data in batches
INSERT INTO ohlc_data_partitioned
SELECT * FROM ohlc_data
WHERE timestamp >= '2024-07-01'
ON CONFLICT DO NOTHING;

-- Step 2: Rename tables
ALTER TABLE ohlc_data RENAME TO ohlc_data_old;
ALTER TABLE ohlc_data_partitioned RENAME TO ohlc_data;

-- Step 3: Drop old table after verification
-- DROP TABLE ohlc_data_old;
*/
