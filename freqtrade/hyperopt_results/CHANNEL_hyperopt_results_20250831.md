# Channel Strategy Hyperopt Results
**Date**: August 31, 2025  
**Runtime**: 9 minutes 7 seconds  
**Epochs**: 3000  
**Data Period**: July 22, 2025 - August 31, 2025 (40 days)  
**Timeframe**: 5 minutes  
**Loss Function**: CalmarHyperOptLoss  

## Performance Summary
- **Total Trades**: 57
- **Win/Draw/Loss**: 40/0/17 (70.2% win rate)
- **Average Profit per Trade**: 0.40%
- **Median Profit**: 0.53%
- **Total Profit**: 15.30 USDT (0.15% of 10,000 USDT starting balance)
- **Average Trade Duration**: 3 hours 33 minutes
- **Max Drawdown**: 10.20 USDT (0.10%)
- **Objective Score**: -73.62 (lower is better for CalmarHyperOptLoss)

## Optimized Parameters

### Buy Parameters
```python
buy_params = {
    "buy_bb_period": 30,                    # Bollinger Band period (default: 20)
    "buy_bb_std": 2.0,                      # Bollinger Band std dev (default: 2.0)
    "buy_channel_entry_threshold": 0.1,      # Channel position threshold (default: 0.15)
    "buy_price_drop_min": -8.9,             # Min price drop percentage (default: -2.0)
    "buy_rsi_max": 65,                       # Max RSI for entry (default: 65)
    "buy_rsi_min": 32,                       # Min RSI for entry (default: 35)
    "buy_volatility_max": 0.03,             # Max volatility threshold (default: 0.05)
    "buy_volume_ratio_min": 1.0,            # Min volume ratio (default: 0.8)
}
```

### Sell Parameters
```python
sell_params = {
    "sell_channel_exit_threshold": 0.94,    # Channel exit position (default: 0.85)
    "sell_rsi_high": 72,                     # RSI high threshold (default: 75)
    "sell_take_profit": 0.04,               # Take profit percentage (default: 0.05)
}
```

### Risk Management
```python
# Stoploss
stoploss = -0.146  # 14.6% stoploss (default: -0.10)

# Trailing stop
trailing_stop = True
trailing_stop_positive = 0.222           # Start trailing at 22.2% profit
trailing_stop_positive_offset = 0.248    # Trail by 24.8% from peak
trailing_only_offset_is_reached = True
```

## Key Insights

### What Changed from Defaults:
1. **More Conservative Entry**: 
   - Requires larger price drop (-8.9% vs -2.0%)
   - Tighter channel entry (0.1 vs 0.15)
   - Lower RSI minimum (32 vs 35)
   - Higher volume requirement (1.0 vs 0.8)

2. **Later Exit Strategy**:
   - Higher channel exit threshold (0.94 vs 0.85) - waits for stronger moves
   - Slightly lower RSI exit (72 vs 75)
   - Lower take profit (4% vs 5%)

3. **Wider Risk Tolerance**:
   - Larger stoploss (14.6% vs 10%)
   - Much higher trailing stop activation (22.2% vs default)
   - Aggressive trailing offset (24.8%)

### Strategy Characteristics:
- **Patient Entry**: Waits for significant dips and oversold conditions
- **Momentum Exit**: Holds positions longer, riding trends
- **Risk Management**: Accepts larger drawdowns but protects big wins with trailing stops
- **Lower Frequency**: Fewer trades (57 in 40 days = ~1.4 per day across all pairs)

## Files Generated
- Strategy parameters saved to: `user_data/strategies/hyperopt/ChannelStrategyV1_HO.json`
- Full results saved to: `user_data/hyperopt_results/strategy_ChannelStrategyV1_HO_2025-08-31_20-16-32.fthypt`

## Next Steps
1. Test these parameters in dry-run mode
2. Compare with your current manual settings
3. Consider the trade-off between win rate (70.2%) and average profit (0.40%)
4. Run longer backtests with more historical data if available
