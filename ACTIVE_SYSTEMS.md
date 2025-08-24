# Active Systems Quick Reference

**Last Updated**: January 2025

## 🚀 Currently Active Production Systems

### Paper Trading
```bash
scripts/run_paper_trading_simple.py  # ACTIVE ✅
```
- Railway Service: "Paper Trading"
- Config: `configs/paper_trading.json`
- Core Classes: `SimplePaperTraderV2`

### Data Updates
```bash
scripts/incremental_ohlc_updater.py  # ACTIVE ✅
```
- Railway Service: "Data Scheduler"
- Updates: 1m, 15m, 1h, 1d OHLC data

### Strategy Pre-Calculator
```bash
scripts/strategy_precalculator.py  # ACTIVE ✅
```
- Railway Service: "System - Pre-Calculator"
- Updates cache tables every 5 minutes

### ML Analyzer
```bash
scripts/run_ml_analyzer.py  # ACTIVE ✅
```
- Railway Service: "Research - ML Analyzer"
- Analyzes scan_history, generates predictions

### Dashboard
```bash
live_dashboard.py  # ACTIVE ✅
```
- Railway Service: "Live Dashboard"
- Port: 8080 (local), Railway URL (deployed)

### Daily Jobs
```bash
scripts/run_daily_retraining.py      # ML Retrainer
scripts/daily_data_cleanup.py        # Data retention
scripts/refresh_materialized_views.py # View refresh
```

## 📁 Directory Structure

```
crypto-tracker-v3/
├── src/              # Core application code
├── scripts/          # Active scripts
│   └── _deprecated/  # Old/unused scripts
├── tests/            # Test files
├── configs/          # Configuration files
├── docs/             # Documentation
├── models/           # ML model files
├── migrations/       # Database migrations
└── logs/             # Log files
```

## ⚠️ Deprecated Scripts Location

All deprecated scripts have been moved to:
- `scripts/_deprecated/`

Including:
- Old paper trading versions (v1, v2)
- Old data collectors
- Old feature calculators
- Test scripts (moved to `tests/`)

## 🔄 Data Flow

1. **Polygon API** → `incremental_ohlc_updater.py` → **ohlc_data table**
2. **ohlc_data** → `HybridDataFetcher` → **Strategies**
3. **Strategies** → `SimplePaperTraderV2` → **paper_trades table**
4. **paper_trades** → `live_dashboard.py` → **Web UI**

## 🛠️ Quick Commands

```bash
# Run paper trading locally
python scripts/run_paper_trading_simple.py

# Run dashboard locally
python live_dashboard.py

# Run ML analyzer
python scripts/run_ml_analyzer.py

# Update OHLC data
python scripts/incremental_ohlc_updater.py

# Pre-calculate strategy readiness
python scripts/strategy_precalculator.py
```

## 📊 Database Tables

**Active Tables**:
- `ohlc_data` - Price data
- `paper_trades` - Trading records
- `paper_performance` - Performance metrics
- `scan_history` - All scanning decisions
- `ml_predictions` - ML predictions
- `strategy_status_cache` - Pre-calculated readiness
- `market_summary_cache` - Market conditions

## 🚨 Important Notes

1. **Always check MASTER_PLAN.md** "Current Active Systems" section for full details
2. **Never use scripts in _deprecated/** folder
3. **Test files are in tests/** not scripts/
4. **Documentation is in docs/** not root
5. **Logs go in logs/** directory

---

For detailed information, see the "Current Active Systems" section in MASTER_PLAN.md
