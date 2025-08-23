#!/bin/bash
# Start all strategy engines and related processes

echo "🚀 Starting All Strategy Engines..."
echo "================================"
echo "Time: $(date)"
echo ""

# Set up environment
cd "$(dirname "$0")/.."  # Go to project root
export PYTHONPATH="$PWD:$PYTHONPATH"

# Kill any existing processes to avoid duplicates
echo "🔄 Cleaning up old processes..."
pkill -f "run_all_strategies" 2>/dev/null
pkill -f "run_paper_trading" 2>/dev/null
pkill -f "signal_generator" 2>/dev/null
pkill -f "run_data_collector" 2>/dev/null
sleep 2

# Create logs directory if it doesn't exist
mkdir -p logs

# Function to start a process
start_process() {
    local script_name=$1
    local log_name=$2
    local description=$3

    if [ -f "$script_name" ]; then
        echo "✅ Starting $description..."
        nohup python3 "$script_name" > "logs/$log_name.log" 2>&1 &
        echo "   PID: $!"
    else
        echo "⚠️  $description script not found at $script_name"
    fi
}

# Start core processes
echo ""
echo "📊 Starting Core Services:"
echo "--------------------------"

# 1. Data Collector (if not already running)
if ! pgrep -f "run_data_collector" > /dev/null; then
    start_process "scripts/run_data_collector.py" "data_collector" "Data Collector"
else
    echo "✅ Data Collector already running"
fi

# 2. All Strategies Scanner (NEW - runs DCA, SWING, CHANNEL)
start_process "scripts/run_all_strategies.py" "all_strategies" "All Strategies Scanner"

# 3. Paper Trading
if [ -f "scripts/run_paper_trading.py" ]; then
    # Check if it needs the new config
    echo "✅ Starting Paper Trading with new thresholds..."
    nohup python3 scripts/run_paper_trading.py > logs/paper_trading.log 2>&1 &
    echo "   PID: $!"
else
    echo "⚠️  Paper Trading script not found"
fi

# 4. ML Predictor (if exists)
if [ -f "scripts/run_ml_predictor.py" ]; then
    start_process "scripts/run_ml_predictor.py" "ml_predictor" "ML Predictor"
fi

# Wait a bit for processes to start
sleep 5

# Verify processes are running
echo ""
echo "📊 Verification:"
echo "----------------"

# Count running processes
RUNNING=$(ps aux | grep -E "run_all_strategies|run_paper_trading|run_data_collector" | grep python3 | grep -v grep | wc -l)
echo "✅ Total strategy processes running: $RUNNING"

# Show individual process status
echo ""
echo "📋 Process Status:"
ps aux | grep python3 | grep -E "run_all_strategies|run_paper_trading|run_data_collector|run_ml_predictor" | grep -v grep | while read line; do
    PID=$(echo $line | awk '{print $2}')
    SCRIPT=$(echo $line | awk '{print $12}')
    echo "  ✓ PID $PID: $(basename $SCRIPT)"
done

# Check for startup errors in logs
echo ""
echo "📝 Checking for startup errors..."
for log in logs/*.log; do
    if [ -f "$log" ]; then
        # Check last 10 lines for errors
        ERROR_COUNT=$(tail -n 10 "$log" 2>/dev/null | grep -i "error\|exception\|failed" | wc -l)
        if [ $ERROR_COUNT -gt 0 ]; then
            echo "  ⚠️  $(basename $log): $ERROR_COUNT potential issues"
            echo "      Last error: $(tail -n 10 "$log" | grep -i "error\|exception\|failed" | tail -n 1 | cut -c1-60)..."
        else
            echo "  ✅ $(basename $log): Clean startup"
        fi
    fi
done

echo ""
echo "================================"
echo "✅ Strategy startup complete!"
echo ""
echo "💡 Monitor logs with:"
echo "   tail -f logs/all_strategies.log"
echo "   tail -f logs/paper_trading.log"
echo ""
echo "📊 Check strategy activity with:"
echo "   python3 scripts/check_all_systems.py"
echo ""
echo "🛑 Stop all with:"
echo "   pkill -f 'run_all_strategies|run_paper_trading'"
echo "================================"
