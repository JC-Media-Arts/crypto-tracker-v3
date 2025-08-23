#!/bin/bash

# Setup Slack Webhook URLs for Paper Trading Notifications
#
# This script helps you configure the Slack webhook URLs for different channels:
# - #trades: Buy/sell notifications with exit reasons
# - #reports: Daily performance reports
# - #system-alerts: Serious errors and system issues

echo "=========================================="
echo "📢 SLACK WEBHOOK CONFIGURATION"
echo "=========================================="
echo ""
echo "You'll need to create incoming webhooks for each channel:"
echo ""
echo "1. Go to: https://api.slack.com/apps"
echo "2. Create a new app or use existing one"
echo "3. Go to 'Incoming Webhooks' and activate it"
echo "4. Add webhooks for each channel:"
echo "   - #trades"
echo "   - #reports"
echo "   - #system-alerts"
echo ""
echo "=========================================="
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Creating .env file..."
    touch .env
fi

# Function to add or update environment variable
update_env() {
    local key=$1
    local value=$2

    if grep -q "^${key}=" .env; then
        # Update existing
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s|^${key}=.*|${key}=${value}|" .env
        else
            # Linux
            sed -i "s|^${key}=.*|${key}=${value}|" .env
        fi
        echo "✅ Updated ${key}"
    else
        # Add new
        echo "${key}=${value}" >> .env
        echo "✅ Added ${key}"
    fi
}

# Get webhook URLs from user
echo "Enter the webhook URL for #trades channel:"
echo "(This will receive buy/sell notifications with exit reasons)"
read -r TRADES_WEBHOOK

echo ""
echo "Enter the webhook URL for #reports channel:"
echo "(This will receive daily performance reports)"
read -r REPORTS_WEBHOOK

echo ""
echo "Enter the webhook URL for #system-alerts channel:"
echo "(This will receive serious error notifications)"
read -r ALERTS_WEBHOOK

echo ""
echo "Enter a default/fallback webhook URL (optional):"
read -r DEFAULT_WEBHOOK

# Update .env file
echo ""
echo "Updating .env file..."

if [ ! -z "$TRADES_WEBHOOK" ]; then
    update_env "SLACK_WEBHOOK_TRADES" "$TRADES_WEBHOOK"
fi

if [ ! -z "$REPORTS_WEBHOOK" ]; then
    update_env "SLACK_WEBHOOK_REPORTS" "$REPORTS_WEBHOOK"
fi

if [ ! -z "$ALERTS_WEBHOOK" ]; then
    update_env "SLACK_WEBHOOK_SYSTEM_ALERTS" "$ALERTS_WEBHOOK"
fi

if [ ! -z "$DEFAULT_WEBHOOK" ]; then
    update_env "SLACK_WEBHOOK_URL" "$DEFAULT_WEBHOOK"
fi

echo ""
echo "=========================================="
echo "✅ SLACK WEBHOOK CONFIGURATION COMPLETE"
echo "=========================================="
echo ""
echo "Webhooks have been saved to .env file"
echo ""
echo "You can test the notifications by running:"
echo "  python scripts/test_slack_notifications.py"
echo ""
echo "To send a daily report manually:"
echo "  python scripts/send_paper_trading_report.py"
echo ""
echo "The paper trading system will automatically send:"
echo "  - Trade notifications to #trades"
echo "  - Daily reports to #reports (via cron or manual run)"
echo "  - Error alerts to #system-alerts"
echo ""
