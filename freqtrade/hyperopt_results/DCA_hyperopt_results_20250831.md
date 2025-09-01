# DCA Strategy Hyperopt Results
**Date**: August 31, 2025  
**Runtime**: ~4 minutes  
**Epochs**: 1560 (stopped early)  
**Data Period**: July 22, 2025 - August 31, 2025 (40 days)  
**Timeframe**: 5 minutes  
**Loss Function**: CalmarHyperOptLoss  

## ⚠️ WARNING: NEGATIVE PERFORMANCE
The DCA strategy showed **negative returns** during hyperoptimization. This suggests the strategy may not be well-suited for the current market conditions or the parameters need significant adjustment.

## Performance Summary
- **Total Trades**: 334
- **Win/Draw/Loss**: 136/0/198 (40.7% win rate)
- **Average Profit per Trade**: -0.58% ❌
- **Median Profit**: -0.26%
- **Total Profit**: -128.61 USDT (-1.29% of 10,000 USDT starting balance) ❌
- **Average Trade Duration**: 4 hours 27 minutes
- **Max Drawdown**: 128.61 USDT (1.29%)
- **Objective Score**: 48.99 (lower is better for CalmarHyperOptLoss)
- **Calmar Ratio**: -48.99 (very poor risk-adjusted returns)

## Optimized Parameters

### Buy Parameters
```python
buy_params = {
    "buy_drop_threshold": -2.32,          # Min price drop to trigger (default: -2.25)
    "buy_grid_levels": 4,                  # Number of DCA levels (default: 5)
    "buy_grid_spacing": 0.016,             # Spacing between levels (default: 0.02)
    "buy_rsi_max": 74,                     # Max RSI for entry (default: 65)
    "buy_rsi_min": 27,                     # Min RSI for entry (default: 25)
    "buy_volatility_max": 0.15,            # Max volatility (default: 0.1)
    "buy_volume_requirement": 0.51,        # Volume ratio requirement (default: 0.85)
    "buy_volume_threshold": 187074,        # Min volume in USDT (default: 100000)
}
```

### Sell Parameters
```python
sell_params = {
    "sell_rsi_high": 73,                   # RSI exit threshold (default: 75)
    "sell_take_profit": 0.14,              # Take profit percentage (default: 0.07)
}
```

### Risk Management
```python
# Stoploss
stoploss = -0.263  # 26.3% stoploss (default: -0.10)

# Trailing stop
trailing_stop = True
trailing_stop_positive = 0.024           # Start trailing at 2.4% profit
trailing_stop_positive_offset = 0.041    # Trail by 4.1% from peak
trailing_only_offset_is_reached = False
```

## Per-Pair Performance
| Pair | Trades | Avg Profit | Total Profit | Win Rate |
|------|--------|------------|--------------|----------|
| ALGO/USDT | 14 | 0.02% | 0.15 USDT | 50.0% ✅ |
| BTC/USDT | 3 | -0.44% | -0.87 USDT | 0.0% ❌ |
| ATOM/USDT | 6 | -0.55% | -2.18 USDT | 50.0% |
| DOT/USDT | 16 | -0.27% | -2.85 USDT | 56.2% |
| ETH/USDT | 31 | -0.26% | -5.27 USDT | 38.7% ❌ |
| ADA/USDT | 54 | -0.37% | -13.03 USDT | 46.3% ❌ |
| SOL/USDT | 38 | -0.59% | -14.78 USDT | 36.8% ❌ |
| XRP/USDT | 27 | -0.83% | -14.86 USDT | 29.6% ❌ |
| AVAX/USDT | 33 | -0.78% | -17.06 USDT | 30.3% ❌ |
| LINK/USDT | 62 | -0.63% | -25.63 USDT | 46.8% ❌ |
| DOGE/USDT | 50 | -0.98% | -32.22 USDT | 38.0% ❌ |

## Key Issues & Insights

### 🔴 Critical Problems:
1. **Negative Overall Performance**: Lost 1.29% over 40 days
2. **Poor Win Rate**: Only 40.7% of trades profitable
3. **Worst Performers**: DOGE, LINK, AVAX showing significant losses
4. **High Trade Frequency**: 334 trades (8.56/day) may be overtrading

### What the Optimizer Found:
1. **Reduced Grid Levels**: 4 instead of 5 (less averaging down)
2. **Tighter Grid Spacing**: 1.6% vs 2% between levels
3. **Higher RSI Tolerance**: Allows buying up to RSI 74 (vs 65)
4. **Lower Volume Requirements**: 51% vs 85% volume ratio
5. **Much Higher Take Profit**: 14% vs 7% target
6. **Wider Stop Loss**: 26.3% vs 10%

### Why It's Failing:
- **Market Conditions**: 40-day period may have been trending down (-6.13% market change)
- **DCA Nature**: Strategy buys into falling knives without proper trend confirmation
- **Exit Strategy**: Even with 14% take profit target, most trades exit at losses
- **Risk/Reward**: Wide stops (26.3%) with low win rate is a losing combination

## Recommendations

### ⚠️ DO NOT USE THESE PARAMETERS IN PRODUCTION

1. **Reconsider DCA Strategy**: The negative performance suggests DCA may not be suitable for crypto's volatile nature without additional filters

2. **Add Trend Filters**: Consider adding:
   - Moving average filters (only DCA above MA200)
   - Market structure confirmation
   - Momentum indicators

3. **Reduce Position Sizing**: With 334 trades and poor performance, consider:
   - Fewer simultaneous positions
   - Smaller grid levels (2-3 instead of 4-5)
   - Higher volume thresholds

4. **Alternative Approaches**:
   - Test on longer timeframes (1h, 4h)
   - Add market regime detection
   - Consider mean reversion only in ranging markets

## Files Generated
- Full results saved to: `user_data/hyperopt_results/strategy_DCAStrategyV1_HO_2025-08-31_20-29-38.fthypt`
- Parameters NOT saved to JSON due to poor performance

## Next Steps
1. Review the strategy logic fundamentally
2. Consider if DCA is appropriate for your risk tolerance
3. Test with additional market filters
4. Run backtests on different market conditions (bull vs bear)
5. Consider focusing on Channel and Swing strategies instead


