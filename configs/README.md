# Configuration Files

## paper_trading.json

This is the **single source of truth** for all trading strategy configurations.

### Key Sections:

#### 1. Strategy Exit Thresholds
Each strategy (DCA, SWING, CHANNEL) has exit thresholds defined by market cap tier:
- **large_cap**: BTC, ETH, and other major coins
- **mid_cap**: SOL, LINK, ATOM, etc.
- **small_cap**: All other coins

Example for CHANNEL strategy (conservative thresholds):
```json
"CHANNEL": {
  "exits_by_tier": {
    "large_cap": {
      "take_profit": 0.015,   // 1.5%
      "stop_loss": 0.02,      // 2%
      "trailing_stop": 0.005  // 0.5%
    }
  }
}
```

#### 2. Market Cap Tiers
Define which symbols belong to each tier:
```json
"market_cap_tiers": {
  "large_cap": ["BTC", "ETH", "BNB", ...],
  "mid_cap": ["LINK", "MATIC", "ATOM", ...]
}
```

#### 3. Fees and Slippage
Configure exchange fees and slippage by market cap:
```json
"fees": {
  "kraken_taker": 0.0026  // 0.26%
},
"slippage_rates": {
  "large": 0.0008,  // 0.08%
  "mid": 0.0015,    // 0.15%
  "small": 0.0035   // 0.35%
}
```

### How to Update Thresholds:

1. Edit the appropriate strategy section under `strategies`
2. Update the `exits_by_tier` for your target market cap tier
3. Restart the paper trading system to apply changes

**Note**: Changes only affect NEW positions. Existing positions keep their original thresholds.

### Recent Changes (January 2025):

- Applied conservative thresholds to CHANNEL strategy based on backtest analysis
- CHANNEL was experiencing 99% loss rate with previous thresholds
- New conservative thresholds designed to capture profits before reversals
