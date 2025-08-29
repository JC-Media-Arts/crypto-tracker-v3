# Freqtrade Integration for Crypto Tracker V3

## Overview

This is the Freqtrade integration for the crypto-tracker-v3 platform. It replaces SimplePaperTraderV2 with a battle-tested open-source trading engine, reducing code maintenance by 85% (from 3,500 lines to 500 lines).

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│              CUSTOM DASHBOARD (Railway)                   │
│  • Trade Performance View (reads Freqtrade DB)           │
│  • ML/Shadow Recommendations Display                     │
│  • Admin Panel (Full Strategy Control)                   │
└────────────┬─────────────────────────┬───────────────────┘
             │                         │
             ▼                         ▼
┌──────────────────────┐   ┌──────────────────────────────┐
│   CONFIG BRIDGE      │   │   ML/SHADOW RESEARCH LAYER   │
│  • Sync Admin → FT   │   │  • Scan Logger (from FT)     │
│  • Parameter Updates │   │  • Shadow Testing (8 vars)   │
│  • Risk Management   │   │  • ML Training Pipeline      │
└──────────┬───────────┘   │  • Recommendations Engine    │
           │                └──────────┬───────────────────┘
           ▼                           │
┌──────────────────────────────────────▼───────────────────┐
│                    FREQTRADE CORE                        │
│  • Strategy Execution (CHANNEL, DCA, SWING)              │
│  • Paper & Live Trading on Kraken                        │
│  • Position Management                                   │
│  • Order Execution                                       │
│  • Built-in Risk Management                              │
│  • Database (SQLite/PostgreSQL)                          │
└───────────────────────────────────────────────────────────┘
```

## Components

### 1. **ChannelStrategyV1** (`user_data/strategies/ChannelStrategyV1.py`)
- CHANNEL strategy ported from SimplePaperTraderV2
- Enters when price is in lower 15% of Bollinger Band channel
- Uses market cap tiers for position sizing and stop loss
- Logs all scan decisions for ML training

### 2. **ConfigBridge** (`user_data/config_bridge.py`)
- Syncs unified configuration to Freqtrade
- Reads from `configs/paper_trading_config_unified.json`
- Updates strategy parameters in real-time
- Maintains compatibility with admin panel

### 3. **ScanLogger** (`user_data/scan_logger.py`)
- Captures all Freqtrade trading decisions
- Writes to `scan_history` table for ML training
- Implements efficient batching (500 records/5 min)
- Provides statistics and analysis

### 4. **SupabaseDataProvider** (`user_data/data/supabase_dataprovider.py`)
- Connects Freqtrade to existing Polygon data in Supabase
- Fetches OHLC data from `ohlc_data` table
- Provides market cap information
- No need to download exchange data

## Setup Instructions

### 1. Environment Setup

```bash
# Navigate to freqtrade directory
cd crypto-tracker-v3/freqtrade

# Activate virtual environment
source venv/bin/activate

# Copy environment template
cp env.example .env

# Edit .env and add your Supabase credentials
# SUPABASE_URL=https://your-project.supabase.co
# SUPABASE_KEY=your-anon-key
```

### 2. Test Setup

```bash
# Run the test script
python test_setup.py
```

This will verify:
- All modules can be imported
- Environment variables are set
- Configuration files are valid
- Database connection works

### 3. Run Freqtrade

#### Dry Run Mode (Paper Trading)

```bash
# Set environment variables
export SUPABASE_URL=your_url
export SUPABASE_KEY=your_key

# Run Freqtrade in dry-run mode
freqtrade trade --config config/config.json --strategy ChannelStrategyV1
```

#### Backtesting

```bash
# Run backtest with historical data
freqtrade backtesting --config config/config.json --strategy ChannelStrategyV1 --timerange 20240101-20241231
```

#### Web UI

```bash
# Start the web UI
freqtrade webserver --config config/config.json
# Access at http://localhost:8080
```

## Configuration

### Unified Config Integration

The system reads from `configs/paper_trading_config_unified.json` and automatically syncs:
- Strategy thresholds (entry/exit conditions)
- Market cap tiers (stop loss, take profit, position sizing)
- Risk parameters (max positions, timeouts)
- Symbol whitelist

### Freqtrade Config

Main configuration in `config/config.json`:
- Exchange: Kraken (dry-run mode by default)
- Strategy: ChannelStrategyV1
- API Server: Enabled on port 8080
- Max positions: 10
- Timeframe: 1 hour

## Database Tables

### Required Tables

1. **ohlc_data** - Historical price data
   - symbol, timestamp, open, high, low, close, volume

2. **market_data** - Market cap information
   - symbol, timestamp, market_cap

3. **scan_history** - ML training data (created by ScanLogger)
   - timestamp, symbol, strategy, decision, features, metadata

## Next Steps

### Day 3-4: Dashboard Integration
- Modify dashboard to read from Freqtrade database
- Add Freqtrade trade display

### Day 5-6: ML/Shadow Integration
- Connect ML analyzer to scan_history
- Implement shadow testing variations

### Day 7-9: Production Deployment
- Create Docker container
- Deploy to Railway
- Set up monitoring

## Troubleshooting

### Import Errors
- Ensure virtual environment is activated
- Check that all dependencies are installed: `pip install -r requirements.txt`

### Database Connection
- Verify SUPABASE_URL and SUPABASE_KEY are set
- Check network connectivity to Supabase

### Strategy Not Found
- Ensure strategy file is in `user_data/strategies/`
- Check strategy class name matches config

## Migration from SimplePaperTraderV2

### What Changes
- Trading execution: SimplePaperTraderV2 → Freqtrade
- Database: paper_trades → Freqtrade database
- Configuration: Direct updates → ConfigBridge

### What Stays the Same
- Admin panel interface
- ML training pipeline
- Shadow testing system
- Unified configuration structure
- Railway deployment

## Resources

- [Freqtrade Documentation](https://www.freqtrade.io/)
- [Strategy Development](https://www.freqtrade.io/en/stable/strategy-customization/)
- [Configuration](https://www.freqtrade.io/en/stable/configuration/)
- [REST API](https://www.freqtrade.io/en/stable/rest-api/)
