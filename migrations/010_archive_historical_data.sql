-- Data Archival Process - Run During Maintenance Window
-- This script archives historical data to improve performance

-- Step 1: Create archive table if it doesn't exist
CREATE TABLE IF NOT EXISTS ohlc_data_archive (
    LIKE ohlc_data INCLUDING ALL
);

-- Step 2: Create view for seamless access to both tables
CREATE OR REPLACE VIEW ohlc_data_unified AS
SELECT * FROM ohlc_data WHERE timestamp >= '2024-01-01'::timestamptz
UNION ALL
SELECT * FROM ohlc_data_archive WHERE timestamp < '2024-01-01'::timestamptz;

-- Step 3: Archive data in monthly chunks to avoid timeout
-- This uses a loop to process one month at a time
DO $$
DECLARE
    start_date DATE := '2015-01-01';
    end_date DATE := '2015-02-01';
    rows_moved INTEGER;
    total_rows INTEGER := 0;
BEGIN
    -- Archive everything before 2024
    WHILE start_date < '2024-01-01'::date LOOP
        -- Insert into archive
        INSERT INTO ohlc_data_archive
        SELECT * FROM ohlc_data
        WHERE timestamp >= start_date::timestamptz
        AND timestamp < end_date::timestamptz
        ON CONFLICT DO NOTHING;

        GET DIAGNOSTICS rows_moved = ROW_COUNT;
        total_rows := total_rows + rows_moved;

        -- Delete from main table
        DELETE FROM ohlc_data
        WHERE timestamp >= start_date::timestamptz
        AND timestamp < end_date::timestamptz;

        -- Log progress
        RAISE NOTICE 'Archived % rows for %', rows_moved, to_char(start_date, 'YYYY-MM');

        -- Move to next month
        start_date := end_date;
        end_date := end_date + INTERVAL '1 month';

        -- Brief pause to avoid overload
        PERFORM pg_sleep(0.5);
    END LOOP;

    RAISE NOTICE 'Total rows archived: %', total_rows;
END $$;

-- Step 4: Create indexes on archive table for historical queries
CREATE INDEX IF NOT EXISTS idx_archive_symbol_time
ON ohlc_data_archive(symbol, timeframe, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_archive_timestamp
ON ohlc_data_archive USING BRIN(timestamp);

-- Step 5: Vacuum and analyze both tables
VACUUM ANALYZE ohlc_data;
VACUUM ANALYZE ohlc_data_archive;

-- Step 6: Create indexes on the now-smaller main table
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_symbol_time
ON ohlc_data(symbol, timeframe, timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlc_timestamp
ON ohlc_data USING BRIN(timestamp);

-- Step 7: Update table statistics
ANALYZE ohlc_data;
ANALYZE ohlc_data_archive;
