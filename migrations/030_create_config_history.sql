-- Migration: Create Configuration History Table
-- Purpose: Track all configuration changes with before/after values and performance impact
-- Created: 2025-01-03

-- Drop table if exists (for clean migration)
DROP TABLE IF EXISTS config_history CASCADE;

-- Create configuration history table
CREATE TABLE config_history (
    id SERIAL PRIMARY KEY,
    
    -- Change metadata
    change_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    change_type VARCHAR(50) NOT NULL, -- 'manual', 'admin_panel', 'api', 'system'
    changed_by VARCHAR(255), -- User email or system identifier
    change_description TEXT, -- Human-readable description of what changed
    
    -- Configuration tracking
    config_version VARCHAR(20) NOT NULL, -- Version from config file
    config_section VARCHAR(100) NOT NULL, -- Which section was changed (e.g., 'strategies.DCA.thresholds')
    field_name VARCHAR(255) NOT NULL, -- Specific field that changed
    old_value JSONB, -- Previous value (stored as JSON for flexibility)
    new_value JSONB, -- New value (stored as JSON for flexibility)
    
    -- Full config snapshot (optional but useful for rollback)
    full_config_before JSONB, -- Complete config before change
    full_config_after JSONB, -- Complete config after change
    
    -- Performance tracking fields (populated later by analysis)
    trades_before_change INTEGER DEFAULT 0, -- Number of trades in period before change
    trades_after_change INTEGER DEFAULT 0, -- Number of trades in period after change
    pnl_before_change DECIMAL(15, 2), -- P&L % in period before change
    pnl_after_change DECIMAL(15, 2), -- P&L % in period after change
    win_rate_before DECIMAL(5, 2), -- Win rate % before change
    win_rate_after DECIMAL(5, 2), -- Win rate % after change
    
    -- Analysis period settings
    analysis_period_hours INTEGER DEFAULT 24, -- How many hours to analyze before/after
    performance_analyzed_at TIMESTAMPTZ, -- When performance metrics were calculated
    
    -- Additional metadata
    environment VARCHAR(50) DEFAULT 'paper', -- 'paper' or 'live'
    is_active BOOLEAN DEFAULT TRUE, -- Whether this config is currently active
    rollback_id INTEGER REFERENCES config_history(id), -- If this change was rolled back, reference to the rollback entry
    notes TEXT -- Any additional notes about this change
);

-- Create indexes for efficient querying
CREATE INDEX idx_config_history_timestamp ON config_history(change_timestamp DESC);
CREATE INDEX idx_config_history_section ON config_history(config_section);
CREATE INDEX idx_config_history_field ON config_history(field_name);
CREATE INDEX idx_config_history_changed_by ON config_history(changed_by);
CREATE INDEX idx_config_history_active ON config_history(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_config_history_performance ON config_history(pnl_after_change) WHERE pnl_after_change IS NOT NULL;

-- Create a view for recent configuration changes with performance impact
CREATE OR REPLACE VIEW recent_config_changes AS
SELECT 
    id,
    change_timestamp,
    change_type,
    changed_by,
    config_section,
    field_name,
    old_value,
    new_value,
    change_description,
    trades_after_change,
    pnl_after_change,
    win_rate_after,
    CASE 
        WHEN pnl_before_change IS NOT NULL AND pnl_after_change IS NOT NULL THEN
            ROUND(pnl_after_change - pnl_before_change, 2)
        ELSE NULL
    END as pnl_impact,
    CASE 
        WHEN win_rate_before IS NOT NULL AND win_rate_after IS NOT NULL THEN
            ROUND(win_rate_after - win_rate_before, 2)
        ELSE NULL
    END as win_rate_impact,
    notes
FROM config_history
WHERE is_active = TRUE
ORDER BY change_timestamp DESC
LIMIT 100;

-- Create a summary view for configuration sections and their performance
CREATE OR REPLACE VIEW config_section_performance AS
SELECT 
    config_section,
    COUNT(*) as total_changes,
    COUNT(DISTINCT field_name) as unique_fields_changed,
    AVG(pnl_after_change - pnl_before_change) as avg_pnl_impact,
    AVG(win_rate_after - win_rate_before) as avg_win_rate_impact,
    MAX(change_timestamp) as last_changed,
    STRING_AGG(DISTINCT changed_by, ', ') as changed_by_users
FROM config_history
WHERE pnl_before_change IS NOT NULL 
  AND pnl_after_change IS NOT NULL
  AND is_active = TRUE
GROUP BY config_section
ORDER BY avg_pnl_impact DESC;

-- Add comments for documentation
COMMENT ON TABLE config_history IS 'Tracks all configuration changes with performance impact analysis';
COMMENT ON COLUMN config_history.change_type IS 'Source of the change: manual, admin_panel, api, or system';
COMMENT ON COLUMN config_history.config_section IS 'Dot-notation path to the configuration section (e.g., strategies.DCA.thresholds)';
COMMENT ON COLUMN config_history.old_value IS 'Previous value stored as JSONB for flexibility with different data types';
COMMENT ON COLUMN config_history.new_value IS 'New value stored as JSONB for flexibility with different data types';
COMMENT ON COLUMN config_history.analysis_period_hours IS 'Number of hours to analyze performance before and after the change';

-- Grant appropriate permissions
GRANT SELECT ON config_history TO authenticated;
GRANT INSERT ON config_history TO authenticated;
GRANT SELECT ON recent_config_changes TO authenticated;
GRANT SELECT ON config_section_performance TO authenticated;
