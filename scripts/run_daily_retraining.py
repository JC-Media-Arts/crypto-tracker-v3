#!/usr/bin/env python3
"""
Daily Model Retraining Script
Runs daily to retrain models when enough new data is available
"""

import sys
import asyncio
from datetime import datetime
from loguru import logger

sys.path.append('.')

from src.data.supabase_client import SupabaseClient
from src.ml.simple_retrainer import SimpleRetrainer
from src.notifications.slack_notifier import SlackNotifier, NotificationType


async def run_daily_retraining():
    """Run the daily retraining process"""
    
    logger.info("="*60)
    logger.info(f"DAILY MODEL RETRAINING - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60)
    
    # Initialize components
    supabase = SupabaseClient()
    retrainer = SimpleRetrainer(supabase.client)
    slack = SlackNotifier()
    
    # Check and retrain all strategies
    results = retrainer.retrain_all_strategies()
    
    # Prepare summary
    summary_lines = []
    models_updated = 0
    
    for strategy, result in results.items():
        logger.info(f"{strategy}: {result}")
        summary_lines.append(f"• {strategy}: {result}")
        
        if "Model updated" in result or "Initial model trained" in result:
            models_updated += 1
    
    # Send Slack notification
    if slack.enabled:
        title = f"🤖 Daily Model Retraining Complete"
        
        if models_updated > 0:
            message = f"✅ {models_updated} model(s) updated successfully!"
            color = "good"
        else:
            message = "No models updated - insufficient new data or no improvement"
            color = "warning"
        
        details = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'results': '\n'.join(summary_lines)
        }
        
        await slack.send_notification(
            NotificationType.DAILY_REPORT,
            title,
            message,
            details,
            color
        )
    
    logger.info("="*60)
    logger.info(f"Retraining complete. {models_updated} models updated.")
    logger.info("="*60)
    
    return results


def check_current_status():
    """Check current model status and training data availability"""
    
    print("\n" + "="*60)
    print("MODEL RETRAINING STATUS CHECK")
    print("="*60)
    
    supabase = SupabaseClient()
    retrainer = SimpleRetrainer(supabase.client)
    
    for strategy in ['DCA', 'SWING', 'CHANNEL']:
        should_retrain, count = retrainer.should_retrain(strategy)
        
        print(f"\n{strategy} Strategy:")
        print(f"  - New completed trades: {count}")
        print(f"  - Minimum required: {retrainer.min_new_samples}")
        print(f"  - Ready to retrain: {'✅ Yes' if should_retrain else '❌ No'}")
        
        # Check if model exists
        import os
        model_file = os.path.join(retrainer.model_dir, f"{strategy.lower()}_model.pkl")
        if os.path.exists(model_file):
            # Load metadata if available
            metadata_file = os.path.join(retrainer.model_dir, f"{strategy.lower()}_metadata.json")
            if os.path.exists(metadata_file):
                import json
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    print(f"  - Current model score: {metadata.get('score', 'N/A'):.3f}")
                    print(f"  - Last trained: {metadata.get('timestamp', 'Unknown')}")
            else:
                print(f"  - Current model: Exists (no metadata)")
        else:
            print(f"  - Current model: Not found")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Daily Model Retraining')
    parser.add_argument('--check', action='store_true', help='Check status without retraining')
    parser.add_argument('--force', action='store_true', help='Force retraining regardless of sample count')
    
    args = parser.parse_args()
    
    if args.check:
        check_current_status()
    else:
        if args.force:
            print("⚠️  Force mode not implemented yet. Running normal retraining...")
        
        asyncio.run(run_daily_retraining())
