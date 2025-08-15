# Railway Setup Checklist

## Pre-Deployment Checklist

- [ ] Railway Pro account active ✅
- [ ] GitHub repository pushed with Railway config ✅
- [ ] Environment variables ready
- [ ] Supabase database has tables created
- [ ] Polygon.io API key ready
- [ ] Slack webhook configured

## Railway Setup Steps

### 1. Create New Project
- [ ] Go to https://railway.app/new
- [ ] Click "Deploy from GitHub repo"
- [ ] Select `JC-Media-Arts/crypto-tracker-v3`
- [ ] Railway will detect the Procfile automatically

### 2. Configure Environment Variables
Go to each service's Variables tab and add:

#### Required for ALL services:
- [ ] `POLYGON_API_KEY` = (your key from Polygon.io)
- [ ] `SUPABASE_URL` = (from Supabase project settings)
- [ ] `SUPABASE_KEY` = (anon/public key from Supabase)
- [ ] `ENVIRONMENT` = production
- [ ] `LOG_LEVEL` = INFO

#### Required for notifications:
- [ ] `SLACK_WEBHOOK_URL` = (from Slack app)
- [ ] `SLACK_BOT_TOKEN` = (from Slack app)

#### Trading configuration:
- [ ] `POSITION_SIZE` = 100
- [ ] `MAX_POSITIONS` = 5
- [ ] `STOP_LOSS_PCT` = 5.0
- [ ] `TAKE_PROFIT_PCT` = 10.0
- [ ] `MIN_CONFIDENCE` = 0.60

### 3. Deploy Services
- [ ] Click "Deploy" on each service
- [ ] Wait for build to complete (~2-5 minutes)
- [ ] Check logs for each service

### 4. Verify Deployment

#### Data Collector Service:
- [ ] Check logs show "Successfully authenticated with Polygon"
- [ ] Check logs show "Subscribed to all 99 symbols"
- [ ] Verify no "Maximum connections exceeded" errors

#### Feature Calculator Service:
- [ ] Check logs show "Starting ML Feature Calculator (Production)"
- [ ] Verify it's finding symbols with enough data
- [ ] Check for successful feature calculations

#### ML Trainer Service:
- [ ] Check logs show "Next training scheduled for"
- [ ] Verify it's waiting for 2 AM UTC

### 5. Monitor Initial Performance
- [ ] Check Railway metrics (CPU, Memory, Network)
- [ ] Verify data flowing to Supabase
- [ ] Check for any crash loops
- [ ] Monitor costs in Railway dashboard

### 6. Set Up Monitoring
- [ ] Enable Railway notifications for crashes
- [ ] Set up Slack alerts for critical errors
- [ ] Configure usage alerts if needed

## Post-Deployment Verification

### Database Checks:
```sql
-- Check recent price data
SELECT symbol, COUNT(*) as records, MAX(timestamp) as latest
FROM price_data
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY symbol
ORDER BY symbol;

-- Check ML features
SELECT symbol, COUNT(*) as features, MAX(timestamp) as latest
FROM ml_features
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY symbol
ORDER BY symbol;
```

### Common Issues:

1. **"Module not found" errors**
   - Check requirements.txt is complete
   - Verify Python version compatibility

2. **Database connection errors**
   - Double-check Supabase credentials
   - Ensure tables are created

3. **Polygon WebSocket issues**
   - Verify API key is correct
   - Check you're not running locally too

4. **High memory usage**
   - Normal for initial data collection
   - Should stabilize after ~1 hour

## Success Indicators

✅ All three services show "Deployed" status
✅ No restart loops in first hour
✅ Data flowing to Supabase consistently
✅ Feature calculations running every 2 minutes
✅ Costs tracking within budget (~$10-20/month)

## Next Steps

Once everything is running smoothly:
1. Let system collect data for 24-48 hours
2. Verify feature calculations are working
3. Prepare for first ML model training
4. Set up production monitoring dashboards
