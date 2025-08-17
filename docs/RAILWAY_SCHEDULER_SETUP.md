# Railway Data Scheduler Setup Guide

## Overview
The Data Scheduler service runs continuously on Railway and manages all OHLC data updates automatically.

## Deployment Steps

### 1. Create New Service in Railway

1. Go to your Railway project dashboard
2. Click "New Service"
3. Select "GitHub Repo" 
4. Choose your `crypto-tracker-v3` repository
5. Name the service: "Data Scheduler"

### 2. Configure Environment Variables

Add these environment variables to the new service:

```bash
# Required - Identifies this as the scheduler service
SERVICE_TYPE=data_scheduler

# Copy these from your existing services
POLYGON_API_KEY=your_polygon_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# Optional - for Slack alerts (if configured)
SLACK_WEBHOOK_URL=your_slack_webhook_url

# Timezone (optional, defaults to UTC)
TZ=America/Los_Angeles
```

### 3. Deploy Settings

Railway should automatically detect and use:
- **Builder**: Heroku buildpack (same as other services)
- **Start Command**: Automatically uses `start.py`
- **Runtime**: Python 3.11.9 (from runtime.txt)

### 4. Verify Deployment

After deployment, check the logs to confirm:
1. "Starting Data Scheduler Service on Railway" appears
2. "Scheduled 1m: every_5_minutes" and other schedules are logged
3. "Running initial updates..." shows the service is working

## Update Schedule

The scheduler will automatically run:

| Timeframe | Frequency | Time |
|-----------|-----------|------|
| 1-minute | Every 5 minutes | :00, :05, :10, :15, etc |
| 15-minute | Every 15 minutes | :00, :15, :30, :45 |
| 1-hour | Every hour | :05 past the hour |
| 1-day | Daily | 12:05 AM PST |
| Gap Check | Daily | 1:00 AM PST |
| Health Check | Every 30 minutes | :00, :30 |

## Monitoring

### Check Service Health
1. View logs in Railway dashboard
2. Look for successful update messages
3. Monitor for any error messages

### Database Verification
Check the `pipeline_runs` table in Supabase to see update history:
```sql
SELECT * FROM pipeline_runs 
ORDER BY started_at DESC 
LIMIT 10;
```

### Manual Testing
To test a specific update manually:
```bash
# SSH into Railway service (if needed) or run locally
python3 scripts/incremental_ohlc_updater.py --timeframe 1m --symbols BTC
```

## Troubleshooting

### Service Not Starting
- Check SERVICE_TYPE is set to "data_scheduler"
- Verify all required environment variables are set
- Check Railway logs for specific error messages

### Updates Not Running
- Check if service is running (green status in Railway)
- Verify Polygon API key is valid
- Check Supabase connection
- Look for rate limiting errors in logs

### Data Gaps
- The scheduler includes automatic gap detection and healing
- Gaps are checked daily at 1 AM PST
- Check `data_gaps` table for unhealed gaps

## Cost Considerations

This service runs 24/7, so it will use:
- **CPU**: Minimal (mostly idle between updates)
- **Memory**: ~256-512 MB
- **Network**: Moderate (API calls every 5 minutes)

Estimated Railway cost: ~$5-10/month

## Maintenance

### Stopping the Service
- Click "Remove" in Railway dashboard to stop
- Or set replicas to 0 to pause temporarily

### Updating Schedule
- Modify `scripts/schedule_updates.py`
- Push to GitHub
- Railway will auto-deploy changes

### Adding New Symbols
- Update symbol list in `scripts/incremental_ohlc_updater.py`
- The scheduler will automatically include them in next update

## Integration with Existing Services

The scheduler works alongside your existing services:
- **Data Collector**: Handles real-time WebSocket data
- **Feature Calculator**: Computes technical indicators
- **ML Trainer**: Trains models
- **Data Scheduler**: Ensures historical data completeness

All services share the same Supabase database and work together seamlessly.

## Success Metrics

After 24 hours, you should see:
- ~288 successful 1-minute updates (every 5 min)
- ~96 successful 15-minute updates (every 15 min)
- ~24 successful hourly updates
- 1 successful daily update
- 0 data gaps for active trading hours
- Data freshness < 10 minutes for all symbols

## Next Steps

1. Deploy the service to Railway
2. Monitor logs for first few update cycles
3. Verify data is being updated in Supabase
4. Set up Slack alerts for critical issues (optional)
5. Let it run continuously to maintain data pipeline

The scheduler is designed to be "set and forget" - once deployed, it will maintain your data pipeline automatically!
