.PHONY: help setup install test clean run-all run-data run-ml run-trading monitor backfill train report stop-all lint format check

# Default target
help:
	@echo "Crypto Tracker v3 - Make Commands"
	@echo "================================="
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make setup          - Complete initial setup"
	@echo "  make install        - Install Python dependencies"
	@echo ""
	@echo "Running Components:"
	@echo "  make run-all        - Start all components"
	@echo "  make run-data       - Start data collection"
	@echo "  make run-ml         - Start ML predictions"
	@echo "  make run-trading    - Start paper trading"
	@echo "  make stop-all       - Stop all components"
	@echo ""
	@echo "Operations:"
	@echo "  make backfill       - Backfill historical data"
	@echo "  make train          - Train ML model"
	@echo "  make monitor        - Monitor system health"
	@echo "  make report         - Generate performance report"
	@echo ""
	@echo "Development:"
	@echo "  make test           - Run test suite"
	@echo "  make lint           - Run linting"
	@echo "  make format         - Format code with black"
	@echo "  make check          - Run all checks"
	@echo "  make clean          - Clean cache and logs"

# Setup & Installation
setup: install
	@echo "Setting up database..."
	@python scripts/setup/create_database.py
	@python scripts/migrations/run_migrations.py
	@echo "Verifying setup..."
	@python scripts/setup/verify_setup.py
	@echo "Setup complete!"

install:
	@echo "Installing dependencies..."
	@pip install --upgrade pip
	@pip install -r requirements.txt
	@echo "Dependencies installed!"

# Running Components
run-all:
	@echo "Starting all components..."
	@python src/main.py --all &
	@echo "All components started!"

run-data:
	@echo "Starting data collection..."
	@python src/data/collector.py &
	@echo "Data collection started!"

run-ml:
	@echo "Starting ML predictions..."
	@python src/ml/predictor.py &
	@echo "ML predictions started!"

run-trading:
	@echo "Starting paper trading..."
	@python src/trading/paper_trader.py &
	@echo "Paper trading started!"

stop-all:
	@echo "Stopping all components..."
	@pkill -f "python src/" || true
	@echo "All components stopped!"

# Operations
backfill:
	@echo "Starting historical data backfill..."
	@python scripts/data/backfill_historical.py

train:
	@echo "Training ML model..."
	@python scripts/ml/train_model.py

monitor:
	@echo "Opening system monitor..."
	@python scripts/monitoring/system_monitor.py

report:
	@echo "Generating performance report..."
	@python scripts/reporting/generate_report.py

# Development
test:
	@echo "Running tests..."
	@pytest tests/ -v --cov=src --cov-report=term-missing

test-unit:
	@echo "Running unit tests..."
	@pytest tests/unit/ -v

test-integration:
	@echo "Running integration tests..."
	@pytest tests/integration/ -v

lint:
	@echo "Running linting..."
	@flake8 src/ tests/ scripts/
	@mypy src/ --ignore-missing-imports

format:
	@echo "Formatting code..."
	@black src/ tests/ scripts/

check: lint test
	@echo "All checks passed!"

# Cleaning
clean:
	@echo "Cleaning up..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type f -name "*.log" -delete 2>/dev/null || true
	@rm -rf .pytest_cache/ 2>/dev/null || true
	@rm -rf .coverage 2>/dev/null || true
	@rm -rf htmlcov/ 2>/dev/null || true
	@rm -rf dist/ 2>/dev/null || true
	@rm -rf build/ 2>/dev/null || true
	@rm -rf *.egg-info 2>/dev/null || true
	@echo "Cleanup complete!"

# Database operations
db-migrate:
	@echo "Running database migrations..."
	@python scripts/migrations/run_migrations.py

db-reset:
	@echo "Resetting database..."
	@python scripts/setup/reset_database.py

# Logs
logs:
	@tail -f logs/crypto-tracker.log

logs-errors:
	@grep ERROR logs/crypto-tracker.log | tail -50
