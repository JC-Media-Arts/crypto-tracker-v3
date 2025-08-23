#!/bin/bash
# Cron-safe strategy runner with lock file to prevent overlaps

LOCKFILE="/tmp/crypto_strategies.lock"
LOGFILE="/Users/justincoit/crypto-tracker-v3/logs/strategy_cron.log"

# Check if already running
if [ -e "$LOCKFILE" ]; then
    # Check if the PID in lockfile is still running
    PID=$(cat "$LOCKFILE")
    if ps -p $PID > /dev/null 2>&1; then
        echo "$(date): Strategies already running with PID $PID, skipping..." >> "$LOGFILE"
        exit 0
    else
        echo "$(date): Removing stale lock file" >> "$LOGFILE"
        rm "$LOCKFILE"
    fi
fi

# Create lock file with current PID
echo $$ > "$LOCKFILE"

# Ensure we remove lock file on exit
trap "rm -f $LOCKFILE" EXIT

cd /Users/justincoit/crypto-tracker-v3

echo "$(date): Starting strategy scan..." >> "$LOGFILE"

# Run the strategies with timeout (4 minutes max to avoid overlap with 5-min cron)
timeout 240 python3 scripts/run_all_strategies.py >> "$LOGFILE" 2>&1

EXIT_CODE=$?

if [ $EXIT_CODE -eq 124 ]; then
    echo "$(date): Strategy scan timed out after 4 minutes" >> "$LOGFILE"
elif [ $EXIT_CODE -eq 0 ]; then
    echo "$(date): Strategy scan completed successfully" >> "$LOGFILE"
else
    echo "$(date): Strategy scan failed with exit code $EXIT_CODE" >> "$LOGFILE"
fi

# Remove lock file
rm -f "$LOCKFILE"
