# Threshold Analysis for Swing & Channel Strategies

## Current System Architecture

When ML is **disabled**, the system flow is:
1. **Strategy Manager** calls complex detectors first (SwingDetector, ChannelDetector)
2. If complex detector finds nothing, it checks SimpleRules as fallback
3. Problem: Complex detectors are too strict, SimpleRules signals are ignored

## 📊 SWING STRATEGY THRESHOLDS

### SwingDetector (Complex - Primary)
Located in: `src/strategies/swing/detector.py`

| Parameter | Current Value | Issue | Proposed Change |
|-----------|--------------|-------|-----------------|
| breakout_threshold | 1.02 (2% above resistance) | Too high for current market | **1.005 (0.5%)** |
| volume_spike_threshold | 2.0x average | Too strict - market has low volume | **1.3x** |
| rsi_bullish_min | 50 | Reasonable | Keep 50 |
| min_price_change_24h | 3.0% | Too high for consolidating market | **1.0%** |
| max_price_change_24h | 15.0% | Reasonable | Keep 15% |
| min_volume_usd | $1,000,000 | May be too high for smaller coins | **$100,000** |
| max_volatility | 10% | Reasonable | Keep 10% |
| min_trend_strength | 2% SMA difference | Reasonable | Keep 2% |

### SimpleRules (Fallback - Currently Ignored)
Located in: `src/strategies/simple_rules.py`
- swing_breakout_threshold: 0.3% (already aggressive)
- volume requirement: 1.5x (reasonable)

## 📈 CHANNEL STRATEGY THRESHOLDS

### ChannelDetector (Complex - Primary)
Located in: `src/strategies/channel/detector.py`

| Parameter | Current Value | Issue | Proposed Change |
|-----------|--------------|-------|-----------------|
| min_touches | 2 per line | Requires perfect channels | **1 per line** |
| min_channel_width | 1% | Reasonable | Keep 1% |
| max_channel_width | 10% | Reasonable | Keep 10% |
| touch_tolerance | 0.2% | Too strict | **0.5%** |
| buy_zone | Bottom 25% | Reasonable | Keep 25% |
| sell_zone | Top 25% | Reasonable | Keep 75% |
| parallel_tolerance | 15% slope diff | Too strict for real channels | **30%** |

### SimpleRules (Fallback - Currently Ignored)
- channel_position_threshold: 35% (already reasonable)
- Works fine but being bypassed!

## 🔧 INTEGRATION ISSUE

The main problem is in `src/strategies/manager.py`:

### Current Flow (BROKEN):
```python
# _scan_channel_opportunities()
channel = self.channel_detector.detect_channel(symbol, data)  # Too strict!
if not channel:
    continue  # Never reaches SimpleRules!

# Later...
simple_setup = self.simple_rules.check_channel_setup(symbol, data)
# This only runs if complex detector already found something
```

### Proposed Fix:
When ML is disabled, we should:
1. Try complex detector first
2. If it fails, try SimpleRules as true fallback
3. OR lower complex detector thresholds significantly

## Market Analysis Results

From our testing:
- **Swing**: All coins showing negative breakouts (-0.25% to -0.57%), low volume (0.5x-0.9x)
- **Channel**: Many coins at channel bottoms (0-12% position) - ready for Channel buys!

## Recommendation

1. **Lower complex detector thresholds** as shown above
2. **Fix integration logic** to properly use SimpleRules as fallback
3. **Consider market conditions** - we're in consolidation, not trending

Would you like me to proceed with these threshold changes?
