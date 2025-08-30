-- Migration: Create Active Trading Configuration Table
-- Purpose: Store the active trading configuration for real-time access by all services
-- Created: 2025-01-03
-- This enables Railway-deployed Freqtrade to access config without file system dependencies

-- Drop table if exists (for clean migration)
DROP TABLE IF EXISTS trading_config CASCADE;

-- Create active trading configuration table
CREATE TABLE trading_config (
    id SERIAL PRIMARY KEY,
    
    -- Configuration identification
    config_key VARCHAR(50) NOT NULL DEFAULT 'active' UNIQUE, -- 'active' for current config, could support multiple configs later
    config_version VARCHAR(20) NOT NULL, -- Version from config file (e.g., "1.0.37")
    
    -- Full configuration as JSON
    config_data JSONB NOT NULL, -- The complete configuration JSON
    
    -- Metadata
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by VARCHAR(255), -- User email or system identifier
    update_source VARCHAR(50) NOT NULL DEFAULT 'admin_panel', -- 'admin_panel', 'api', 'migration', 'system'
    
    -- Validation and status
    is_valid BOOLEAN DEFAULT TRUE, -- Whether config passed validation
    validation_errors JSONB, -- Any validation errors if not valid
    validation_warnings JSONB, -- Non-blocking warnings
    
    -- Environment tracking
    environment VARCHAR(50) DEFAULT 'paper', -- 'paper' or 'live'
    
    -- Checksums for integrity
    config_hash VARCHAR(64), -- SHA256 hash of config_data for integrity checking
    
    -- Additional metadata
    notes TEXT, -- Any notes about this configuration
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for efficient querying
CREATE INDEX idx_trading_config_key ON trading_config(config_key);
CREATE INDEX idx_trading_config_updated ON trading_config(last_updated DESC);
CREATE INDEX idx_trading_config_version ON trading_config(config_version);

-- Create a function to update the last_updated timestamp
CREATE OR REPLACE FUNCTION update_trading_config_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = NOW();
    -- Also calculate hash of config_data
    NEW.config_hash = encode(sha256(NEW.config_data::text::bytea), 'hex');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to auto-update timestamp and hash on changes
CREATE TRIGGER update_trading_config_timestamp
    BEFORE UPDATE ON trading_config
    FOR EACH ROW
    EXECUTE FUNCTION update_trading_config_timestamp();

-- Create a view for easy access to specific config sections
CREATE OR REPLACE VIEW trading_config_active AS
SELECT 
    config_version,
    config_data,
    last_updated,
    updated_by,
    update_source,
    is_valid,
    config_data->'global_settings' as global_settings,
    config_data->'strategies' as strategies,
    config_data->'position_management' as position_management,
    config_data->'risk_management' as risk_management,
    config_data->'market_protection' as market_protection,
    config_data->'market_cap_tiers' as market_cap_tiers,
    config_data->'notifications' as notifications
FROM trading_config
WHERE config_key = 'active'
AND is_valid = TRUE
ORDER BY last_updated DESC
LIMIT 1;

-- Function to get the active configuration
CREATE OR REPLACE FUNCTION get_active_trading_config()
RETURNS JSONB AS $$
BEGIN
    RETURN (
        SELECT config_data 
        FROM trading_config 
        WHERE config_key = 'active' 
        AND is_valid = TRUE
        ORDER BY last_updated DESC 
        LIMIT 1
    );
END;
$$ LANGUAGE plpgsql;

-- Function to update the active configuration with validation
CREATE OR REPLACE FUNCTION update_active_trading_config(
    new_config JSONB,
    updated_by_user VARCHAR(255) DEFAULT NULL,
    source VARCHAR(50) DEFAULT 'admin_panel'
)
RETURNS TABLE (
    success BOOLEAN,
    message TEXT,
    config_version VARCHAR(20)
) AS $$
DECLARE
    v_version VARCHAR(20);
    v_existing_id INTEGER;
BEGIN
    -- Extract version from config
    v_version := new_config->>'version';
    
    -- Basic validation
    IF v_version IS NULL THEN
        RETURN QUERY SELECT FALSE, 'Configuration must include a version field', NULL::VARCHAR(20);
        RETURN;
    END IF;
    
    -- Check if active config exists
    SELECT id INTO v_existing_id 
    FROM trading_config 
    WHERE config_key = 'active';
    
    IF v_existing_id IS NULL THEN
        -- Insert new config
        INSERT INTO trading_config (
            config_key, 
            config_version, 
            config_data, 
            updated_by, 
            update_source
        ) VALUES (
            'active', 
            v_version, 
            new_config, 
            updated_by_user, 
            source
        );
    ELSE
        -- Update existing config
        UPDATE trading_config 
        SET 
            config_version = v_version,
            config_data = new_config,
            updated_by = updated_by_user,
            update_source = source
        WHERE id = v_existing_id;
    END IF;
    
    RETURN QUERY SELECT TRUE, 'Configuration updated successfully', v_version;
END;
$$ LANGUAGE plpgsql;

-- Add comments for documentation
COMMENT ON TABLE trading_config IS 'Stores the active trading configuration for all services';
COMMENT ON COLUMN trading_config.config_key IS 'Configuration identifier, "active" for current config';
COMMENT ON COLUMN trading_config.config_data IS 'Complete trading configuration as JSON';
COMMENT ON COLUMN trading_config.config_hash IS 'SHA256 hash of config_data for integrity verification';
COMMENT ON FUNCTION get_active_trading_config() IS 'Returns the current active trading configuration';
COMMENT ON FUNCTION update_active_trading_config(JSONB, VARCHAR, VARCHAR) IS 'Updates the active configuration with validation';

-- Grant appropriate permissions
GRANT SELECT ON trading_config TO authenticated;
GRANT INSERT, UPDATE ON trading_config TO authenticated;
GRANT SELECT ON trading_config_active TO authenticated;
GRANT EXECUTE ON FUNCTION get_active_trading_config() TO authenticated;
GRANT EXECUTE ON FUNCTION update_active_trading_config(JSONB, VARCHAR, VARCHAR) TO authenticated;

-- Insert initial configuration from file (this will be done by the migration script)
-- The ConfigLoader will handle the initial population when it first runs
