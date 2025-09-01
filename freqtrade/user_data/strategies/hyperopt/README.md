# Hyperoptable Strategies for Initial Calibration

## ⚠️ IMPORTANT: These are NOT for production use!

These `*_HO.py` strategies are hyperoptable versions designed to find optimal initial parameters through backtesting. After optimization, apply the discovered values to your Admin config and use the production strategies (`../ChannelStrategyV1.py`, etc.) for actual trading.

## Purpose

These strategies serve as a **one-time calibration tool** to:
1. Find mathematically optimal starting parameters
2. Provide data-driven initial values for your Admin config
3. Validate threshold assumptions against historical data

After initial calibration, your ML/Shadow Testing system takes over for continuous optimization.

## Available Strategies

- `ChannelStrategyV1_HO.py` - Bollinger Band channel position trading
- `DCAStrategyV1_HO.py` - Dollar cost averaging on dips
- `SwingStrategyV1_HO.py` - Momentum/breakout trading

## How to Use

### 1. Run Hyperopt for Initial Calibration

```bash
# Navigate to freqtrade directory
cd /Users/justincoit/crypto-tracker-v3/freqtrade

# Activate the virtual environment
source venv/bin/activate

# Run hyperopt for DCA strategy (example)
freqtrade hyperopt \
    --config config/config_webui.json \
    --hyperopt-loss SharpeHyperOptLoss \
    --strategy DCAStrategyV1_HO \
    --timerange 20230901-20240901 \
    --epochs 1000 \
    --spaces buy sell protection \
    --jobs 4

# For SWING strategy
freqtrade hyperopt \
    --config config/config_webui.json \
    --hyperopt-loss SortinoHyperOptLoss \
    --strategy SwingStrategyV1_HO \
    --timerange 20230901-20240901 \
    --epochs 1000 \
    --spaces buy sell protection \
    --jobs 4

# For CHANNEL strategy (uses 5m timeframe - will take longer)
freqtrade hyperopt \
    --config config/config_webui.json \
    --hyperopt-loss CalmarHyperOptLoss \
    --strategy ChannelStrategyV1_HO \
    --timerange 20240601-20240901 \
    --epochs 500 \
    --spaces buy sell protection \
    --jobs 4
```

### 2. Interpret Results

After hyperopt completes, you'll see output like:

```
Best result:
   873/1000:    245 trades. 148/52/45 Wins/Draws/Losses.
   Avg profit   2.31%. Total profit  0.05659 BTC ( 565.95%).
   Avg duration 4:35:00 hours.

   # Buy hyperspace params:
   {   'buy_drop_threshold': -3.25,
       'buy_volume_requirement': 0.92,
       'buy_rsi_min': 28,
       'buy_rsi_max': 68,
       'buy_momentum_score_min': 45
   }
   
   # Sell hyperspace params:
   {   'sell_take_profit': 0.065,
       'sell_rsi_high': 78
   }
   
   # Protection hyperspace params:
   {   'buy_stoploss': -0.055,
       'buy_trailing_stop_positive': 0.018,
       'buy_trailing_stop_positive_offset': 0.032
   }
```

### 3. Apply to Admin Config

Take the optimal values and update your `configs/paper_trading_config_unified.json`:

```json
{
  "strategies": {
    "DCA": {
      "detection_thresholds": {
        "drop_threshold": -3.25,      // From hyperopt
        "volume_requirement": 0.92,    // From hyperopt
        ...
      },
      "exits_by_tier": {
        "mid_cap": {
          "take_profit": 0.065,        // From hyperopt
          "stop_loss": 0.055,          // From hyperopt
          "trailing_stop": 0.018,      // From hyperopt
          ...
        }
      }
    }
  }
}
```

### 4. Optional: Run Per-Tier Optimization

For more granular optimization, run hyperopt with filtered pairs:

```bash
# Create a config for large cap only
cp config/config_webui.json config/config_largecap.json
# Edit whitelist to only include BTC/USDT, ETH/USDT

# Run hyperopt for large caps
freqtrade hyperopt \
    --config config/config_largecap.json \
    --strategy DCAStrategyV1_HO \
    --timerange 20230901-20240901 \
    --epochs 500

# Repeat for other tiers
```

## Hyperopt Parameters Explained

### Loss Functions

- **SharpeHyperOptLoss** - Optimizes risk-adjusted returns (good for DCA)
- **SortinoHyperOptLoss** - Penalizes downside volatility (good for SWING)
- **CalmarHyperOptLoss** - Optimizes return/max drawdown (good for CHANNEL)
- **ProfitDrawDownHyperOptLoss** - Balances profit and drawdown
- **OnlyProfitHyperOptLoss** - Simple profit maximization (not recommended)

### Spaces

- `buy` - Optimizes entry conditions
- `sell` - Optimizes exit conditions
- `protection` - Optimizes stoploss and trailing stop
- `roi` - Optimizes ROI table (disabled in our strategies)

### Other Parameters

- `--epochs` - Number of iterations (more = better results but slower)
- `--jobs` - Parallel jobs (use CPU cores - 1)
- `--timerange` - Date range for backtesting
- `--min-trades` - Minimum trades required (default 1)

## Best Practices

1. **Start with shorter timeranges** for faster iteration
2. **Use different loss functions** to see various perspectives
3. **Run multiple times** - results can vary due to randomness
4. **Validate results** with different timeranges
5. **Don't overfit** - if results seem too good, they probably are

## Integration with ML/Shadow Testing

After applying hyperopt results:

1. Your Admin config has optimized starting values
2. ML/Shadow Testing continuously refines these
3. No need to run hyperopt regularly
4. Can re-run quarterly/yearly as a sanity check

## Troubleshooting

### "No trades found"
- Check your timerange has enough data
- Verify data is synced for that period
- Try loosening parameters (wider ranges)

### "Takes too long"
- Reduce epochs
- Use fewer spaces (e.g., just `buy`)
- Use shorter timerange
- Increase `--jobs` parameter

### "Results vary wildly"
- Normal due to random search
- Run multiple times and average
- Increase epochs for more stability

## Remember

These hyperoptable strategies are **calibration tools**, not production code. Always use the main strategies (`ChannelStrategyV1.py`, etc.) for actual trading, with parameters controlled via your Admin dashboard.
