# Use the official Freqtrade image as base
FROM freqtradeorg/freqtrade:stable

# Stay as default user (ftuser) and use python -m pip
USER ftuser

# Install additional Python packages needed for our custom strategy
# Use older psycopg2-binary that's compatible with more Python versions
RUN python -m pip install --user --no-cache-dir \
    loguru==0.7.2 \
    supabase==2.10.0 \
    python-dotenv==1.0.0 \
    psycopg2-binary==2.9.5

# Switch to root for file operations
USER root

# Copy our custom strategy and modules
COPY user_data/strategies/ /freqtrade/user_data/strategies/
COPY user_data/config_bridge.py /freqtrade/user_data/
COPY user_data/scan_logger.py /freqtrade/user_data/
COPY user_data/freqtrade_supabase_bridge.py /freqtrade/user_data/
COPY user_data/data/supabase_dataprovider.py /freqtrade/user_data/data/
# Note: Data will be synced from Supabase on startup
# Note: trade_sync.py no longer needed - using PostgreSQL directly

# Copy our configuration files and startup script
COPY config/config.json /freqtrade/user_data/
COPY start.sh /freqtrade/

# Make startup script executable
RUN chmod +x /freqtrade/start.sh

# Note: paper_trading_config_unified.json will be read from /app/configs/ at runtime
# This allows real-time updates from the Admin dashboard

# Ensure proper permissions and make start.sh executable
RUN chown -R ftuser:ftuser /freqtrade/user_data && \
    chmod +x /freqtrade/start.sh

# Switch back to non-root user
USER ftuser

# Set working directory
WORKDIR /freqtrade

# Set the command to run Freqtrade with Supabase data sync
# Use our shell script that syncs data then starts Freqtrade
ENTRYPOINT ["/bin/sh"]
CMD ["/freqtrade/start.sh"]