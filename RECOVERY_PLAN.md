# System Recovery & Stabilization Plan
*Created: August 21, 2024*
*Priority: CRITICAL*

## Executive Summary
The system has been built "top-down" with ML and Shadow Testing layers added before the core trading foundation was proven to work. This plan outlines a systematic approach to rebuild from the foundation up.

## Current State Analysis

### Working Components ✅
- **Data Collection**: Singleton websocket implementation (fragile but functional)
- **Strategy Scanning**: All 3 strategies actively scanning
- **Data Storage**: Accumulating significant data in Supabase

### Non-Working Components ❌
- **Paper Trading**: Hummingbot configured but not executing trades
- **ML Integration**: Models trained but not connected to trading
- **Shadow Testing**: Evaluating non-existent trades

### Critical Issues 🚨
1. No trades are actually executing despite signals being generated
2. ML/Shadow systems built on non-functional trading foundation
3. Data storage growing rapidly without retention policies
4. Polygon API reaching connection limits

---

## Recovery Plan - Phased Approach

### Phase 0: Data Storage Optimization (Immediate)
**Timeline**: Day 1 (Parallel with Phase 1)
**Goal**: Prevent runaway storage costs and optimize performance

#### Actions:
1. **Run Storage Analysis**
   ```bash
   python scripts/analyze_data_storage.py
   ```

2. **Implement Immediate Cleanup**
   ```sql
   -- Delete old scan history
   DELETE FROM scan_history WHERE timestamp < NOW() - INTERVAL '30 days';
   DELETE FROM shadow_testing_scans WHERE scan_time < NOW() - INTERVAL '30 days';
   DELETE FROM ml_features WHERE timestamp < NOW() - INTERVAL '90 days';
   ```

3. **Create Data Retention Policy**
   - **1-minute data**: Keep 30 days, archive 30-90 days, delete >90 days
   - **15-minute data**: Keep 6 months, archive 6-12 months, delete >1 year
   - **1-hour data**: Keep 1 year, archive 1-2 years
   - **ML features**: Keep 3 months (regenerate as needed)
   - **Scan history**: Keep 30 days raw, aggregate 30-90 days

4. **Set Up Archival Process**
   ```sql
   -- Create archive table
   CREATE TABLE ohlc_data_archive (LIKE ohlc_data INCLUDING ALL);
   
   -- Move old data (run during off-hours)
   INSERT INTO ohlc_data_archive 
   SELECT * FROM ohlc_data 
   WHERE timeframe = '1min' AND timestamp < NOW() - INTERVAL '30 days';
   ```

5. **Monitor Impact**
   - Check storage reduction
   - Verify query performance improvement
   - Calculate cost savings

---

### Phase 1: Stabilize Foundation (Days 1-2)
**Goal**: Get basic paper trading working with simple signals

#### 1.1 Disable Complex Systems
```python
# In process_manager.py, disable:
'ml-predictor': {'enabled': False},
'shadow-testing': {'enabled': False},
'ml-trainer': {'enabled': False}
```

#### 1.2 Simplify Strategy Detection
- Remove ML confidence requirements
- Use pure rule-based signals
- Lower all thresholds by 30%:
  ```python
  DCA_DROP_THRESHOLD = 0.03  # Was 0.05
  SWING_BREAKOUT = 0.02      # Was 0.03
  CHANNEL_STRENGTH = 0.5     # Was 0.7
  ```

#### 1.3 Create Direct Trading Pipeline
```python
# New file: scripts/simple_paper_trader.py
"""
Direct pipeline: Strategy Signal → Hummingbot API
No ML, no shadows, just pure execution
"""
```

#### 1.4 Configure Hummingbot Integration
- Set up programmatic API access
- Remove manual interaction requirements
- Create order submission pipeline
- Implement position tracking

#### 1.5 Verification Checklist
- [ ] Strategies detecting signals
- [ ] Signals reaching Hummingbot
- [ ] Orders being placed
- [ ] Positions being tracked
- [ ] P&L being calculated

---

### Phase 2: Validate Trading System (Days 3-5)
**Goal**: Generate 50+ trades to prove system works

#### 2.1 Aggressive Testing Configuration
```python
PAPER_TRADING_TEST = {
    'min_confidence': 0.4,      # Very low threshold
    'position_size': 20,        # Small positions
    'max_positions': 20,        # Many concurrent
    'strategies': ['DCA'],      # Start with one
    'symbols': ['BTC', 'ETH']  # Top liquidity only
}
```

#### 2.2 Monitor & Debug
- Log every signal generated
- Track signal → order conversion rate
- Identify any bottlenecks
- Fix integration issues

#### 2.3 Success Metrics
- [ ] 50+ trades executed
- [ ] <5% order failure rate
- [ ] Stop-loss orders working
- [ ] Take-profit orders working
- [ ] All trades logged to database

---

### Phase 3: Reintroduce ML (Days 6-8)
**Goal**: Layer ML predictions on proven foundation

#### 3.1 Enable ML Predictions
```python
# Re-enable in process_manager.py:
'ml-predictor': {'enabled': True},
# Keep shadow-testing disabled
```

#### 3.2 Conservative ML Integration
- ML as confidence booster only
- Still accept rule-based signals
- ML confidence threshold: 0.6
- Track ML vs non-ML performance

