# 🔬 Shadow Testing System Deployment Guide

## Overview
The Shadow Testing system runs 8 parallel variations of your trading strategies to accelerate learning without risk. This guide covers testing, deployment, and monitoring.

## 📋 Pre-Deployment Checklist

### 1. Database Setup
- [ ] Run migration `006_create_shadow_testing.sql` in Supabase
- [ ] Verify all tables created (shadow_variations, shadow_outcomes, etc.)
- [ ] Confirm views are accessible (champion_vs_challengers, etc.)
- [ ] Test functions work (get_shadows_ready_for_evaluation)

### 2. Configuration
- [ ] Update `.env` with `ENABLE_SHADOW_TESTING=true`
- [ ] Set `SHADOW_EVALUATION_INTERVAL=300` (5 minutes)
- [ ] Configure `SHADOW_ADJUSTMENT_HOUR=2` (2 AM PST)
- [ ] Verify Slack webhooks are configured

### 3. Testing
```bash
# Run comprehensive tests
python scripts/test_shadow_system.py

# Quick configuration test
python scripts/test_shadow_system.py --quick

# Test Slack integration
python scripts/shadow_slack_reporter.py --test
```

## 🚀 Deployment Options

### Option 1: Local Development
```bash
# Run shadow services locally
python scripts/run_shadow_services.py

# View dashboard
python scripts/shadow_dashboard.py --live

# Send test summary
python scripts/shadow_slack_reporter.py --summary
```

### Option 2: Railway Deployment

1. **Create New Service in Railway**
   - Name: `shadow-evaluator`
   - Source: Your GitHub repo
   - Branch: main

2. **Configure Environment Variables**
   ```
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   POLYGON_API_KEY=your_polygon_key
   SLACK_WEBHOOK_URL=your_webhook
   ENABLE_SHADOW_TESTING=true
   SHADOW_EVALUATION_INTERVAL=300
   SHADOW_ADJUSTMENT_HOUR=2
   LOG_LEVEL=INFO
   ```

3. **Set Start Command**
   ```
   python scripts/run_shadow_services.py
   ```

4. **Deploy**
   - Push to GitHub
   - Railway auto-deploys
   - Monitor logs for startup confirmation

### Option 3: Integration with Existing Services

Add shadow logging to your existing paper trader:

```python
# In run_paper_trading.py, add:
from src.analysis.shadow_logger import ShadowLogger

# After each scan, log shadow decisions:
shadow_decisions = await shadow_logger.log_shadow_decisions(
    scan_id=scan_id,
    symbol=symbol,
    strategy_name=strategy,
    features=features,
    ml_predictions=predictions,
    ml_confidence=confidence,
    current_price=price,
    base_parameters=params
)
```

## 📊 Monitoring

### Dashboard Commands
```bash
# Live dashboard (updates every 60s)
python scripts/shadow_dashboard.py --live

# One-time summary
python scripts/shadow_dashboard.py

# Specific timeframe analysis
python -c "
from scripts.shadow_dashboard import ShadowDashboard
import asyncio
d = ShadowDashboard()
asyncio.run(d.print_summary())
"
```

### Slack Notifications
Daily at 2 AM PST, you'll receive:
- Champion vs Challengers performance
- Top 3 recommendations
- Recent adjustments
- ML retraining results

### Database Queries
```sql
-- Current champion performance
SELECT * FROM shadow_performance 
WHERE variation_name = 'CHAMPION' 
AND timeframe = '24h'
AND strategy_name = 'OVERALL';

-- Best challengers
SELECT * FROM champion_vs_challengers
WHERE timeframe = '7d'
ORDER BY outperformance_vs_champion DESC
LIMIT 5;

-- Recent adjustments
SELECT * FROM threshold_adjustments
WHERE adjusted_at > NOW() - INTERVAL '24 hours'
ORDER BY adjusted_at DESC;

-- Shadow consensus for recent scans
SELECT * FROM shadow_consensus
WHERE scan_id IN (
    SELECT scan_id FROM scan_history 
    WHERE timestamp > NOW() - INTERVAL '1 hour'
);
```

## 🛡️ Safety Controls

### Automatic Rollbacks
The system automatically rolls back adjustments if:
- Win rate drops >15% in 24 hours
- 3 consecutive losses after adjustment
- Underperformance for 48 hours

### Manual Controls
```python
# Emergency stop all adjustments
from src.trading.threshold_manager import ThresholdManager
tm = ThresholdManager(supabase_client)
await tm.emergency_stop("Manual intervention")

# Rollback specific adjustment
await tm.rollback_adjustment(adjustment_id=123, reason="Manual rollback")

# Disable shadow testing
os.environ['ENABLE_SHADOW_TESTING'] = 'false'
```

