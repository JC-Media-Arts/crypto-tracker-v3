-- Create table for syncing Freqtrade trades
-- This allows ML training on Railway without direct SQLite access

CREATE TABLE IF NOT EXISTS freqtrade_trades (
    id SERIAL PRIMARY KEY,
    trade_id INTEGER UNIQUE NOT NULL,  -- Freqtrade's internal trade ID
    pair VARCHAR(20) NOT NULL,         -- e.g., 'BTC/USDT'
    symbol VARCHAR(10) NOT NULL,       -- e.g., 'BTC' (extracted from pair)
    is_open BOOLEAN DEFAULT true,
    amount DECIMAL(20, 8),
    open_rate DECIMAL(20, 8),
    close_rate DECIMAL(20, 8),
    open_date TIMESTAMP WITH TIME ZONE,
    close_date TIMESTAMP WITH TIME ZONE,
    close_profit DECIMAL(10, 6),       -- Profit percentage
    close_profit_abs DECIMAL(20, 8),   -- Absolute profit
    sell_reason VARCHAR(100),
    strategy VARCHAR(50),
    timeframe VARCHAR(10),
    fee_open DECIMAL(10, 6),
    fee_close DECIMAL(10, 6),
    stop_loss DECIMAL(20, 8),
    initial_stop_loss DECIMAL(20, 8),
    trailing_stop BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_freqtrade_trades_symbol ON freqtrade_trades(symbol);
CREATE INDEX idx_freqtrade_trades_is_open ON freqtrade_trades(is_open);
CREATE INDEX idx_freqtrade_trades_close_date ON freqtrade_trades(close_date);
CREATE INDEX idx_freqtrade_trades_strategy ON freqtrade_trades(strategy);

-- Add comment
COMMENT ON TABLE freqtrade_trades IS 'Synced trades from Freqtrade for ML training on Railway';
