# Railway Cron Job Setup for Daily Model Retraining

## Overview
This guide explains how to set up the daily model retraining as a cron job on Railway.

## Railway Configuration Options

### Option 1: Separate Cron Service (RECOMMENDED)
Create a dedicated Railway service just for the cron job.

#### Steps:
1. **In Railway Dashboard:**
   - Go to your project
   - Click "New Service"
   - Select "GitHub Repo"
   - Choose your `crypto-tracker-v3` repository

2. **Configure the Service:**
   - Name: `ML Retrainer Cron`
   - Set Start Command: `python scripts/railway_retrainer.py`
   
3. **Add Cron Schedule:**
   - Go to Settings → Cron
   - Enable "Cron Schedule"
   - Set Schedule: `0 9 * * *` (2 AM PST = 9 AM UTC)
   - Or use: `0 2 * * *` if Railway uses your local timezone

4. **Configure Environment:**
   - Copy all environment variables from your main service
   - Especially: `SUPABASE_URL`, `SUPABASE_KEY`, `SLACK_WEBHOOK_*`

5. **Set Resource Limits:**
   - CPU: 1 vCPU
   - Memory: 512 MB
   - Execution timeout: 10 minutes

### Option 2: Add to Existing Service
Add cron functionality to your existing paper trading service.

#### In Railway:
1. Go to your existing service
2. Settings → Cron
3. Add cron schedule: `0 9 * * *`
4. Modify start command to handle both modes

### Option 3: Use Railway's Scheduled Jobs (Beta)
Railway now supports scheduled jobs as a first-class feature.

## Cron Schedule Formats

```
# Daily at 2 AM PST (9 AM UTC)
0 9 * * *

# Daily at 2 AM in your Railway project timezone
0 2 * * *

# Every 6 hours
0 */6 * * *

# Weekdays only at 2 AM
0 2 * * 1-5
```

## Environment Variables Required

```bash
# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# Slack (for notifications)
SLACK_WEBHOOK_REPORTS=your_reports_webhook
SLACK_WEBHOOK_ALERTS=your_alerts_webhook

# Railway-specific
RAILWAY_ENVIRONMENT=production
TZ=America/Los_Angeles  # Set timezone
```

## Monitoring & Logs

### View Logs:
```bash
# In Railway Dashboard
Services → ML Retrainer Cron → Logs

# Or via Railway CLI
railway logs -s "ML Retrainer Cron"
```

### Check Last Run:
- Railway shows last execution time in the service dashboard
- Check Slack #reports channel for notifications
- Query database: `SELECT * FROM last_train.json`

## Testing Locally

Before deploying to Railway:

```bash
# Test the script locally
python scripts/railway_retrainer.py

# Test with Railway environment
railway run python scripts/railway_retrainer.py
```

## Deployment Steps

1. **Commit changes:**
```bash
git add .
git commit -m "Add Railway cron job for daily model retraining"
git push origin main
```

2. **Railway will automatically:**
   - Detect the new configuration
   - Create the cron service
   - Schedule it to run at 2 AM daily

3. **Verify setup:**
   - Check Railway dashboard for the new service
   - Confirm cron schedule is set
   - Monitor first execution in logs

## Troubleshooting

### Cron not running?
- Check timezone settings
- Verify environment variables
- Check Railway service logs for errors

### Models not updating?
- Need 20+ completed trades
- Check `python scripts/run_daily_retraining.py --check`
- Verify database connectivity

### Slack notifications not working?
- Verify SLACK_WEBHOOK_REPORTS is set
- Check Railway logs for notification errors

## Manual Trigger

To manually trigger the retrainer from Railway:

1. Go to your cron service
2. Click "Deploy" → "Trigger Deploy"
3. Or use Railway CLI: `railway run python scripts/railway_retrainer.py`

## Cost Considerations

- Cron jobs consume compute minutes only when running
- Daily retraining typically takes < 1 minute
- Monthly cost: ~30 minutes of compute time
- Estimated: < $0.50/month

## Next Steps

1. Deploy to Railway
2. Monitor first automatic run at 2 AM
3. Check Slack for completion notification
4. Verify models are improving over time
