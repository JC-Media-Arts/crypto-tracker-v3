# Crypto ML Trading System - Master Architecture & Implementation Plan
## crypto-tracker-v3

*Phase 1 MVP - Proving ML Can Predict Crypto Movements*
*Created: January 2025*
*Location: Los Angeles, CA*

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Phase 1 Architecture](#phase-1-architecture)
3. [Data Sources](#data-sources)
4. [Database Schema](#database-schema)
5. [ML Pipeline](#ml-pipeline)
6. [Trading Logic](#trading-logic)
7. [Paper Trading System](#paper-trading-system)
8. [Risk Management](#risk-management)
9. [Slack Integration](#slack-integration)
10. [Data Health Monitoring](#data-health-monitoring)
11. [Project Structure](#project-structure)
12. [Implementation Plan](#implementation-plan)
13. [Environment Configuration](#environment-configuration)
14. [Quick Start Guide](#quick-start-guide)
15. [Success Metrics](#success-metrics)
16. [Phase 2 Preview](#phase-2-preview)

---

## System Overview

A streamlined crypto trading system designed to prove whether machine learning can successfully predict short-term price movements. Phase 1 focuses on validating the core ML hypothesis with minimal complexity.

**Core Question:** Can ML predict crypto price direction better than random (>55% accuracy)?

**Timeline:** 30-60 days to prove/disprove

**Tech Stack:**
- **Data:** Polygon.io WebSocket ($49/month)
- **Database:** Supabase (PostgreSQL)
- **ML:** Python + XGBoost
- **Interface:** Slack
- **Execution:** Kraken API
- **Development:** Cursor + GitHub

---

## Phase 1 Architecture

### Data Flow
```
Polygon WebSocket → Real-time Prices → Feature Calculation → ML Model
                           ↓                                    ↓
                      Supabase Storage                   Predictions
                                                              ↓
                                                        Paper Trading
                                                              ↓
                                                     Performance Tracking
                                                              ↓
                                                        Slack Alerts
```

---

## Data Sources

### Primary Data (Polygon.io - $49/month)
- **Product:** Currencies Starter Plan
- **Features:**
  - Real-time WebSocket streaming
  - Second-level aggregates
  - 10+ years historical data
  - Unlimited API calls
  - All crypto tickers

### Exchange Data
- **Kraken API** (Free)
  - Order validation
  - Paper trading validation
  - Order book depth (Phase 2)

### Supported Coins (100 Total)

#### Tier 1: Core (20 coins)
BTC, ETH, SOL, BNB, XRP, ADA, AVAX, DOGE, DOT, POL, LINK, TON, SHIB, TRX, UNI, ATOM, BCH, APT, NEAR, ICP

#### Tier 2: DeFi/Layer 2 (20 coins)
ARB, OP, AAVE, CRV, MKR, LDO, SUSHI, COMP, SNX, BAL, INJ, SEI, PENDLE, BLUR, ENS, GRT, RENDER, FET, RPL, SAND

#### Tier 3: Trending/Memecoins (20 coins)
PEPE, WIF, BONK, FLOKI, MEME, POPCAT, MEW, TURBO, NEIRO, PNUT, GOAT, ACT, TRUMP, FARTCOIN, MOG, PONKE, TREMP, BRETT, GIGA, HIPPO

#### Tier 4: Solid Mid-Caps (40 coins)
FIL, RUNE, IMX, FLOW, MANA, AXS, CHZ, GALA, LRC, OCEAN, QNT, ALGO, XLM, XMR, ZEC, DASH, HBAR, VET, THETA, EOS, KSM, STX, KAS, TIA, JTO, JUP, PYTH, DYM, STRK, ALT, PORTAL, BEAM, BLUR, MASK, API3, ANKR, CTSI, YFI, AUDIO, ENJ

---

## Database Schema

### Minimal Phase 1 Tables (Supabase)

```sql
-- 1. Price data (partitioned by month)
CREATE TABLE price_data (
    timestamp TIMESTAMPTZ,
    symbol VARCHAR(10),
    price DECIMAL(20,8),
    volume DECIMAL(20,2),
    PRIMARY KEY (symbol, timestamp)
);

CREATE INDEX idx_symbol_time ON price_data(symbol, timestamp DESC);

-- 2. ML Features (pre-calculated hourly)
CREATE TABLE ml_features (
    timestamp TIMESTAMPTZ,
    symbol VARCHAR(10),
    price_change_5m DECIMAL(10,4),
    price_change_1h DECIMAL(10,4),
    volume_ratio DECIMAL(10,4),
    rsi_14 DECIMAL(10,2),
    distance_from_support DECIMAL(10,4),
    PRIMARY KEY (symbol, timestamp)
);

-- 3. ML Predictions
CREATE TABLE ml_predictions (
    prediction_id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    symbol VARCHAR(10),
    prediction VARCHAR(10), -- 'UP' or 'DOWN'
    confidence DECIMAL(3,2),
    actual_move DECIMAL(10,4), -- Filled in later
    correct BOOLEAN
);

-- 4. Paper Trades
CREATE TABLE paper_trades (
    trade_id SERIAL PRIMARY KEY,
    symbol VARCHAR(10),
    entry_time TIMESTAMPTZ,
    entry_price DECIMAL(20,8),
    exit_time TIMESTAMPTZ,
    exit_price DECIMAL(20,8),
    exit_reason VARCHAR(20), -- 'stop_loss', 'take_profit', 'time_exit'
    pnl DECIMAL(10,2),
    ml_confidence DECIMAL(3,2),
    kraken_validated BOOLEAN DEFAULT FALSE
);

-- 5. Daily Performance
CREATE TABLE daily_performance (
    date DATE PRIMARY KEY,
    trades_count INTEGER,
    wins INTEGER,
    losses INTEGER,
    net_pnl DECIMAL(10,2),
    ml_accuracy DECIMAL(5,2)
);

-- 6. Health Metrics
CREATE TABLE health_metrics (
    timestamp TIMESTAMPTZ PRIMARY KEY,
    metric_name VARCHAR(50),
    status VARCHAR(20),
    value DECIMAL(10,2),
    alert_sent BOOLEAN DEFAULT FALSE
);
```

---

## ML Pipeline

### Phase 1 Simple Configuration

```python
ML_CONFIG = {
    'model_type': 'XGBoost',
    'prediction_target': 'price_direction_2h',  # UP or DOWN in 2 hours
    'features': [
        'returns_5m',
        'returns_1h',
        'rsi_14',
        'distance_from_sma20',
        'volume_ratio',
        'support_distance'
    ],
    'training': {
        'frequency': 'nightly_2am',
        'data_window': 'last_6_months',
        'validation_split': 0.2,
        'test_split': 0.2
    },
    'thresholds': {
        'minimum_confidence': 0.60,
        'minimum_accuracy': 0.55,
        'minimum_trades_backtest': 100
    }
}
```

### Model Performance Tracking

```python
MODEL_METRICS = {
    'accuracy': 'Track daily',
    'confidence_correlation': 'Higher confidence should = higher accuracy',
    'feature_importance': 'Track which features matter',
    'drift_detection': 'Alert if accuracy drops below 50%'
}
```

---

## Trading Logic

### Simple Phase 1 Rules

```python
TRADING_RULES = {
    'entry_conditions': {
        'ml_confidence_minimum': 0.60,
        'max_open_positions': 5,
        'max_positions_per_coin': 1,
        'position_size': 100,  # $100 fixed
        'no_new_trades_if_daily_loss': -10.0  # Stop at -10% day
    },
    
    'exit_conditions': {
        'stop_loss': -5.0,  # -5% fixed
        'take_profit': 10.0,  # +10% fixed  
        'time_exit': 24,  # Exit after 24 hours
        'priority': 'stop_loss > take_profit > time_exit'
    },
    
    'risk_limits': {
        'max_daily_loss': -10.0,  # Percent
        'max_open_risk': 500,  # $500 total (5 x $100)
    }
}
```

---

## Paper Trading System

### Validation Modes

```python
PAPER_TRADING_MODES = {
    'development': {
        'kraken_validation': 0.0,  # No validation
        'purpose': 'Fast iteration',
        'slippage_simulation': 0.002  # 0.2%
    },
    'testing': {
        'kraken_validation': 0.10,  # Validate 10% of trades
        'purpose': 'Balance speed and realism'
    },
    'production': {
        'kraken_validation': 1.0,  # Validate all trades
        'purpose': 'Pre-live verification'
    }
}
```

### Kraken Validation

```python
def validate_with_kraken(symbol, side, amount):
    """Validate order would execute on Kraken"""
    result = kraken_api.add_order(
        pair=symbol,
        type=side,
        ordertype='market',
        volume=amount,
        validate=True  # Don't actually execute
    )
    return result['error'] == []
```

---

## Risk Management

### Phase 1 Simple Risk Rules

```python
RISK_MANAGEMENT = {
    'position_sizing': {
        'method': 'fixed',
        'amount': 100,  # $100 per trade
        'adjust_for_confidence': False  # Keep it simple
    },
    
    'portfolio_limits': {
        'max_positions': 5,
        'max_exposure': 500,  # $500 total
        'stop_if_down': -50,  # Stop if -$50 for day
    },
    
    'emergency_stops': {
        'ml_accuracy_below': 0.45,  # Stop if worse than random
        'consecutive_losses': 5,  # Stop after 5 losses
        'system_error': 'Stop all trading on critical error'
    }
}
```

---

## Slack Integration

### Channel Configuration

```python
SLACK_CHANNELS = {
    '#ml-signals': 'Real-time predictions and trades',
    '#daily-reports': '7 AM and 7 PM summaries',  
    '#system-alerts': 'Critical issues only'
}
```

### Notification Templates

```python
NOTIFICATIONS = {
    'trade_opened': """
        💰 Trade Opened
        Coin: {symbol}
        Entry: ${price:.2f}
        Confidence: {confidence:.0f}%
        Stop: ${stop_loss:.2f} (-5%)
        Target: ${take_profit:.2f} (+10%)
    """,
    
    'trade_closed': """
        {emoji} Trade Closed
        Coin: {symbol}
        P&L: ${pnl:.2f} ({pnl_pct:+.1f}%)
        Reason: {exit_reason}
        Duration: {hours}h {minutes}m
    """,
    
    'big_events': {
        'big_win': '@channel Big WIN! {symbol} +${profit:.2f}',
        'big_loss': '@channel Loss Alert: {symbol} -${loss:.2f}',
        'daily_goal': '@channel Daily goal hit! +${total:.2f}'
    }
}
```

### Report Schedule

```python
REPORTS = {
    'morning': {
        'time': '07:00 America/Los_Angeles',
        'content': 'Last 12 hours summary'
    },
    'evening': {
        'time': '19:00 America/Los_Angeles',
        'content': 'Day trading summary'
    },
    'weekly': {
        'time': 'Sunday 19:00 America/Los_Angeles',
        'content': 'Weekly performance analysis'
    }
}
```

### Slack Commands

- `/ml-status` - Check model status
- `/performance` - Current P&L
- `/positions` - Open positions
- `/pause` - Pause trading
- `/resume` - Resume trading

---

## Data Health Monitoring

### Simple Phase 1 Checks

```python
HEALTH_MONITORING = {
    'data_flow': {
        'check_frequency': 'every_5_min',
        'alert_if': 'no_data_for_10_min',
        'action': 'Slack alert @channel'
    },
    
    'price_sanity': {
        'check_frequency': 'every_1_min',
        'alert_if': 'price_change > 50% in 1 min',
        'action': 'Flag as bad data'
    },
    
    'ml_health': {
        'check_frequency': 'every_30_min',
        'alert_if': 'no_predictions_for_30_min',
        'action': 'Restart ML service'
    }
}
```

---

## Project Structure

```
crypto-tracker-v3/
├── .github/workflows/          # GitHub Actions
├── src/
│   ├── config/                # Configuration
│   ├── data/                  # Data pipeline
│   ├── ml/                    # ML models
│   ├── trading/               # Trading logic
│   ├── monitoring/            # Health monitoring
│   ├── notifications/         # Slack integration
│   └── utils/                 # Utilities
├── scripts/                   # Setup and maintenance
├── migrations/                # Database migrations
├── tests/                     # Test suite
├── configs/                   # YAML configurations
├── docs/                      # Documentation
├── requirements.txt           # Dependencies
├── .env.example              # Environment template
├── Makefile                  # Common commands
└── README.md                 # Project overview
```

---

## Implementation Plan

### Week 1: Foundation Setup

#### Day 1-2: Project Initialization
```bash
# Create repository
mkdir crypto-tracker-v3
cd crypto-tracker-v3
git init

# Create structure
mkdir -p src/{config,data,ml,trading,monitoring,notifications,utils}
mkdir -p scripts/{setup,data,ml,maintenance}
mkdir -p tests/{unit,integration}
mkdir -p {migrations,configs,docs,logs,data}

# Setup Python environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

#### Day 3-4: Database & Data Pipeline
- Setup Supabase project
- Run migration scripts
- Implement Polygon WebSocket connection
- Verify data flowing to database

#### Day 5-7: Feature Engineering
- Calculate technical indicators
- Store features in ml_features table
- Backfill historical data

### Week 2: ML Development

#### Day 8-10: Model Training
- Implement XGBoost model
- Train on historical data
- Run initial backtests

#### Day 11-14: Paper Trading
- Connect ML predictions to paper trader
- Implement position tracking
- Add Kraken validation

### Week 3: Integration

#### Day 15-17: Slack Integration
- Setup webhook and bot
- Implement notifications
- Add command handlers

#### Day 18-21: Monitoring & Testing
- Add health checks
- Implement alerts
- Full system testing

### Week 4-8: Validation
- Run continuous paper trading
- Monitor ML accuracy
- Collect 100+ trades
- Daily performance reviews
- Weekly optimizations

---

## Environment Configuration

### .env.example

```bash
# Polygon.io
POLYGON_API_KEY=your_polygon_api_key

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key

# Kraken
KRAKEN_API_KEY=your_kraken_api_key
KRAKEN_API_SECRET=your_kraken_api_secret

# Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
SLACK_BOT_TOKEN=xoxb-your-bot-token

# Trading Configuration
POSITION_SIZE=100
MAX_POSITIONS=5
STOP_LOSS_PCT=5.0
TAKE_PROFIT_PCT=10.0
MIN_CONFIDENCE=0.60

# System
TIMEZONE=America/Los_Angeles
ENVIRONMENT=development  # development, testing, production
LOG_LEVEL=INFO
```

---

## Quick Start Guide

### Initial Setup

```bash
# 1. Clone repository
git clone https://github.com/yourusername/crypto-tracker-v3.git
cd crypto-tracker-v3

# 2. Setup Python environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 4. Setup database
python scripts/setup/create_database.py
python scripts/migrations/run_migrations.py

# 5. Verify setup
python scripts/setup/verify_setup.py
```

### Running the System

```bash
# Start individual components
make run-data      # Start data collection
make run-ml        # Start ML predictions  
make run-trading   # Start paper trading

# Or run everything
make run-all

# Monitor system
make monitor

# View logs
tail -f logs/app/crypto-tracker.log
```

### Common Commands (Makefile)

```bash
make setup         # Initial setup
make test          # Run tests
make backfill      # Backfill historical data
make train         # Train ML model
make report        # Generate report
make clean         # Clean cache/logs
```

---

## Success Metrics

### Phase 1 Success Criteria

```python
SUCCESS_METRICS = {
    'ml_performance': {
        'accuracy': '>55%',  # Better than random
        'confidence_correlation': 'Positive',  # Higher conf = better results
        'minimum_trades': 100,  # Statistical significance
    },
    
    'trading_performance': {
        'win_rate': '>50%',
        'profit_factor': '>1.0',  # Wins > Losses
        'total_pnl': 'Positive after fees',
        'max_drawdown': '<15%'
    },
    
    'system_reliability': {
        'uptime': '>95%',
        'data_quality': '>99%',
        'ml_predictions': 'Every minute during market hours'
    }
}
```

### Evaluation Timeline

- **Week 1-2:** System operational
- **Week 3-4:** Initial results  
- **Week 5-6:** Optimization
- **Week 7-8:** Final evaluation

### Decision Points

```python
if ml_accuracy > 0.55 and total_pnl > 0:
    proceed_to_phase_2()
elif ml_accuracy > 0.52:
    optimize_and_retry()
else:
    pivot_strategy()
```

---

## Phase 2 Preview

If Phase 1 succeeds (ML accuracy >55%, profitable trading):

### Planned Enhancements

1. **Advanced ML Models**
   - LSTM for sequence prediction
   - Ensemble methods
   - Reinforcement learning

2. **Additional Data Sources**
   - Order book depth
   - Social sentiment (LunarCrush)
   - On-chain metrics

3. **Complex Trading Strategies**
   - DCA on oversold bounces
   - Trailing stops
   - Dynamic position sizing
   - Multi-timeframe analysis

4. **AI Agents**
   - Strategy optimizer
   - Risk manager
   - Market analyzer
   - Performance reporter

5. **Live Trading**
   - Gradual transition from paper
   - Start with micro positions
   - Scale with confidence

6. **Advanced Risk Management**
   - Portfolio optimization
   - Correlation analysis
   - Dynamic hedging

---

## Troubleshooting

### Common Issues

1. **No data flowing**
   - Check Polygon API key
   - Verify WebSocket connection
   - Check Supabase connection

2. **ML predictions not generating**
   - Check if model file exists
   - Verify feature calculation
   - Check for NaN values

3. **Trades not executing**
   - Verify Kraken API credentials
   - Check position limits
   - Verify sufficient balance

4. **Slack notifications not working**
   - Verify webhook URL
   - Check channel names
   - Test with curl command

---

## Support & Resources

### Documentation
- [Polygon.io Docs](https://polygon.io/docs)
- [Supabase Docs](https://supabase.com/docs)
- [Kraken API Docs](https://docs.kraken.com/rest/)
- [Slack API Docs](https://api.slack.com/)

### Project Links
- GitHub: `https://github.com/yourusername/crypto-tracker-v3`
- Supabase Dashboard: `https://app.supabase.com/project/your-project`
- Slack Workspace: Your workspace

---

## License

MIT License - See LICENSE file for details

---

## Changelog

### Version 1.0.0 (January 2025)
- Initial Phase 1 MVP implementation
- Basic ML prediction model
- Paper trading system
- Slack integration

---

*End of Master Document*
