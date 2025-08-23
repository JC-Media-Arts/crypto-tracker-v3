#!/bin/bash

# Setup Daily Paper Trading Report Cron Job
# Sends a daily report to Slack #reports channel

echo "=========================================="
echo "📅 SETUP DAILY REPORT CRON JOB"
echo "=========================================="
echo ""

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Check if virtual environment exists
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo "❌ Virtual environment not found at $PROJECT_DIR/venv"
    echo "Please create it first with: python3 -m venv venv"
    exit 1
fi

# Create the cron command
CRON_CMD="cd $PROJECT_DIR && source venv/bin/activate && python scripts/send_paper_trading_report.py >> logs/daily_report.log 2>&1"

echo "Select when to send the daily report:"
echo "1) 9:00 AM (local time)"
echo "2) 12:00 PM (local time)"
echo "3) 6:00 PM (local time)"
echo "4) 9:00 PM (local time)"
echo "5) Custom time"
read -p "Enter choice (1-5): " choice

case $choice in
    1)
        CRON_TIME="0 9"
        TIME_DESC="9:00 AM"
        ;;
    2)
        CRON_TIME="0 12"
        TIME_DESC="12:00 PM"
        ;;
    3)
        CRON_TIME="0 18"
        TIME_DESC="6:00 PM"
        ;;
    4)
        CRON_TIME="0 21"
        TIME_DESC="9:00 PM"
        ;;
    5)
        read -p "Enter hour (0-23): " hour
        read -p "Enter minute (0-59): " minute
        CRON_TIME="$minute $hour"
        TIME_DESC="${hour}:${minute}"
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

# Full cron line
CRON_LINE="$CRON_TIME * * * $CRON_CMD"

echo ""
echo "This will add the following cron job:"
echo "$CRON_LINE"
echo ""
echo "This will run the daily report at $TIME_DESC every day"
echo ""

read -p "Do you want to add this cron job? (y/n): " confirm

if [ "$confirm" != "y" ]; then
    echo "Cancelled"
    exit 0
fi

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "send_paper_trading_report.py"; then
    echo ""
    echo "⚠️  A daily report cron job already exists:"
    crontab -l | grep "send_paper_trading_report.py"
    echo ""
    read -p "Do you want to replace it? (y/n): " replace

    if [ "$replace" == "y" ]; then
        # Remove old cron job
        (crontab -l 2>/dev/null | grep -v "send_paper_trading_report.py") | crontab -
        echo "Old cron job removed"
    else
        echo "Keeping existing cron job"
        exit 0
    fi
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -

echo ""
echo "✅ Cron job added successfully!"
echo ""
echo "The daily report will be sent at $TIME_DESC every day"
echo ""
echo "You can check your cron jobs with:"
echo "  crontab -l"
echo ""
echo "To remove the cron job later:"
echo "  crontab -e"
echo "  (then delete the line with send_paper_trading_report.py)"
echo ""
echo "Logs will be saved to: $PROJECT_DIR/logs/daily_report.log"
echo ""

# Create logs directory if it doesn't exist
mkdir -p "$PROJECT_DIR/logs"

echo "You can test the report manually with:"
echo "  python scripts/send_paper_trading_report.py"
echo ""
