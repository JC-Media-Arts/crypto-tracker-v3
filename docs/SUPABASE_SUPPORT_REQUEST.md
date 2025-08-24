# Supabase Support Request Template

## Subject: Request for Assistance Creating Indexes on Large Table

Hi Supabase Support Team,

**Project Details:**
- Project URL: [Your Supabase Project URL]
- Table Name: `ohlc_data`
- Estimated Rows: 30-50 million
- Date Range: 2015-2025 (10 years of historical data)
- Issue: Index creation timing out due to table size

## Problem Description

We're experiencing timeouts when attempting to create performance-critical indexes on our OHLC (Open-High-Low-Close) data table. This table stores cryptocurrency price data for 90 symbols across multiple timeframes (1m, 15m, 1h, 1d).

## Indexes We Need Created

We need help creating these performance-critical indexes:

```sql
-- Primary composite index
CREATE INDEX idx_ohlc_symbol_time
ON ohlc_data(symbol, timeframe, timestamp DESC);

-- BRIN index for time-series queries
CREATE INDEX idx_ohlc_timestamp
ON ohlc_data USING BRIN(timestamp);

-- Symbol-specific index
CREATE INDEX idx_ohlc_symbol_timestamp
ON ohlc_data(symbol, timestamp DESC);
```

## What We've Already Tried

1. **Standard CREATE INDEX** - Times out after ~8 seconds
2. **CREATE INDEX CONCURRENTLY** - Also times out
3. **Partial indexes on recent data** - [Pending/Successful]
4. **BRIN index alone** - Times out

## Request

Could you please:

1. **Option A:** Run these indexes with extended timeout during your next maintenance window
2. **Option B:** Temporarily increase our query timeout limit so we can create the indexes ourselves
3. **Option C:** Enable CONCURRENTLY option with extended timeout for our plan
4. **Option D:** Advise on best practices for handling tables of this size in Supabase

## Business Impact

This is currently blocking our production trading system's performance. Without these indexes:
- Query times are 10-100x slower than acceptable
- ML feature calculation is timing out
- Real-time trading signals are delayed

## Additional Information

- We're willing to schedule this during off-peak hours
- We have a data archival plan ready to implement after indexes are created
- We're on the [Free/Pro/Team/Enterprise] plan

Thank you for your assistance. This is a critical performance issue for our production system.

Best regards,
[Your Name]
[Your Contact Email]

---

## Alternative Message for Live Chat

Hi! We have a large OHLC table (30-50M rows) and index creation is timing out. Table: ohlc_data, Project: [URL]. Need help creating indexes:
1. CREATE INDEX idx_ohlc_symbol_time ON ohlc_data(symbol, timeframe, timestamp DESC)
2. CREATE INDEX idx_ohlc_timestamp ON ohlc_data USING BRIN(timestamp)

Can you run these with extended timeout or advise on best approach? This is blocking production. Thanks!
