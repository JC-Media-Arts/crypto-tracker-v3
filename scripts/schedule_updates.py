#!/usr/bin/env python3
"""
OHLC Update Scheduler
Manages scheduled updates for all timeframes
Can be run as a long-running process or via cron
"""

import os
import sys
import time
import signal
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional
from dateutil import tz
import argparse
import schedule
import subprocess
from threading import Thread, Event

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from loguru import logger

# Configure logging
logger.remove()
logger.add(
    "logs/scheduler.log",
    rotation="1 day",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)
logger.add(sys.stdout, level="INFO")

class OHLCScheduler:
    """Manages scheduled OHLC updates"""
    
    def __init__(self, mode='daemon'):
        """
        Initialize scheduler
        mode: 'daemon' for long-running process, 'cron' for single execution
        """
        self.mode = mode
        self.stop_event = Event()
        self.running_jobs = {}
        
        # Schedule configuration
        self.schedules = {
            '1m': {
                'frequency': 'every_5_minutes',
                'schedule_func': lambda: schedule.every(5).minutes,
                'command': 'python3 scripts/incremental_ohlc_updater.py --timeframe 1m'
            },
            '15m': {
                'frequency': 'every_15_minutes',
                'schedule_func': lambda: schedule.every(15).minutes,
                'command': 'python3 scripts/incremental_ohlc_updater.py --timeframe 15m'
            },
            '1h': {
                'frequency': 'every_hour',
                'schedule_func': lambda: schedule.every().hour.at(":05"),  # 5 minutes past the hour
                'command': 'python3 scripts/incremental_ohlc_updater.py --timeframe 1h'
            },
            '1d': {
                'frequency': 'daily_at_midnight',
                'schedule_func': lambda: schedule.every().day.at("00:05"),  # 12:05 AM PST
                'command': 'python3 scripts/incremental_ohlc_updater.py --timeframe 1d'
            },
            'gap_check': {
                'frequency': 'daily_at_1am',
                'schedule_func': lambda: schedule.every().day.at("01:00"),  # 1:00 AM PST
                'command': 'python3 scripts/validate_and_heal_gaps.py --action scan'
            },
            'health_check': {
                'frequency': 'every_30_minutes',
                'schedule_func': lambda: schedule.every(30).minutes,
                'command': 'python3 scripts/monitor_data_health.py'
            }
        }
        
        # Track last run times
        self.last_run_file = Path('data/scheduler_state.json')
        self.last_runs = self.load_last_runs()
        
    def load_last_runs(self) -> Dict:
        """Load last run times from file"""
        if self.last_run_file.exists():
            try:
                with open(self.last_run_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading last runs: {e}")
        return {}
    
    def save_last_runs(self):
        """Save last run times to file"""
        try:
            self.last_run_file.parent.mkdir(exist_ok=True)
            with open(self.last_run_file, 'w') as f:
                json.dump(self.last_runs, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving last runs: {e}")
    
    def run_job(self, job_name: str, command: str):
        """Run a single job"""
        # Check if job is already running
        if job_name in self.running_jobs and self.running_jobs[job_name].poll() is None:
            logger.warning(f"Job {job_name} is still running, skipping this execution")
            return
        
        logger.info(f"Starting job: {job_name}")
        start_time = datetime.now(tz.UTC)
        
        try:
            # Run the command
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.running_jobs[job_name] = process
            
            # For daemon mode, don't wait for completion
            if self.mode == 'daemon':
                # Start a thread to monitor completion
                Thread(target=self.monitor_job, args=(job_name, process, start_time)).start()
            else:
                # For cron mode, wait for completion
                stdout, stderr = process.communicate()
                return_code = process.returncode
                
                if return_code == 0:
                    logger.success(f"Job {job_name} completed successfully")
                else:
                    logger.error(f"Job {job_name} failed with return code {return_code}")
                    if stderr:
                        logger.error(f"Error output: {stderr}")
                
                # Update last run time
                self.last_runs[job_name] = start_time.isoformat()
                self.save_last_runs()
                
        except Exception as e:
            logger.error(f"Error running job {job_name}: {e}")
    
    def monitor_job(self, job_name: str, process: subprocess.Popen, start_time: datetime):
        """Monitor a running job (for daemon mode)"""
        stdout, stderr = process.communicate()
        return_code = process.returncode
        
        duration = (datetime.now(tz.UTC) - start_time).total_seconds()
        
        if return_code == 0:
            logger.success(f"Job {job_name} completed successfully in {duration:.1f} seconds")
        else:
            logger.error(f"Job {job_name} failed with return code {return_code}")
            if stderr:
                logger.error(f"Error output: {stderr}")
        
        # Update last run time
        self.last_runs[job_name] = start_time.isoformat()
        self.save_last_runs()
        
        # Remove from running jobs
        if job_name in self.running_jobs:
            del self.running_jobs[job_name]
    
    def setup_schedules(self):
        """Set up all scheduled jobs"""
        for job_name, config in self.schedules.items():
            # Create the scheduled job
            job = config['schedule_func']()
            job.do(self.run_job, job_name=job_name, command=config['command'])
            logger.info(f"Scheduled {job_name}: {config['frequency']}")
    
    def run_daemon(self):
        """Run as a long-running daemon process"""
        logger.info("Starting OHLC Update Scheduler in daemon mode")
        
        # Set up signal handlers
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        signal.signal(signal.SIGINT, self.handle_shutdown)
        
        # Set up schedules
        self.setup_schedules()
        
        # Run initial updates for critical timeframes
        logger.info("Running initial updates...")
        self.run_job('1m', self.schedules['1m']['command'])
        self.run_job('15m', self.schedules['15m']['command'])
        
        logger.info("Scheduler is running. Press Ctrl+C to stop.")
        
        # Main loop
        while not self.stop_event.is_set():
            schedule.run_pending()
            time.sleep(1)
        
        logger.info("Scheduler stopped")
    
    def run_cron_job(self, job_name: str):
        """Run a specific job (for cron mode)"""
        if job_name not in self.schedules:
            logger.error(f"Unknown job: {job_name}")
            return
        
        logger.info(f"Running cron job: {job_name}")
        
        # Check if we should run based on last run time
        if self.should_run(job_name):
            self.run_job(job_name, self.schedules[job_name]['command'])
        else:
            logger.info(f"Skipping {job_name} - already run recently")
    
    def should_run(self, job_name: str) -> bool:
        """Check if a job should run based on last run time"""
        if job_name not in self.last_runs:
            return True
        
        last_run = datetime.fromisoformat(self.last_runs[job_name])
        if last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=tz.UTC)
        
        now = datetime.now(tz.UTC)
        
        # Minimum intervals to prevent too frequent runs
        min_intervals = {
            '1m': timedelta(minutes=4),
            '15m': timedelta(minutes=14),
            '1h': timedelta(minutes=55),
            '1d': timedelta(hours=23),
            'gap_check': timedelta(hours=23),
            'health_check': timedelta(minutes=25)
        }
        
        min_interval = min_intervals.get(job_name, timedelta(minutes=5))
        
        return (now - last_run) >= min_interval
    
    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("Received shutdown signal, stopping scheduler...")
        self.stop_event.set()
        
        # Wait for running jobs to complete
        for job_name, process in self.running_jobs.items():
            if process.poll() is None:
                logger.info(f"Waiting for {job_name} to complete...")
                process.wait(timeout=60)
    
    def generate_crontab(self):
        """Generate crontab entries for all scheduled jobs"""
        print("\n# OHLC Update Scheduler Crontab Entries")
        print("# Add these to your crontab with: crontab -e")
        print("# Times are in PST/PDT\n")
        
        cron_entries = {
            '1m': '*/5 * * * *',      # Every 5 minutes
            '15m': '*/15 * * * *',    # Every 15 minutes
            '1h': '5 * * * *',        # 5 minutes past every hour
            '1d': '5 0 * * *',        # 12:05 AM daily
            'gap_check': '0 1 * * *', # 1:00 AM daily
            'health_check': '*/30 * * * *'  # Every 30 minutes
        }
        
        script_path = Path(__file__).absolute()
        
        for job_name, cron_time in cron_entries.items():
            command = f"cd {script_path.parent.parent} && {sys.executable} {script_path} --mode cron --job {job_name}"
            print(f"{cron_time} {command}")
        
        print("\n# Example using flock to prevent overlapping runs:")
        print("# */5 * * * * flock -n /tmp/ohlc_1m.lock -c 'cd /path/to/project && python3 scripts/schedule_updates.py --mode cron --job 1m'")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='OHLC Update Scheduler')
    parser.add_argument('--mode', choices=['daemon', 'cron', 'generate-crontab'],
                       default='daemon', help='Execution mode')
    parser.add_argument('--job', help='Specific job to run (for cron mode)')
    
    args = parser.parse_args()
    
    if args.mode == 'generate-crontab':
        scheduler = OHLCScheduler()
        scheduler.generate_crontab()
    elif args.mode == 'daemon':
        scheduler = OHLCScheduler(mode='daemon')
        scheduler.run_daemon()
    elif args.mode == 'cron':
        if not args.job:
            logger.error("Job name required for cron mode")
            sys.exit(1)
        scheduler = OHLCScheduler(mode='cron')
        scheduler.run_cron_job(args.job)

if __name__ == "__main__":
    main()
