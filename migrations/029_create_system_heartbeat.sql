-- Migration 029: Create system heartbeat table
-- Purpose: Track service health without polluting scan_history table
-- Date: 2025-01-27

-- Create system_heartbeat table for monitoring service health
CREATE TABLE IF NOT EXISTS system_heartbeat (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR(50) NOT NULL,
    last_heartbeat TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'running',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(service_name)
);

-- Create index for quick status checks
CREATE INDEX IF NOT EXISTS idx_heartbeat_service_time
    ON system_heartbeat(service_name, last_heartbeat DESC);

-- Create index for finding stale heartbeats
CREATE INDEX IF NOT EXISTS idx_heartbeat_last_update
    ON system_heartbeat(last_heartbeat DESC);

-- Add comment to table
COMMENT ON TABLE system_heartbeat IS 'Tracks service health status without polluting business data tables';
COMMENT ON COLUMN system_heartbeat.service_name IS 'Name of the service (e.g., paper_trading_engine, ml_analyzer)';
COMMENT ON COLUMN system_heartbeat.last_heartbeat IS 'Last time the service reported it was running';
COMMENT ON COLUMN system_heartbeat.status IS 'Current status: running, stopped, error';
COMMENT ON COLUMN system_heartbeat.metadata IS 'Additional service-specific information (positions open, symbols monitored, etc)';

-- Create or replace function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_heartbeat_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update updated_at
DROP TRIGGER IF EXISTS update_system_heartbeat_timestamp ON system_heartbeat;
CREATE TRIGGER update_system_heartbeat_timestamp
    BEFORE UPDATE ON system_heartbeat
    FOR EACH ROW
    EXECUTE FUNCTION update_heartbeat_timestamp();