#### 3.3 Validation
- [ ] ML predictions being generated
- [ ] Predictions influencing trades appropriately
- [ ] ML-enhanced trades executing
- [ ] Performance improvement measurable

---

### Phase 4: Add Shadow Testing (Days 9-10)
**Goal**: Enable shadow testing with real trades to compare

#### 4.1 Enable Shadow System
```python
# Start with minimal variations:
SHADOW_VARIATIONS = ['CHAMPION', 'CONSERVATIVE', 'AGGRESSIVE']
```

#### 4.2 Validate Shadow Logic
- [ ] Real trades available for comparison
- [ ] Shadow evaluations accurate
- [ ] Performance differences tracked
- [ ] Adjustment recommendations logical

---

## Implementation Scripts

### 1. Simple Paper Trader
```python
# scripts/simple_paper_trader.py
"""Minimal trading pipeline for testing"""

async def execute_trade(signal):
    """Direct signal to Hummingbot execution"""
    # No ML check
    # No shadow check
    # Just execute if signal exists
    pass
```

### 2. System Health Monitor
```python
# scripts/monitor_system_health.py
"""Real-time monitoring of all components"""

def check_components():
    return {
        'data_flow': check_polygon_data(),
        'signals': count_recent_signals(),
        'trades': count_recent_trades(),
        'errors': get_recent_errors()
    }
```

### 3. Trade Verification
```python
# scripts/verify_trades.py
"""Ensure trades are actually happening"""

def verify_trade_execution():
    # Check signal was generated
    # Verify order was placed
    # Confirm execution
    # Validate P&L calculation
    pass
```

---

## Data Pipeline Fixes

### Polygon WebSocket Issues
1. **Current**: Singleton connection (temporary fix)
2. **Short-term**: Add connection retry logic
3. **Medium-term**: Purchase second WebSocket connection
4. **Long-term**: Add backup data source (Binance/CoinGecko)

### Backup Data Source
```python
# src/data/backup_fetcher.py
class BackupDataFetcher:
    """Fallback when Polygon fails"""
    
    def fetch_from_binance(self):
        # Free tier, no WebSocket limits
        pass
    
    def fetch_from_coingecko(self):
        # Additional backup
        pass
```

---

## Success Criteria

### Phase 1 Complete When:
- [x] 10+ trades executed successfully
- [x] Orders reaching Hummingbot
- [x] Basic position management working

### Phase 2 Complete When:
- [x] 50+ trades with <5% failure rate
- [x] Stop-loss/take-profit working
- [x] All strategies tested

### Phase 3 Complete When:
- [x] ML predictions improving win rate by >5%
- [x] 100+ ML-influenced trades
- [x] Clear performance metrics

### Phase 4 Complete When:
- [x] Shadow variations showing clear differences
- [x] Adjustment recommendations validated
- [x] Full system integrated

---

## Risk Mitigation

### If Paper Trading Won't Work:
1. Build custom paper trader using current prices
2. Use src/trading/paper_trader.py as base
3. Simulate order execution locally

### If Polygon Continues Failing:
1. Immediately implement Binance backup
2. Reduce symbol count to top 20
3. Increase data fetch intervals

### If Storage Costs Escalate:
1. Aggressive data deletion (>30 days)
2. Disable ML feature storage
3. Move to time-series database

---

## Timeline

| Day | Phase | Key Activities |
|-----|-------|---------------|
| 1 | Phase 0+1 | Storage cleanup + Disable ML/Shadow |
| 2 | Phase 1 | Fix Hummingbot integration |
| 3-4 | Phase 2 | Generate test trades |
| 5 | Phase 2 | Validate & debug |
| 6-7 | Phase 3 | Re-enable ML |
| 8 | Phase 3 | Measure ML impact |
| 9-10 | Phase 4 | Enable shadows |

---

## Daily Checklist

### Morning (9 AM PST)
- [ ] Check overnight data collection
- [ ] Review error logs
- [ ] Verify storage usage
- [ ] Check signal generation

### Afternoon (2 PM PST)
- [ ] Review trade execution
- [ ] Check P&L tracking
- [ ] Monitor system resources
- [ ] Fix any issues

### Evening (6 PM PST)
- [ ] Daily performance summary
- [ ] Adjust parameters if needed
- [ ] Plan next day priorities
- [ ] Update progress tracker

---

## Emergency Procedures

### If Everything Breaks:
1. Stop all services: `pkill -f python`
2. Clear corrupted data: `python scripts/cleanup_bad_data.py`
3. Restart data collection only
4. Gradually re-enable services

### If Storage Fills Up:
1. Emergency delete: `DELETE FROM scan_history WHERE timestamp < NOW() - INTERVAL '7 days';`
2. Disable all scanning temporarily
3. Archive critical data
4. Resume with reduced retention

### If No Trades Execute:
1. Switch to local paper trader
2. Log simulated trades to database
3. Continue testing with simulation
4. Fix Hummingbot integration separately

---

## Notes

- **Priority**: Storage optimization and basic trading MUST work before anything else
- **Simplicity**: Remove complexity until base system proven
- **Monitoring**: Log everything for debugging
- **Incremental**: Add features back one at a time
- **Validation**: Prove each phase works before proceeding

---

*Last Updated: August 21, 2024*
