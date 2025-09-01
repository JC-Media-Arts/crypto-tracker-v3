-- Migration: Create freqtrade_trades table for syncing trades from Freqtrade
-- Date: 2025-01-09
-- Purpose: Store Freqtrade trades for dashboard display and ML training

CREATE TABLE IF NOT EXISTS freqtrade_trades (
    id SERIAL PRIMARY KEY,
    trade_id INTEGER UNIQUE NOT NULL,
    pair VARCHAR(20) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    is_open BOOLEAN DEFAULT true,
    amount DECIMAL(20, 8),
    open_rate DECIMAL(20, 8),
    close_rate DECIMAL(20, 8),
    open_date TIMESTAMP WITH TIME ZONE,
    close_date TIMESTAMP WITH TIME ZONE,
    stake_amount DECIMAL(20, 8),
    fee_open DECIMAL(10, 8),
    fee_close DECIMAL(10, 8),
    realized_profit DECIMAL(20, 8),
    close_profit DECIMAL(10, 8),
    close_profit_pct DECIMAL(10, 4),
    strategy VARCHAR(50),
    timeframe VARCHAR(10),
    exit_reason VARCHAR(100),
    min_rate DECIMAL(20, 8),
    max_rate DECIMAL(20, 8),
    stop_loss_abs DECIMAL(20, 8),
    stop_loss_ratio DECIMAL(10, 8),
    initial_stop_loss_abs DECIMAL(20, 8),
    initial_stop_loss_ratio DECIMAL(10, 8),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX idx_freqtrade_trades_trade_id ON freqtrade_trades(trade_id);
CREATE INDEX idx_freqtrade_trades_pair ON freqtrade_trades(pair);
CREATE INDEX idx_freqtrade_trades_symbol ON freqtrade_trades(symbol);
CREATE INDEX idx_freqtrade_trades_is_open ON freqtrade_trades(is_open);
CREATE INDEX idx_freqtrade_trades_open_date ON freqtrade_trades(open_date);
CREATE INDEX idx_freqtrade_trades_close_date ON freqtrade_trades(close_date);
CREATE INDEX idx_freqtrade_trades_strategy ON freqtrade_trades(strategy);

-- Add update trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_freqtrade_trades_updated_at 
    BEFORE UPDATE ON freqtrade_trades
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions
GRANT ALL ON freqtrade_trades TO authenticated;
GRANT ALL ON freqtrade_trades TO service_role;
