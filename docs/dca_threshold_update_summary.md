# DCA Tiered Threshold Configuration Update

## ✅ Configuration Updated Successfully

**File Updated:** `/configs/paper_trading_config_unified.json`
**Version:** 1.0.15 → 1.0.16

## 📊 New Tiered Entry Thresholds (Aggressive-Leaning for ML)

### DCA Strategy - Detection Thresholds by Market Cap Tier:

| Tier | Drop Threshold | Previous | Volume Req | Previous |
|------|---------------|----------|------------|----------|
| **Large Cap** | **-1.75%** | -3.1% | **0.75x** | 0.85x |
| **Mid Cap** | **-2.25%** | -4.0% | **0.85x** | 0.85x |
| **Small Cap** | **-3.0%** | -4.5% | **0.9x** | 0.8x |
| **Memecoin** | **-4.0%** | -5.0% | **1.1x** | 0.75x |

## 🎯 Expected Impact

### Signal Generation (per week):
- **Large Cap**: ~15-20 signals (BTC, ETH, SOL, etc.)
- **Mid Cap**: ~40-50 signals (LINK, MATIC, DOT, etc.) 
- **Small Cap**: ~10-15 signals (SHIB, DOGE, TRX, APT)
- **Memecoin**: ~15-25 signals (PEPE, WIF, BONK, etc.)
- **Total**: ~80-110 signals/week

### Benefits for ML & Shadow Testing:
1. **30-40% more signals** than conservative approach
2. **More diverse market conditions** captured
3. **Better ML training data** with varied scenarios
4. **Faster feedback loops** for strategy optimization

## 🚀 Next Steps

1. **Deploy to Railway** - The paper trading service will pick up the new config
2. **Monitor Signal Distribution** - Watch for signals across all tiers
3. **Track Performance Metrics**:
   - Completion rate (target >30% in 7 days)
   - Win rate by tier
   - Average hold times
   
## 📈 Adjustment Guidelines

After 1-2 weeks, fine-tune based on results:
- If too many low-quality signals: Increase thresholds by 0.25%
- If too few signals in a tier: Decrease threshold by 0.25%
- If memecoins too noisy: Increase to -4.5% or -5.0%

The configuration is now live and ready for deployment!
