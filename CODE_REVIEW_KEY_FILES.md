# Key Files for Code Review

## 1. Critical Scripts to Review

### Data Pipeline Files

#### `/scripts/fetch_all_historical_ohlc.py`
- **Purpose:** Main historical data fetcher
- **Review Focus:** Rate limiting, error handling, data validation
- **Known Issues:** May not be handling all 90 symbols properly

#### `/scripts/incremental_ohlc_updater.py`
- **Purpose:** Incremental updates for real-time data
- **Review Focus:** Gap detection, retry logic, performance
- **Configuration:**
  ```python
  update_config = {
      "1m": {"lookback_minutes": 10, "max_days_back": 2},
      "15m": {"lookback_minutes": 30, "max_days_back": 5},
      "1h": {"lookback_minutes": 120, "max_days_back": 7},
      "1d": {"lookback_minutes": 2880, "max_days_back": 10}
  }
  ```

#### `/scripts/validate_and_heal_gaps.py`
- **Purpose:** Detect and fix data gaps
- **Review Focus:** Gap detection algorithm, healing strategy

### Strategy Implementation

#### `/src/strategies/manager.py` (875 lines)
- **Purpose:** Central strategy orchestrator
- **Review Focus:** Signal generation, ML integration, error handling
- **Key Methods:**
  - `scan_for_signals()` - Main entry point
  - `_check_dca_setup()` - DCA strategy logic
  - `_get_ml_predictions()` - ML model integration

#### `/src/strategies/dca/detector.py` (478 lines)
- **Purpose:** DCA opportunity detection
- **Review Focus:** Setup detection logic, configuration management
- **Critical Config:**
  ```python
  default_config = {
      "price_drop_threshold": -5.0,
      "ml_confidence_threshold": 0.60,
      "grid_levels": 5,
      "take_profit": 10.0,
      "stop_loss": -8.0
  }
  ```

#### `/src/strategies/dca/executor.py` (564 lines)
- **Purpose:** DCA trade execution
- **Review Focus:** Grid calculation, position sizing, risk management

### ML Pipeline

#### `/src/ml/feature_calculator.py` (203 lines)
- **Purpose:** Technical indicator calculation
- **Review Focus:** Feature engineering, data quality
- **Features Calculated:**
  - RSI (14, 30)
  - MACD
  - Bollinger Bands
  - Moving Averages (SMA, EMA)
  - Volume indicators

#### `/src/ml/predictor.py`
- **Purpose:** ML model inference
- **Review Focus:** Model loading, prediction logic, confidence scoring

### Trading System

#### `/src/trading/paper_trader.py`
- **Purpose:** Paper trading simulation
- **Review Focus:** Order simulation, P&L tracking, position management

#### `/scripts/run_paper_trading.py` (651 lines)
- **Purpose:** Main paper trading orchestrator
- **Review Focus:** Main loop, error recovery, state management

### Database & Configuration

#### `/src/config/settings.py` (111 lines)
- **Purpose:** Central configuration management
- **Review Focus:** Environment variable handling, default values
- **Key Settings:**
  ```python
  position_size: 100.0
  max_positions: 5
  stop_loss_pct: 5.0
  take_profit_pct: 10.0
  min_confidence: 0.60
  ```

#### `/src/data/supabase_client.py`
- **Purpose:** Database interface
- **Review Focus:** Query optimization, connection management, error handling

---

## 2. Migration Files to Review

### Critical Migrations

#### `/migrations/006_create_shadow_testing.sql` (463 lines)
- Most recent migration
- Creates shadow testing infrastructure
- **Status:** May not be applied to production

#### `/migrations/002_strategy_tables.sql`
- Creates strategy configuration tables
- **Issue:** Tables not found in current database

#### `/migrations/003_create_unified_ohlc_table.sql`
- OHLC table structure
- **Review:** Check indexes and partitioning

---

## 3. Railway Deployment Files

#### `/railway.json`
```json
{
  "services": {
    "Paper Trading": {
      "startCommand": "python scripts/run_paper_trading.py"
    },
    "Data Collector": {
      "startCommand": "python scripts/run_data_collector.py"
    },
    "ML Retrainer Cron": {
      "startCommand": "python scripts/run_daily_retraining.py",
      "cronSchedule": "0 9 * * *"
    }
  }
}
```

#### `/Procfile`
```
web: ls -la && ls -la scripts/ && ls -la src/ && ls -la src/ml/ && python -u start.py
```
**Issue:** Contains debug commands that shouldn't be in production

---

## 4. Test Files to Review

### Integration Tests
- `/scripts/test_integration.py`
- `/scripts/test_strategy_manager.py`
- `/scripts/test_paper_trader.py`

### Strategy Tests
- `/scripts/test_dca_detector.py`
- `/scripts/test_dca_executor.py`
- `/scripts/test_swing_strategy.py`
- `/scripts/test_channel_strategy.py`

---

## 5. Recent Git Commits (Last 20)

```
d2b9dbc Fix ML predictor field names to match StrategyManager expectations
b350c9c Implement ML prediction methods for all strategies
4e57223 Apply Black formatting to fix CI
bab92e8 Fix critical shadow evaluator bugs
354f80f Apply Black formatting to shadow_scan_monitor.py
0890a6e Fix None value errors in shadow logger
f9153b7 Apply Black formatting to fix CI
28f1f60 Fix Supabase client issues and add shadow scan monitor
0ed5f8f Fix Supabase query issues in shadow analyzer and evaluator
89c7da2 Add ShadowLogger integration to StrategyManager (partial)
6196ff4 Fix missing Dict import in run_shadow_services.py
f98a6cf Apply Black formatting to shadow testing files
7d49885 Fix aiohttp version conflict - remove duplicate entry
e438bb0 Add Shadow Testing System - 10x learning acceleration
9893362 Fix ML Retrainer Cron command - remove invalid --once flag
```

---

## 6. Questions for Code Review

### Data Pipeline
1. Why is only 1 symbol showing data when 90 are configured?
2. Is the Polygon API rate limiting causing issues?
3. Why are strategy label tables missing?

### ML Pipeline
1. How often are models retrained?
2. What's the model performance on test data?
3. Are features being calculated correctly for all symbols?

### Trading System
1. Is paper trading running continuously?
2. How are positions being tracked?
3. What's the latency between signal and execution?

### Deployment
1. Are all Railway services running?
2. How is monitoring configured?
3. What's the rollback strategy?

### Performance
1. Database query timeouts - need indexing?
2. Memory usage of services?
3. WebSocket connection stability?

---

## 7. Recommended Review Order

1. **Start with database state**
   - Run `scripts/gather_review_data.py`
   - Check migration status

2. **Review data pipeline**
   - `fetch_all_historical_ohlc.py`
   - `incremental_ohlc_updater.py`
   - Check data coverage

3. **Review strategy implementation**
   - `manager.py` - main orchestrator
   - DCA detector and executor
   - ML predictor integration

4. **Review deployment**
   - Railway configuration
   - Service health
   - Error logs

5. **Test coverage**
   - Run integration tests
   - Check test results

---

## 8. Commands to Run During Review

```bash
# Check database state
python scripts/gather_review_data.py

# Check data coverage
python scripts/check_data_coverage.py

# Check ML features
python scripts/check_ml_features.py

# Check recent trading activity
python scripts/analyze_trading_activity.py

# View scan history
python scripts/view_scan_history.py

# Test paper trading
python scripts/test_paper_trader.py

# Check system health
python scripts/monitor_data_health.py
```
