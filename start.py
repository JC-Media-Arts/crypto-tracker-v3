#!/usr/bin/env python3
"""
Railway startup script for crypto-tracker-v3
Version: 3.0.0 - Direct execution to bypass path issues
"""

import os
import sys

# Force unbuffered output
os.environ['PYTHONUNBUFFERED'] = '1'

# Add the current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

print(f"=== Railway Startup V3 ===")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"__file__ location: {current_dir}")

# Determine which service to run
service = os.environ.get('SERVICE_TYPE', 'data_collector')
print(f"Service type: {service}")

# Import and run the appropriate service directly
if service == 'data_collector':
    print("Starting Data Collector Service (direct import)...")
    # Direct execution instead of subprocess
    exec(open('scripts/run_data_collector.py').read())
    
elif service == 'feature_calculator':
    print("Starting Feature Calculator Service (direct import)...")
    # Direct execution instead of subprocess
    exec(open('scripts/run_feature_calculator.py').read())
    
elif service == 'ml_trainer':
    print("Starting ML Trainer Service (direct import)...")
    # Direct execution instead of subprocess
    exec(open('scripts/run_ml_trainer.py').read())
    
elif service == 'data_scheduler' or service == 'scheduler':
    print("Starting Data Scheduler Service...")
    # Import and run the scheduler
    from src.services.data_scheduler import main
    main()
    
else:
    print(f"Unknown service type: {service}")
    sys.exit(1)
