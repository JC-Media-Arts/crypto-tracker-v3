# Freqtrade Railway Deployment Guide

## Quick Deploy to Railway

### 1. Push to GitHub
```bash
cd /Users/justincoit/crypto-tracker-v3
git add freqtrade/
git commit -m "Add Freqtrade with Docker setup for Railway deployment"
git push origin main
```

### 2. Create New Railway Service

1. Go to your Railway dashboard
2. Click "New Service"
3. Select "GitHub Repo"
4. Choose `crypto-tracker-v3` repository
5. Set the **Root Directory** to: `freqtrade`
6. Railway will auto-detect the Dockerfile

### 3. Configure Environment Variables

In Railway service settings, add these variables:

```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
TRADING_MODE=dry_run
PORT=8080
```

### 4. Deploy

Railway will automatically:
- Build the Docker image
- Install Freqtrade and dependencies
- Start the service
- Monitor health via API endpoint

## Service Details

- **Name**: Freqtrade Trading Engine
- **Type**: Docker container
- **Health Check**: `http://localhost:8080/api/v1/ping`
- **Logs**: Available in Railway dashboard
- **Restart Policy**: Auto-restart on failure (max 3 retries)

## What It Does

Once deployed, Freqtrade will:
1. Connect to Kraken for market data (dry-run mode)
2. Scan 13 cryptocurrency pairs every hour
3. Log all scan decisions to Supabase `scan_history` table
4. Execute paper trades in dry-run mode
5. Provide API access for monitoring

## Monitoring

### Check Service Health
```bash
curl https://your-service.railway.app/api/v1/ping
```

### View Logs
- Railway Dashboard → Service → Logs
- Or use Railway CLI: `railway logs`

### Database Verification
Check scan_history table in Supabase:
- Should see new CHANNEL strategy scans every hour
- Features logged for ML training
- Decisions (TAKE/SKIP) recorded

## Troubleshooting

### Service Won't Start
- Check environment variables are set
- Verify Supabase credentials
- Check Railway logs for errors

### No Scans in Database
- Verify SUPABASE_URL and SUPABASE_KEY
- Check scan_logger initialization in logs
- Ensure scan_history table exists

### API Not Responding
- Check PORT is set to 8080
- Verify health check endpoint
- Check firewall/network settings

## Next Steps

After successful deployment:
1. Monitor scan_history table for data collection
2. Verify scans are being logged every hour
3. Set up alerts for service downtime
4. Consider adding Telegram notifications
