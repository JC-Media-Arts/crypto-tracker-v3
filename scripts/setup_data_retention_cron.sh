#!/bin/bash
# Setup daily data retention cleanup cron job
# Runs at 3 AM PST every day

echo "📊 Setting up Data Retention Cron Job"
echo "======================================"

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Create log directory if it doesn't exist
mkdir -p "$PROJECT_DIR/logs/retention"

# Create the cron script
cat > "$PROJECT_DIR/scripts/run_data_cleanup.sh" << 'EOF'
#!/bin/bash
# Daily data cleanup runner

# Set up environment
export PATH="/usr/local/bin:/usr/bin:/bin"
cd /Users/justincoit/crypto-tracker-v3

# Load environment variables
source venv/bin/activate 2>/dev/null || true
export $(cat .env | grep -v '^#' | xargs)

# Run cleanup with logging
LOG_FILE="logs/retention/cleanup_$(date +%Y%m%d_%H%M%S).log"
echo "Starting data cleanup at $(date)" >> "$LOG_FILE"

python3 scripts/daily_data_cleanup.py >> "$LOG_FILE" 2>&1

echo "Cleanup completed at $(date)" >> "$LOG_FILE"

# Keep only last 30 days of logs
find logs/retention -name "cleanup_*.log" -mtime +30 -delete
EOF

# Make the script executable
chmod +x "$PROJECT_DIR/scripts/run_data_cleanup.sh"

# Add to crontab (3 AM PST = 11 AM UTC)
CRON_JOB="0 11 * * * $PROJECT_DIR/scripts/run_data_cleanup.sh"

# Check if cron job already exists
crontab -l 2>/dev/null | grep -q "run_data_cleanup.sh"
if [ $? -eq 0 ]; then
    echo "⚠️  Cron job already exists. Updating..."
    # Remove old entry and add new one
    (crontab -l 2>/dev/null | grep -v "run_data_cleanup.sh"; echo "$CRON_JOB") | crontab -
else
    echo "✅ Adding new cron job..."
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
fi

echo ""
echo "✅ Data retention cron job setup complete!"
echo ""
echo "Schedule: Daily at 3 AM PST (11 AM UTC)"
echo "Script: $PROJECT_DIR/scripts/run_data_cleanup.sh"
echo "Logs: $PROJECT_DIR/logs/retention/"
echo ""
echo "To view current crontab:"
echo "  crontab -l"
echo ""
echo "To run manually:"
echo "  ./scripts/run_data_cleanup.sh"
echo ""
echo "To check last run:"
echo "  ls -la logs/retention/ | tail -5"