### Adjustment Limits
- Maximum 3 adjustments per day
- Maximum 5% change for confidence thresholds
- Maximum 20% change for stop losses
- Maximum 30% change for position sizes
- No adjustments during unstable market regimes

## 📈 Performance Metrics

### Expected Outcomes
- **Week 1**: 1,000+ shadow trades evaluated
- **Week 2**: First optimal parameters discovered
- **Month 1**: 20-30% win rate improvement
- **Month 3**: Fully optimized per-strategy thresholds

### Key Metrics to Track
1. **Shadow Consensus Score**: % of shadows agreeing with production
2. **Outperformance Rate**: Best challenger vs champion
3. **Adjustment Success Rate**: % of adjustments improving performance
4. **ML Model Improvement**: AUC increase from shadow data

## 🔧 Troubleshooting

### Common Issues

1. **No shadow trades being evaluated**
   - Check if shadow_variations has would_take_trade = true entries
   - Verify OHLC data is available for symbols
   - Ensure 5+ minutes have passed since shadow creation

2. **Recommendations not generating**
   - Need minimum 30 completed shadow trades
   - Check if any variation outperforming champion
   - Verify statistical significance (p < 0.10)

3. **Adjustments not applying**
   - Check market regime stability (12 hours)
   - Verify daily limit not reached (3 max)
   - Ensure minimum real trades (5+)

4. **Slack notifications not sending**
   - Verify SLACK_WEBHOOK_URL is set
   - Check webhook mapping in slack_notifier.py
   - Test with: `python scripts/shadow_slack_reporter.py --test`

### Debug Commands
```bash
# Check shadow evaluation
python -c "
from src.analysis.shadow_evaluator import ShadowEvaluator
from src.data.supabase_client import SupabaseClient
import asyncio
s = SupabaseClient()
e = ShadowEvaluator(s.client)
outcomes = asyncio.run(e.evaluate_pending_shadows())
print(f'Evaluated {len(outcomes)} shadows')
"

# Check recommendations
python -c "
from src.analysis.shadow_analyzer import ShadowAnalyzer
from src.data.supabase_client import SupabaseClient
import asyncio
s = SupabaseClient()
a = ShadowAnalyzer(s.client)
recs = asyncio.run(a.generate_recommendations())
for r in recs:
    print(f'{r.strategy_name}.{r.parameter_name}: {r.current_value} → {r.recommended_value}')
"

# Force threshold adjustment (bypass safety)
python -c "
from src.trading.threshold_manager import ThresholdManager
from src.data.supabase_client import SupabaseClient
import asyncio
s = SupabaseClient()
tm = ThresholdManager(s.client)
# ... create recommendation ...
results = asyncio.run(tm.process_recommendations([rec], force=True))
"
```

## 📚 Architecture Summary

```
┌─────────────────────────────────────────────────────────┐
│                    Production System                      │
│  (Paper Trader → Scans → Trades → ML Models)            │
└────────────────────┬───────────────────────────────────┘
                      │
                      ▼ Every Scan
┌─────────────────────────────────────────────────────────┐
│                   Shadow Logger                           │
│  Records what 8 variations would do for each scan        │
└────────────────────┬───────────────────────────────────┘
                      │
                      ▼ Every 5 min
┌─────────────────────────────────────────────────────────┐
│                  Shadow Evaluator                         │
│  Evaluates outcomes using actual price data              │
│  Full DCA grid simulation, dynamic TP/SL detection       │
└────────────────────┬───────────────────────────────────┘
                      │
                      ▼ Every 3 hours
┌─────────────────────────────────────────────────────────┐
│                 Shadow Analyzer                           │
│  Calculates performance, generates recommendations        │
└────────────────────┬───────────────────────────────────┘
                      │
                      ▼ Daily 2 AM
┌─────────────────────────────────────────────────────────┐
│           Threshold Manager + ML Retrainer                │
│  Applies adjustments with safety controls                 │
│  Retrains models with weighted shadow data               │
└────────────────────┬───────────────────────────────────┘
                      │
                      ▼ Continuous
┌─────────────────────────────────────────────────────────┐
│              Monitoring & Rollbacks                       │
│  Dashboard, Slack alerts, automatic rollbacks            │
└─────────────────────────────────────────────────────────┘
```

## 🎯 Success Criteria

The shadow testing system is working correctly when:
1. ✅ 100+ shadow trades evaluated daily
2. ✅ All 8 variations showing in dashboard
3. ✅ Daily Slack summaries arriving at 2 AM
4. ✅ Recommendations generating after 3 days
5. ✅ ML models retraining with shadow data
6. ✅ Win rate improving over time
7. ✅ Automatic rollbacks triggering when needed

## 📞 Support

For issues or questions:
1. Check logs in Railway dashboard
2. Query database views for current state
3. Run test script for diagnostics
4. Review this documentation

---

*Shadow Testing System v1.0 - Accelerating learning through parallel evaluation*
