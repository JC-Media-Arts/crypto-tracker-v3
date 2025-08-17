# Create OHLC Data Table

## Instructions
1. Go to your Supabase dashboard
2. Navigate to SQL Editor
3. Copy and paste the SQL below
4. Click "Run"

## SQL to Execute

```sql
-- Create OHLC (Open, High, Low, Close) data table
-- This stores aggregated candlestick data from Polygon

CREATE TABLE IF NOT EXISTS ohlc_data (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    open DECIMAL(20,8) NOT NULL,
    high DECIMAL(20,8) NOT NULL,
    low DECIMAL(20,8) NOT NULL,
    close DECIMAL(20,8) NOT NULL,
    volume DECIMAL(20,4),
    num_trades INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Primary key on timestamp + symbol
    PRIMARY KEY (timestamp, symbol)
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_ohlc_symbol ON ohlc_data(symbol);
CREATE INDEX IF NOT EXISTS idx_ohlc_timestamp ON ohlc_data(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_ohlc_symbol_timestamp ON ohlc_data(symbol, timestamp DESC);

-- Add comment
COMMENT ON TABLE ohlc_data IS 'Hourly OHLC candlestick data for crypto symbols';
COMMENT ON COLUMN ohlc_data.open IS 'Opening price at start of period';
COMMENT ON COLUMN ohlc_data.high IS 'Highest price during period';
COMMENT ON COLUMN ohlc_data.low IS 'Lowest price during period';
COMMENT ON COLUMN ohlc_data.close IS 'Closing price at end of period';
COMMENT ON COLUMN ohlc_data.volume IS 'Total volume traded during period';
COMMENT ON COLUMN ohlc_data.num_trades IS 'Number of trades during period';
```

## Verification Query

After creating the table, run this to verify:

```sql
-- Check if table was created
SELECT 
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'ohlc_data'
ORDER BY ordinal_position;
```
