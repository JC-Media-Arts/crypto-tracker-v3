#!/usr/bin/env python3
"""
Send Daily Paper Trading Report to Slack
This script can be run via cron to send daily reports
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.trading.simple_paper_trader_v2 import SimplePaperTraderV2
from src.notifications.paper_trading_notifier import PaperTradingNotifier
from src.data.supabase_client import SupabaseClient

async def generate_daily_report():
    """Generate and send daily paper trading report"""
    
    logger.info("=" * 80)
    logger.info("📊 GENERATING DAILY PAPER TRADING REPORT")
    logger.info("=" * 80)
    
    try:
        # Initialize paper trader to load state
        paper_trader = SimplePaperTraderV2(
            initial_balance=1000.0,
            max_positions=30
        )
        
        # Get portfolio statistics
        stats = paper_trader.get_portfolio_stats()
        
        # Get today's trades
        trades_today = paper_trader.get_trades_today()
        
        # Get open positions
        open_positions = paper_trader.get_open_positions_summary()
        
        # Log summary
        logger.info(f"Portfolio Value: ${stats['total_value']:.2f}")
        logger.info(f"Total P&L: ${stats['total_pnl']:+.2f} ({stats['total_pnl_pct']:+.2f}%)")
        logger.info(f"Open Positions: {stats['positions']}/{stats['max_positions']}")
        logger.info(f"Total Trades: {stats['total_trades']}")
        logger.info(f"Win Rate: {stats['win_rate']:.1f}%")
        logger.info(f"Today's Trades: {len(trades_today)}")
        
        # Initialize notifier and send report
        notifier = PaperTradingNotifier()
        
        if notifier.enabled:
            await notifier.send_daily_report(
                stats=stats,
                trades_today=trades_today,
                open_positions=open_positions
            )
            logger.info("✅ Daily report sent to Slack #reports channel")
        else:
            logger.warning("Slack notifications disabled - no webhook configured")
            
        # Also fetch and report on database statistics if available
        try:
            db_client = SupabaseClient()
            
            # Get today's date
            today = datetime.now().date().isoformat()
            yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()
            
            # Fetch recent trades from database
            recent_trades = db_client.client.table("paper_trades").select("*").gte("created_at", yesterday).execute()
            
            if recent_trades.data:
                logger.info(f"Database records: {len(recent_trades.data)} trades in last 24 hours")
                
                # Calculate database stats
                db_wins = sum(1 for t in recent_trades.data if t.get('pnl', 0) > 0)
                db_losses = sum(1 for t in recent_trades.data if t.get('pnl', 0) < 0)
                db_total_pnl = sum(t.get('pnl', 0) for t in recent_trades.data if t.get('pnl') is not None)
                
                logger.info(f"Database Stats - Wins: {db_wins}, Losses: {db_losses}, P&L: ${db_total_pnl:.2f}")
                
        except Exception as e:
            logger.warning(f"Could not fetch database statistics: {e}")
        
    except Exception as e:
        logger.error(f"Error generating daily report: {e}")
        
        # Try to send error notification
        try:
            notifier = PaperTradingNotifier()
            if notifier.enabled:
                await notifier.notify_system_error(
                    error_type="Daily Report Generation Failed",
                    error_message=str(e),
                    details={
                        "Script": "send_paper_trading_report.py",
                        "Time": datetime.now().isoformat()
                    }
                )
        except:
            pass
        
        return False
    
    logger.info("=" * 80)
    logger.info("✅ Daily report generation complete")
    logger.info("=" * 80)
    
    return True

async def main():
    """Main entry point"""
    success = await generate_daily_report()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())
