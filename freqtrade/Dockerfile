# Use the official Freqtrade image as base
FROM freqtradeorg/freqtrade:stable

# Switch to root to install packages
USER root

# Install additional Python packages needed for our custom strategy
RUN pip install --no-cache-dir \
    loguru==0.7.2 \
    supabase==2.10.0 \
    python-dotenv==1.0.0

# Copy our custom strategy and modules
COPY user_data/strategies/ /freqtrade/user_data/strategies/
COPY user_data/config_bridge.py /freqtrade/user_data/
COPY user_data/scan_logger.py /freqtrade/user_data/
COPY user_data/data/ /freqtrade/user_data/data/

# Copy our configuration files
COPY config/config.json /freqtrade/user_data/

# Note: paper_trading_config_unified.json will be read from /app/configs/ at runtime
# This allows real-time updates from the Admin dashboard

# Ensure proper permissions
RUN chown -R ftuser:ftuser /freqtrade/user_data

# Switch back to non-root user
USER ftuser

# Set working directory
WORKDIR /freqtrade

# Set the command to run Freqtrade
CMD ["freqtrade", "trade", "--config", "/freqtrade/user_data/config.json", "--strategy", "ChannelStrategyV1", "--dry-run"]