#!/bin/bash

# Hummingbot Setup Script
# This script installs and configures Hummingbot for paper trading

echo "================================================"
echo "Setting up Hummingbot for ML Signal Trading"
echo "================================================"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "   Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    echo "   Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"

# Create necessary directories
echo "Creating Hummingbot directories..."
mkdir -p hummingbot/{conf,logs,data,scripts,certs}

# Set permissions
chmod -R 777 hummingbot/

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cat > .env << EOF
# Hummingbot Configuration
HUMMINGBOT_MODE=paper_trade
HUMMINGBOT_EXCHANGE=kraken
HUMMINGBOT_STRATEGY=ml_signal_strategy
CONFIG_PASSWORD=password

# Database
DB_PASSWORD=hummingbot_password

# Your API Keys (add these)
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
POLYGON_API_KEY=your_polygon_key

# Kraken API (optional for paper trading)
KRAKEN_API_KEY=
KRAKEN_API_SECRET=
EOF
    echo "⚠️  Please edit .env file with your API keys"
fi

# Pull Hummingbot image
echo "Pulling Hummingbot Docker image..."
docker pull hummingbot/hummingbot:latest

# Start services
echo "Starting Hummingbot services..."
docker-compose up -d postgres redis

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 10

# Initialize Hummingbot
echo "Initializing Hummingbot..."
docker-compose run --rm hummingbot /bin/bash -c "
    echo 'password' | hummingbot init
"

echo ""
echo "================================================"
echo "Hummingbot Setup Complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your API keys"
echo "2. Start Hummingbot: docker-compose up hummingbot"
echo "3. Or run interactively: docker-compose run --rm hummingbot"
echo ""
echo "To use the ML Signal Strategy:"
echo "1. In Hummingbot, type: import ml_signal_strategy"
echo "2. Then type: start"
echo ""
echo "Monitor logs:"
echo "  docker-compose logs -f hummingbot"
echo ""
