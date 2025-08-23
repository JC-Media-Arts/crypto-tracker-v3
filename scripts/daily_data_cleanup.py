#!/usr/bin/env python3
"""
Daily data cleanup script to enforce retention policies.
Run this via cron at 3 AM PST daily.

APPROVED RETENTION POLICY:
- Daily data: keep forever
- 1 Hour data: keep 2 years  
- 15 minute data: keep 1 year
- 1 minute data: keep 30 days
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import time

sys.path.append(str(Path(__file__).parent.parent))

from src.data.supabase_client import SupabaseClient
from src.notifications.slack_notifier import SlackNotifier
from loguru import logger


class DataRetentionManager:
    """Manages data retention and cleanup."""
    
    def __init__(self):
        self.supabase = SupabaseClient()
        self.slack = SlackNotifier()
        self.cleanup_report = []
        
    def cleanup_ohlc_data(self):
        """Clean OHLC data according to retention policy."""
        
        cleanup_queries = [
            {
                'name': '1-minute data (>30 days)',
                'table': 'ohlc_data',
                'condition': "timeframe IN ('1m', '1min', '1') AND timestamp < NOW() - INTERVAL '30 days'",
                'batch_size': 5000
            },
            {
                'name': '15-minute data (>1 year)',
                'table': 'ohlc_data',
                'condition': "timeframe IN ('15m', '15min') AND timestamp < NOW() - INTERVAL '1 year'",
                'batch_size': 5000
            },
            {
                'name': '1-hour data (>2 years)',
                'table': 'ohlc_data',
                'condition': "timeframe IN ('1h', '1hour') AND timestamp < NOW() - INTERVAL '2 years'",
                'batch_size': 5000
            }
        ]
        
        for cleanup in cleanup_queries:
            try:
                # First, get count of rows to delete
                count_query = f"""
                    SELECT COUNT(*) as count
                    FROM {cleanup['table']}
                    WHERE {cleanup['condition']}
                """
                
                # Note: Direct SQL execution would need to be through Supabase RPC
                # For now, we'll use the client's delete method
                
                logger.info(f"Cleaning {cleanup['name']}...")
                
                # Delete in batches using Supabase client
                # This is a simplified approach - in production you'd want proper SQL
                deleted_count = 0
                
                if '1m' in cleanup['condition'] or '1min' in cleanup['condition']:
                    timeframes = ['1m', '1min', '1']
                    cutoff_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
                elif '15m' in cleanup['condition']:
                    timeframes = ['15m', '15min']
                    cutoff_date = (datetime.utcnow() - timedelta(days=365)).isoformat()
                elif '1h' in cleanup['condition']:
                    timeframes = ['1h', '1hour']
                    cutoff_date = (datetime.utcnow() - timedelta(days=730)).isoformat()
                
                for tf in timeframes:
                    batch_deleted = 0
                    while True:
                        result = self.supabase.client.table(cleanup['table'])\
                            .delete()\
                            .eq('timeframe', tf)\
                            .lt('timestamp', cutoff_date)\
                            .limit(cleanup['batch_size'])\
                            .execute()
                        
                        if not result.data or len(result.data) == 0:
                            break
                            
                        batch_deleted += len(result.data)
                        deleted_count += len(result.data)
                        
                        # Brief pause between batches
                        time.sleep(0.5)
                        
                        # Safety limit
                        if batch_deleted > 100000:
                            logger.warning(f"Reached safety limit for {cleanup['name']}")
                            break
                
                self.cleanup_report.append({
                    'target': cleanup['name'],
                    'deleted': deleted_count,
                    'status': 'success'
                })
                
                logger.info(f"Deleted {deleted_count} rows from {cleanup['name']}")
                
            except Exception as e:
                logger.error(f"Error cleaning {cleanup['name']}: {e}")
                self.cleanup_report.append({
                    'target': cleanup['name'],
                    'deleted': 0,
                    'status': f'error: {str(e)[:100]}'
                })
    
    def cleanup_other_tables(self):
        """Clean non-OHLC tables."""
        
        other_cleanups = [
            {
                'name': 'scan_history',
                'table': 'scan_history',
                'date_field': 'timestamp',
                'retention_days': 7
            },
            {
                'name': 'ml_features',
                'table': 'ml_features',
                'date_field': 'timestamp',
                'retention_days': 30
            },
            {
                'name': 'shadow_testing_scans',
                'table': 'shadow_testing_scans',
                'date_field': 'scan_time',
                'retention_days': 30
            },
            {
                'name': 'shadow_testing_trades',
                'table': 'shadow_testing_trades',
                'date_field': 'created_at',
                'retention_days': 30
            }
        ]
        
        for cleanup in other_cleanups:
            try:
                cutoff_date = (datetime.utcnow() - timedelta(days=cleanup['retention_days'])).isoformat()
                
                result = self.supabase.client.table(cleanup['table'])\
                    .delete()\
                    .lt(cleanup['date_field'], cutoff_date)\
                    .execute()
                
                deleted_count = len(result.data) if result.data else 0
                
                self.cleanup_report.append({
                    'target': cleanup['name'],
                    'deleted': deleted_count,
                    'status': 'success'
                })
                
                logger.info(f"Deleted {deleted_count} rows from {cleanup['name']}")
                
            except Exception as e:
                if "does not exist" not in str(e):
                    logger.error(f"Error cleaning {cleanup['name']}: {e}")
                self.cleanup_report.append({
                    'target': cleanup['name'],
                    'deleted': 0,
                    'status': f'error: {str(e)[:100]}'
                })
    
    def send_report(self):
        """Send cleanup report to Slack."""
        
        # Calculate totals
        total_deleted = sum(item['deleted'] for item in self.cleanup_report)
        successful = sum(1 for item in self.cleanup_report if item['status'] == 'success')
        failed = len(self.cleanup_report) - successful
        
        # Format report
        report_lines = ["📊 *Daily Data Cleanup Report*"]
        report_lines.append(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S PST')}")
        report_lines.append(f"Total rows deleted: {total_deleted:,}")
        report_lines.append(f"Success: {successful}, Failed: {failed}\n")
        
        report_lines.append("*Details:*")
        for item in self.cleanup_report:
            status_emoji = "✅" if item['status'] == 'success' else "❌"
            report_lines.append(f"{status_emoji} {item['target']}: {item['deleted']:,} rows")
            if item['status'] != 'success':
                report_lines.append(f"   Error: {item['status']}")
        
        report_text = "\n".join(report_lines)
        
        # Send to Slack
        try:
            self.slack.send_message(report_text, webhook_type='alerts')
            logger.info("Cleanup report sent to Slack")
        except Exception as e:
            logger.error(f"Failed to send Slack report: {e}")
        
        # Log to console
        print("\n" + "="*60)
        print("DATA CLEANUP REPORT")
        print("="*60)
        print(report_text)
        print("="*60)
    
    def run(self):
        """Run the complete cleanup process."""
        
        logger.info("Starting daily data cleanup...")
        start_time = time.time()
        
        # Run cleanups
        self.cleanup_ohlc_data()
        self.cleanup_other_tables()
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Send report
        self.send_report()
        
        logger.info(f"Data cleanup completed in {duration:.2f} seconds")
        

def main():
    """Main entry point."""
    manager = DataRetentionManager()
    manager.run()


if __name__ == "__main__":
    main()
