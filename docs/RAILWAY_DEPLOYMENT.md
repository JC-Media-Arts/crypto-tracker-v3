# Railway Deployment Guide

## Prerequisites

1. Railway Pro account (✅ You have this!)
2. GitHub repository connected to Railway
3. Environment variables configured

## Step 1: Connect GitHub Repository

1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose `JC-Media-Arts/crypto-tracker-v3`
5. Railway will automatically detect the configuration

## Step 2: Create Services

Railway will create three services based on our `Procfile`:

### Service 1: Data Collector
- **Purpose**: Collects real-time price data from Polygon.io
- **Resource Usage**: ~200-500MB RAM, low CPU
- **Runs**: 24/7

### Service 2: Feature Calculator
- **Purpose**: Calculates ML features every 2 minutes
- **Resource Usage**: ~500MB RAM, burst CPU
- **Runs**: 24/7

### Service 3: ML Trainer
- **Purpose**: Trains the model daily at 2 AM UTC
- **Resource Usage**: ~1-2GB RAM during training
- **Runs**: Scheduled

## Step 3: Configure Environment Variables

For each service, add these environment variables:

```bash
# Core APIs (Required)
POLYGON_API_KEY=your_actual_key
SUPABASE_URL=your_actual_url
SUPABASE_KEY=your_actual_key

# Slack (Required for notifications)
SLACK_WEBHOOK_URL=your_webhook
SLACK_BOT_TOKEN=your_token

# System Settings
ENVIRONMENT=production
LOG_LEVEL=INFO
TIMEZONE=America/Los_Angeles

# Trading Config
POSITION_SIZE=100
MAX_POSITIONS=5
STOP_LOSS_PCT=5.0
TAKE_PROFIT_PCT=10.0
MIN_CONFIDENCE=0.60
```

## Step 4: Deploy

1. Push your code to GitHub:
   ```bash
   git add .
   git commit -m "Add Railway deployment configuration"
   git push origin main
   ```

2. Railway will automatically:
   - Detect the push
   - Build your application
   - Deploy all three services
   - Start them according to the Procfile

## Step 5: Monitor Services

### View Logs
- Click on each service in Railway dashboard
- Navigate to "Logs" tab
- Watch real-time logs

### Check Metrics
- CPU usage
- Memory usage
- Network I/O
- Restart count

### Set Up Alerts
1. Go to service settings
2. Configure alerts for:
   - High memory usage (>80%)
   - Service crashes
   - High restart frequency

## Step 6: Database Considerations

Since Supabase is external:
- No need to set up database in Railway
- Ensure Supabase connection pooling is configured
- Monitor Supabase dashboard for connection limits

## Troubleshooting

### Service Won't Start
- Check environment variables are set
- Verify Python version (3.9+)
- Check logs for import errors

### WebSocket Disconnections
- Normal for Polygon WebSocket to reconnect
- Monitor frequency of disconnects
- Check Polygon API status

### High Memory Usage
- Feature calculator might accumulate data
- Check for memory leaks in logs
- Consider adding periodic restarts

### Database Connection Errors
- Verify Supabase credentials
- Check connection pool settings
- Monitor Supabase status page

## Scaling Considerations

With Railway Pro, you can:

1. **Horizontal Scaling**: Add replicas if needed
2. **Vertical Scaling**: Increase resources per service
3. **Regional Deployment**: Deploy closer to exchanges

## Cost Optimization

To minimize costs:
1. Use sleep schedules for ML trainer
2. Optimize feature calculation frequency
3. Monitor and adjust resource limits
4. Use Railway's usage alerts

## Next Steps

After deployment:
1. Monitor services for 24 hours
2. Check data flow in Supabase
3. Verify feature calculations
4. Test Slack notifications
5. Prepare for ML model training

## Support

- Railway Discord: https://discord.gg/railway
- Railway Docs: https://docs.railway.app
- Our GitHub Issues: https://github.com/JC-Media-Arts/crypto-tracker-v3/issues
