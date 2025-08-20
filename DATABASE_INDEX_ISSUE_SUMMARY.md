# Database Index Creation Issue - Summary for Advisor

## The Problem
We're unable to create performance indexes on the `ohlc_data` table in Supabase due to SQL query timeouts.

### Root Cause
- The `ohlc_data` table contains **10 years of historical data** (2015-2025)
- Likely contains **millions of rows** across 90 symbols and 3 timeframes
- Supabase has a query timeout limit (typically 2-8 seconds for free/pro tiers)
- Creating indexes on tables this large exceeds the timeout threshold

### Impact
- Without indexes, queries will be slower (full table scans)
- Performance degradation especially for:
  - Time-range queries
  - Symbol-specific lookups
  - Recent data retrieval

## Options to Resolve

### Option 1: Create Partial Indexes (Recommended First Try)
Create indexes only on recent data to reduce processing time:
```sql
-- Index only last 30 days of data
CREATE INDEX idx_ohlc_recent_only
    ON ohlc_data(timestamp DESC)
    WHERE timestamp > NOW() - INTERVAL '30 days';
```
**Pros:** Much faster to create, covers most common queries
**Cons:** Historical queries remain slow

### Option 2: Contact Supabase Support
Request Supabase support team to:
- Create indexes with extended timeout
- Run index creation during maintenance window
- Use CONCURRENTLY option if available on your plan

**Pros:** Professional handling, guaranteed success
**Cons:** May take 24-48 hours for response

### Option 3: Archive Historical Data
Move old data to reduce main table size:
```sql
-- Move pre-2024 data to archive
CREATE TABLE ohlc_data_archive AS
SELECT * FROM ohlc_data WHERE timestamp < '2024-01-01';

-- Remove from main table
DELETE FROM ohlc_data WHERE timestamp < '2024-01-01';

-- Then create indexes on smaller table
```
**Pros:** Permanent solution, fast queries on recent data
**Cons:** Need to modify code to query archive when needed

### Option 4: Upgrade Supabase Plan
Higher-tier Supabase plans offer:
- Longer query timeouts
- Background index creation
- Direct database access for maintenance

**Pros:** Solves timeout issues permanently
**Cons:** Additional monthly cost

### Option 5: Proceed Without Indexes
Continue using the system without indexes and optimize in code:
- Limit query date ranges
- Cache frequently accessed data
- Use pagination aggressively

**Pros:** No immediate action needed
**Cons:** Slower query performance

## Recommendation
1. **Try Option 1 first** (partial indexes) - quick and might work
2. **If that fails, use Option 2** (Supabase support) - most reliable
3. **Consider Option 3** (archive) for long-term solution

## What We've Already Completed
Despite the index issue, we successfully implemented:
- ✅ Memory leak fix (bounded buffers)
- ✅ Retry logic with exponential backoff
- ✅ Configuration management improvements
- ✅ Health monitoring system
- ✅ Error handling patterns

These improvements will provide significant benefits regardless of index status.

## Next Steps
Please advise which option to pursue for the index creation. The system remains functional but would benefit from the performance indexes once created.
