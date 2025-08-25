# 📊 Market Regime Detection System - Complete Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Core Architecture](#core-architecture)
3. [Regime States](#regime-states)
4. [Detection Logic](#detection-logic)
5. [Position Size Adjustments](#position-size-adjustments)
6. [Integration Points](#integration-points)
7. [Database Schema](#database-schema)
8. [Circuit Breaker Functionality](#circuit-breaker-functionality)
9. [Configuration & Controls](#configuration--controls)
10. [Monitoring & Alerts](#monitoring--alerts)
11. [Historical Context](#historical-context)
12. [Usage Examples](#usage-examples)

---

## System Overview

The Market Regime Detection System is a critical safety component that monitors Bitcoin price movements to identify market conditions and adjust trading behavior accordingly. It acts as a **circuit breaker** to protect against flash crashes, market panics, and euphoric FOMO conditions.

### Purpose
- **Primary Goal**: Protect capital during extreme market events
- **Secondary Goal**: Optimize position sizing based on market conditions
- **Tertiary Goal**: Provide market context for strategy decisions

### Philosophy
As documented in `MASTER_PLAN.md` (Line 2214):
> "Fast protection against flash crashes"

The system prioritizes capital preservation over opportunity capture during extreme conditions.

---

## Core Architecture

### Main Component: `RegimeDetector` Class
**Location**: `src/strategies/regime_detector.py`

The RegimeDetector maintains a rolling window of Bitcoin price data and continuously evaluates market conditions based on price changes over different timeframes.

### Key Features
- **Real-time Monitoring**: Updates with every BTC price tick
- **Rolling Window**: Stores 240 minutes (4 hours) of price data
- **Multiple Timeframes**: Analyzes 1-hour and 4-hour changes
- **Alert Cooldown**: 5-minute cooldown between alerts to prevent spam
- **Configurable**: Can be enabled/disabled for testing

---

## Regime States

The system identifies four distinct market regimes:

### 1. 🚨 **PANIC**
- **Trigger**: BTC down >3% in 1 hour
- **Action**: Stop ALL new trades immediately
- **Position Multiplier**: 0.0 (no new positions)
- **Rationale**: Extreme downward movement indicates potential crash

### 2. ⚠️ **CAUTION**
- **Trigger**: BTC down >2% in 1hr OR >5% in 4hr
- **Action**: Reduce position sizes by 50%
- **Position Multiplier**: 0.5
- **Rationale**: Significant weakness requiring risk reduction

### 3. 🚀 **EUPHORIA**
- **Trigger**: BTC up >3% in 1 hour
- **Action**: Reduce position sizes by 30% (FOMO protection)
- **Position Multiplier**: 0.7
- **Rationale**: Rapid upward moves often reverse; avoid buying tops

### 4. ✅ **NORMAL**
- **Trigger**: None of the above conditions
- **Action**: Business as usual
- **Position Multiplier**: 1.0
- **Rationale**: Standard market conditions

---

## Detection Logic

### Price Change Calculation
```python
def get_btc_change(hours: float) -> Optional[float]:
    """
    Calculates percentage change over specified hours
    Returns None if insufficient data
    """
    current_price = latest_price
    past_price = price_from_X_hours_ago
    change = ((current_price - past_price) / past_price) * 100
```

### Regime Determination Priority
1. **Check for PANIC** (highest priority)
2. **Check for CAUTION**
3. **Check for EUPHORIA**
4. **Default to NORMAL**

### Data Requirements
- Minimum 2 price points for any calculation
- Uses oldest available data if full history not available
- Returns NORMAL regime if insufficient data

---

## Position Size Adjustments

The system modifies position sizes based on the current regime:

### Strategy-Agnostic Adjustments
From `MASTER_PLAN.md` (Line 2217):
> "All strategies affected equally (per user preference)"

| Regime | Multiplier | Effect |
|--------|------------|--------|
| PANIC | 0.0x | No new positions |
| CAUTION | 0.5x | Half normal size |
| EUPHORIA | 0.7x | 30% reduction |
| NORMAL | 1.0x | Full size |

### ML Model Integration
The regime also affects ML confidence adjustments:
- **BEAR Market**: 1.3x position size (opportunities in downtrends)
- **NORMAL Market**: 1.0x position size
- **BULL Market**: 0.7x position size (reduce during euphoria)

---

## Integration Points

### 1. Strategy Manager (`src/strategies/manager.py`)
- Updates BTC price on every scan
- Checks regime before executing trades
- Logs regime changes
- Blocks trades during PANIC

### 2. Paper Trading (`scripts/run_paper_trading_simple.py`)
- Initializes RegimeDetector on startup
- Updates with market data
- Applies position size adjustments
- Includes regime in scan history

### 3. Position Sizer (`src/trading/position_sizer.py`)
- Reads regime for dynamic sizing
- Applies multipliers to calculated sizes
- Integrates with Kelly Criterion

### 4. DCA Detector (`src/strategies/dca/detector.py`)
- Filters opportunities by BTC regime
- Stores regime with setup data
- Calculates regime if not in database

---

## Database Schema

### `market_regimes` Table
```sql
CREATE TABLE market_regimes (
    timestamp TIMESTAMPTZ PRIMARY KEY,
    btc_regime VARCHAR(20),  -- 'BULL', 'BEAR', 'NEUTRAL', 'CRASH'
    btc_price DECIMAL(20,8),
    btc_trend_strength DECIMAL(10,4),
    market_fear_greed INTEGER,  -- 0-100 scale
    total_market_cap DECIMAL(20,2)
);
```

### `scan_history` Integration
Every scan records:
- `market_regime`: Current regime state
- `btc_price`: BTC price at scan time
- Used for ML training and analysis

---

## Circuit Breaker Functionality

### Automatic Triggers
1. **PANIC Mode Activation**
   - Instantly stops all new position opens
   - Allows closes only
   - Sends alert to Slack

2. **CAUTION Mode Activation**
   - Reduces all position sizes by 50%
   - Increases confirmation requirements
   - Warns in logs and Slack

3. **EUPHORIA Mode Protection**
   - Reduces FOMO by cutting sizes 30%
   - Prevents buying at extreme tops
   - Logs warning about market euphoria

### Manual Controls
- **Enable/Disable**: Pass `enabled=False` to constructor
- **Reset**: Call `regime_detector.reset()` to clear history
- **Force Regime**: Can be overridden for testing

---

## Configuration & Controls

### Initialization
```python
from src.strategies.regime_detector import RegimeDetector

# Production mode
detector = RegimeDetector(enabled=True)

# Testing mode (bypass protection)
detector = RegimeDetector(enabled=False)
```

### Configuration Parameters
```python
REGIME_CONFIG = {
    'enabled': True,  # Master switch
    'btc_window': 240,  # Minutes of history to keep
    'alert_cooldown': 300,  # Seconds between alerts
    
    # Thresholds
    'panic_1h': -3.0,  # 1-hour drop for panic
    'caution_1h': -2.0,  # 1-hour drop for caution
    'caution_4h': -5.0,  # 4-hour drop for caution
    'euphoria_1h': 3.0,  # 1-hour rise for euphoria
    
    # Position multipliers
    'panic_mult': 0.0,
    'caution_mult': 0.5,
    'euphoria_mult': 0.7,
    'normal_mult': 1.0
}
```

---

## Monitoring & Alerts

### Logging Levels
- **ERROR**: PANIC regime (🚨)
- **WARNING**: CAUTION or EUPHORIA regimes (⚠️/🚀)
- **INFO**: NORMAL regime or transitions (✅)

### Slack Integration
When integrated with notifications:
- Sends alerts on regime changes
- Includes BTC price changes
- Respects cooldown period
- Priority based on severity

### Monitoring Stats
```python
stats = detector.get_regime_stats()
# Returns:
{
    "current_regime": "NORMAL",
    "btc_1h_change": -1.5,
    "btc_4h_change": -3.2,
    "position_multiplier": 1.0,
    "data_points": 180,
    "enabled": True
}
```

---

## Historical Context

### Implementation Timeline
- **August 18, 2025**: Initial MVP Circuit Breaker implemented
- **Purpose**: Response to observed flash crashes in crypto markets
- **Design Philosophy**: "Market doesn't follow rules, it follows patterns"

### Lessons Learned
From `MASTER_PLAN.md`:
> "May want strategy-specific adjustments in future"

Currently applies uniform adjustments to all strategies, but architecture supports strategy-specific multipliers if needed.

---

## Usage Examples

### Basic Usage
```python
# Initialize detector
detector = RegimeDetector(enabled=True)

# Update with BTC price
detector.update_btc_price(64000.00)

# Check current regime
regime = detector.get_market_regime()
print(f"Current regime: {regime.value}")

# Get position multiplier
multiplier = detector.get_position_multiplier()
print(f"Position size adjustment: {multiplier}x")
```

### Integration with Trading
```python
# In strategy manager
if "BTC" in market_data:
    btc_price = market_data["BTC"][-1]["close"]
    detector.update_btc_price(btc_price)
    
regime = detector.get_market_regime()

if regime == MarketRegime.PANIC:
    logger.error("PANIC mode - stopping all trades")
    return  # Exit without trading

# Apply position sizing
base_size = 100  # $100
adjusted_size = base_size * detector.get_position_multiplier()
```

### Testing Scenarios
```python
# Test panic scenario
detector = RegimeDetector(enabled=True)
detector.update_btc_price(100000)
time.sleep(1)
detector.update_btc_price(96000)  # 4% drop

regime = detector.get_market_regime()
assert regime == MarketRegime.PANIC
assert detector.get_position_multiplier() == 0.0
```

---

## Advanced Features

### Trend Strength Calculation
The system can calculate trend strength for storage:
- Uses 50-period SMA distance
- Normalizes to percentage
- Stored in `market_regimes` table

### Multiple Regime Systems
The codebase supports two regime concepts:

1. **Circuit Breaker Regimes** (RegimeDetector)
   - PANIC, CAUTION, EUPHORIA, NORMAL
   - Based on short-term BTC movements
   - For immediate risk management

2. **Market Structure Regimes** (DCA/ML)
   - BULL, BEAR, NEUTRAL, CRASH
   - Based on longer-term trends
   - For strategy selection

### Future Enhancements
Documented considerations for Phase 2:
- Strategy-specific multipliers
- Dynamic threshold adjustment
- Correlation-based regime detection
- Fear & Greed Index integration

---

## Best Practices

### 1. Always Enable in Production
```python
# Production
detector = RegimeDetector(enabled=True)

# Only disable for specific testing
detector = RegimeDetector(enabled=False)  # Testing only!
```

### 2. Regular Monitoring
- Check regime stats regularly
- Monitor data point count
- Verify BTC price updates

### 3. Alert Response
- PANIC: Review all open positions immediately
- CAUTION: Monitor closely, prepare for volatility
- EUPHORIA: Avoid new longs, consider taking profits

### 4. Testing
- Test with historical crash data
- Verify multipliers apply correctly
- Ensure Slack alerts work

---

## Troubleshooting

### Common Issues

**Issue**: Regime stuck in PANIC
- **Cause**: BTC price not updating
- **Solution**: Check data feed, verify update calls

**Issue**: No regime changes detected
- **Cause**: Detector disabled or not initialized
- **Solution**: Verify `enabled=True` in initialization

**Issue**: Wrong multipliers applied
- **Cause**: Old regime cached
- **Solution**: Call `get_market_regime()` before `get_position_multiplier()`

---

## Summary

The Market Regime Detection System is a critical safety component that:
- Monitors Bitcoin as the market leader
- Identifies four distinct market conditions
- Automatically adjusts risk exposure
- Acts as a circuit breaker during extreme events
- Provides context for all trading decisions

It represents the system's first line of defense against market crashes and excessive risk-taking during euphoric conditions, embodying the principle that **capital preservation comes before profit generation**.

---

*Last Updated: August 2025*
*System Version: MVP Circuit Breaker v1.0*
