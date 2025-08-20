#!/bin/bash

# Setup script for daily materialized view refresh

echo "=========================================="
echo "MATERIALIZED VIEW REFRESH SETUP"
echo "=========================================="

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REFRESH_SCRIPT="$SCRIPT_DIR/refresh_materialized_views.py"

# Make sure the refresh script exists
if [ ! -f "$REFRESH_SCRIPT" ]; then
    echo "❌ Error: refresh_materialized_views.py not found at $REFRESH_SCRIPT"
    exit 1
fi

echo "Setting up daily refresh for materialized views..."
echo ""

# Option 1: Add to crontab
echo "Option 1: Add to crontab (recommended)"
echo "---------------------------------------"
echo "Add this line to your crontab (run 'crontab -e'):"
echo ""
echo "0 2 * * * /usr/bin/python3 $REFRESH_SCRIPT >> $SCRIPT_DIR/../logs/view_refresh.log 2>&1"
echo ""

# Option 2: Create launchd plist for macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Option 2: macOS LaunchAgent (automatic)"
    echo "---------------------------------------"

    PLIST_NAME="com.crypto-tracker.refresh-views"
    PLIST_FILE="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

    cat > /tmp/$PLIST_NAME.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$REFRESH_SCRIPT</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$SCRIPT_DIR/../logs/view_refresh.log</string>
    <key>StandardErrorPath</key>
    <string>$SCRIPT_DIR/../logs/view_refresh_error.log</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
EOF

    echo "Install LaunchAgent? (y/n)"
    read -r response
    if [[ "$response" == "y" ]]; then
        cp /tmp/$PLIST_NAME.plist "$PLIST_FILE"
        launchctl load "$PLIST_FILE"
        echo "✅ LaunchAgent installed and loaded"
        echo "   Views will refresh daily at 2:00 AM"
    fi
fi

# Option 3: Manual refresh
echo ""
echo "Option 3: Manual refresh"
echo "------------------------"
echo "Run manually whenever needed:"
echo "python3 $REFRESH_SCRIPT"
echo ""

# Test the refresh script
echo "Testing refresh script..."
python3 "$REFRESH_SCRIPT" --test 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ Refresh script is working"
else
    echo "⚠️  Refresh script test failed - check configuration"
fi

echo ""
echo "=========================================="
echo "SETUP COMPLETE"
echo "=========================================="
echo ""
echo "Your materialized views are:"
echo "  • ohlc_today  - Last 24 hours (fast)"
echo "  • ohlc_recent - Last 7 days (fast)"
echo ""
echo "They MUST be refreshed daily to stay current!"
echo ""
echo "Choose one of the options above to ensure daily refresh."
