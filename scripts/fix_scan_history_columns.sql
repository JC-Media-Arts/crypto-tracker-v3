-- Add missing columns to scan_history table
ALTER TABLE scan_history 
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- Verify the columns exist
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'scan_history'
ORDER BY ordinal_position;
