# Crypto ML Trading System - crypto-tracker-v3

## 🎯 Mission
Prove whether machine learning can predict crypto price movements with >55% accuracy through a streamlined Phase 1 MVP.

## 📊 Status
- **Phase:** 1 - MVP Development
- **Goal:** Validate ML hypothesis
- **Timeline:** 30-60 days

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Polygon.io API key ($49/month)
- Supabase account (free tier works)
- Kraken API credentials
- Slack workspace

### Setup
```bash
# Clone repository
git clone https://github.com/yourusername/crypto-tracker-v3.git
cd crypto-tracker-v3

# Setup Python environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Setup database
python scripts/setup/create_database.py
python scripts/migrations/run_migrations.py

# Verify setup
python scripts/setup/verify_setup.py
```

### Running the System
```bash
# Start all components
make run-all

# Or run individually
make run-data      # Data collection
make run-ml        # ML predictions
make run-trading   # Paper trading

# Monitor system
make monitor
```

## 📁 Project Structure
```
crypto-tracker-v3/
├── src/               # Core application code
├── scripts/           # Setup and maintenance scripts
├── tests/            # Test suite
├── migrations/       # Database migrations
├── configs/          # Configuration files
├── docs/            # Documentation
└── MASTER_PLAN.md   # Complete system documentation
```

## 📈 Success Metrics
- ML Accuracy: >55%
- Win Rate: >50%
- Profit Factor: >1.0
- System Uptime: >95%

## 📖 Documentation
See [MASTER_PLAN.md](MASTER_PLAN.md) for complete system documentation.

## 📝 License
MIT License - See LICENSE file for details
