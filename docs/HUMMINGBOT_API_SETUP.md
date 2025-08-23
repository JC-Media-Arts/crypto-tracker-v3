# Hummingbot API Setup Guide

This guide explains how to set up and connect to the official Hummingbot API for Phase 1 Recovery.

## Prerequisites

1. Docker installed and running
2. Hummingbot API repository cloned
3. Exchange API credentials (for paper trading or live trading)

## Step 1: Install Hummingbot API

Based on the [official documentation](https://hummingbot.org/hummingbot-api/):

```bash
# Clone the Hummingbot API repository
git clone https://github.com/hummingbot/hummingbot-api.git
cd hummingbot-api

# Set up with Docker Compose
docker-compose up -d
```

## Step 2: Configure Authentication

The API uses HTTP Basic Authentication. Configure during setup:

```bash
# Default credentials (change these!)
HUMMINGBOT_USERNAME=admin
HUMMINGBOT_PASSWORD=admin
```

## Step 3: Add Exchange Accounts

Use the API to add your exchange credentials:

```python
from hummingbot_api_client import HummingbotAPIClient

client = HummingbotAPIClient(
    base_url="http://localhost:8000",
    username="admin",
    password="admin"
)

# Add exchange account
await client.create_account({
    "name": "binance_paper",
    "connector": "binance_paper_trade",
    "api_key": "your-api-key",
    "api_secret": "your-api-secret"
})
```

## Step 4: Environment Variables

Set these environment variables for our simplified trading system:

```bash
# Hummingbot API Connection
export HUMMINGBOT_HOST=localhost
export HUMMINGBOT_PORT=8000
export HUMMINGBOT_USERNAME=admin
export HUMMINGBOT_PASSWORD=admin
export HUMMINGBOT_CONNECTOR=binance_paper_trade

# Recovery Mode Settings
export ML_ENABLED=false
export SHADOW_TESTING_ENABLED=false
export USE_SIMPLE_RULES=true
```

## Step 5: Test Connection

Run our test script to verify the connection:

```bash
python3 scripts/test_hummingbot_connection.py
```

## Step 6: Run Simplified Trading

Start the simplified trading system:

```bash
python3 scripts/run_simplified_trading.py
```

## Available API Endpoints

The Hummingbot API provides these key endpoints:

### Trading Operations
- `POST /trading/orders` - Place new order
- `GET /trading/orders` - List active orders
- `DELETE /trading/orders/{id}` - Cancel order
- `GET /trading/positions` - Get open positions

### Portfolio Management
- `GET /portfolio/balances` - Get aggregated balances
- `GET /portfolio/performance` - Get performance metrics

### Market Data
- `GET /market-data/ticker/{pair}` - Get current ticker
- `GET /market-data/orderbook/{pair}` - Get order book

### Bot Orchestration (Optional)
- `POST /bot-orchestration/deploy` - Deploy new bot
- `POST /bot-orchestration/bots/{id}/start` - Start bot
- `POST /bot-orchestration/bots/{id}/stop` - Stop bot

## Trading Flow

1. **Signal Detection**: Our simplified rules detect opportunities
2. **Order Creation**: Send order to Hummingbot API
3. **Position Tracking**: Monitor positions via API
4. **Exit Management**: Close positions based on rules

## Troubleshooting

### Connection Failed
- Check if Docker containers are running: `docker ps`
- Verify port 8000 is accessible
- Check credentials are correct

### No Accounts Found
- Add exchange accounts via API
- Verify API keys are valid

### Orders Not Executing
- Check exchange connectivity
- Verify trading pair format (e.g., BTC-USDT)
- Ensure sufficient balance

## Architecture

```
Simplified Trading System
         ↓
    Signals Generated
         ↓
  Hummingbot API Client
         ↓
   Hummingbot API Server
         ↓
    Exchange Connectors
         ↓
   Binance/OKX/Kraken
```

## Next Steps

1. Configure paper trading account
2. Run simplified system in simulation mode
3. Monitor for 10+ successful signals
4. Enable live execution
5. Track performance metrics

## Resources

- [Official Hummingbot API Docs](https://hummingbot.org/hummingbot-api/)
- [API Client Library](https://github.com/hummingbot/hummingbot-api-client)
- [Hummingbot Dashboard](https://github.com/hummingbot/dashboard)
