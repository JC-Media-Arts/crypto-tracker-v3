#!/bin/bash

# Script to create LaunchDaemons for crypto-tracker services

PROJECT_DIR="/Users/justincoit/crypto-tracker-v3"
PYTHON_PATH="/Users/justincoit/crypto-tracker-v3/venv/bin/python"

echo "Creating LaunchDaemon for Data Collector..."

# Create Data Collector plist
cat > ~/Library/LaunchAgents/com.cryptotracker.datacollector.plist <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cryptotracker.datacollector</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON_PATH}</string>
        <string>${PROJECT_DIR}/scripts/run_data_collector.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${PROJECT_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${PROJECT_DIR}/logs/datacollector.log</string>
    <key>StandardErrorPath</key>
    <string>${PROJECT_DIR}/logs/datacollector.error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
EOF

echo "Creating LaunchDaemon for Feature Calculator..."

# Create Feature Calculator plist
cat > ~/Library/LaunchAgents/com.cryptotracker.featurecalculator.plist <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cryptotracker.featurecalculator</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON_PATH}</string>
        <string>${PROJECT_DIR}/scripts/run_feature_calculator_dev.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${PROJECT_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${PROJECT_DIR}/logs/featurecalculator.log</string>
    <key>StandardErrorPath</key>
    <string>${PROJECT_DIR}/logs/featurecalculator.error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
EOF

echo "Loading services..."
launchctl load ~/Library/LaunchAgents/com.cryptotracker.datacollector.plist
launchctl load ~/Library/LaunchAgents/com.cryptotracker.featurecalculator.plist

echo "Services created and started!"
echo ""
echo "Useful commands:"
echo "  Check status: launchctl list | grep cryptotracker"
echo "  Stop service: launchctl unload ~/Library/LaunchAgents/com.cryptotracker.datacollector.plist"
echo "  Start service: launchctl load ~/Library/LaunchAgents/com.cryptotracker.datacollector.plist"
echo "  View logs: tail -f ${PROJECT_DIR}/logs/datacollector.log"
