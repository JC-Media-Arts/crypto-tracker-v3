# Deployment Options for Crypto Tracker V3

## Current Issue
Running data collection and ML services locally on macOS has limitations:
- Computer must stay awake 24/7
- No redundancy if computer crashes
- Internet/power outages affect data collection
- Not scalable for production trading

## Recommended Cloud Solutions

### 1. **AWS EC2** (Recommended for Phase 1)
**Cost**: ~$20-40/month for t3.small instance

```bash
# Quick setup on AWS EC2
1. Launch Ubuntu t3.small instance
2. Clone your repo
3. Install Python and dependencies
4. Use systemd services for auto-restart
5. Use tmux/screen for persistent sessions
```

**Pros**:
- Full control over environment
- Easy to scale up
- Good for learning DevOps
- Can run Docker

**Cons**:
- Requires server management
- Need to handle updates/security

### 2. **Railway.app** (Easiest)
**Cost**: ~$5-20/month

```yaml
# railway.json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python scripts/run_data_collector.py"
  }
}
```

**Pros**:
- Zero DevOps required
- Auto-deploys from GitHub
- Built-in monitoring
- Easy environment variables

**Cons**:
- Less control
- May need multiple services

### 3. **Render.com** (Good Alternative)
**Cost**: ~$7/month per service

**Pros**:
- Similar to Railway
- Good free tier
- Background workers supported
- Auto-scaling available

### 4. **DigitalOcean Droplet**
**Cost**: ~$6-12/month

**Pros**:
- Simple, developer-friendly
- Good documentation
- Predictable pricing

### 5. **Google Cloud Run** (For Scheduled Jobs)
**Cost**: Pay per execution

**Good for**:
- Feature calculation (runs every 2 min)
- Model training (runs daily)
- Not ideal for WebSocket connections

## Immediate Solution (Keep Mac Running)

If you need to keep using your Mac for now:

1. **Disable Sleep**:
   ```bash
   # System Preferences > Energy Saver
   # Set "Computer sleep" to Never
   # Or use: sudo pmset -a sleep 0
   ```

2. **Use tmux for persistence**:
   ```bash
   # Install tmux
   brew install tmux
   
   # Create new session
   tmux new -s crypto
   
   # Run your services
   python scripts/run_data_collector.py
   
   # Detach with Ctrl+B, then D
   # Reattach with: tmux attach -t crypto
   ```

3. **Enable auto-login and auto-start**:
   - System Preferences > Users & Groups > Login Options
   - Set automatic login
   - Add terminal to Login Items

## Production Architecture (Phase 2)

```
┌─────────────────┐     ┌─────────────────┐
│   Data Collector│     │ Feature Calculator│
│   (AWS EC2)     │     │  (AWS Lambda)     │
└────────┬────────┘     └────────┬─────────┘
         │                       │
         ▼                       ▼
    ┌────────────────────────────────┐
    │        Supabase Database       │
    └────────────────┬───────────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
    ┌─────────────┐       ┌──────────────┐
    │ ML Training │       │  Hummingbot  │
    │ (Scheduled) │       │ (Container)  │
    └─────────────┘       └──────────────┘
```

## Next Steps

1. **For Testing**: Keep using Mac with sleep disabled
2. **For Development**: Set up Railway.app for easy deployment
3. **For Production**: Move to AWS EC2 with proper monitoring

## Migration Commands

```bash
# Export current data
python scripts/export_data.py

# On new server
git clone https://github.com/JC-Media-Arts/crypto-tracker-v3.git
cd crypto-tracker-v3
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your keys
python scripts/import_data.py
python scripts/run_data_collector.py
```
