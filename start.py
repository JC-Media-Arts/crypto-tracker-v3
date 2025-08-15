#!/usr/bin/env python3
"""
Railway startup script for crypto-tracker-v3
Runs the data collector as the main service
"""

import os
import sys
import subprocess

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Determine which service to run based on environment variable
service = os.environ.get('SERVICE_TYPE', 'data_collector')

if service == 'data_collector':
    print("Starting Data Collector Service...")
    subprocess.run([sys.executable, 'scripts/run_data_collector.py'])
elif service == 'feature_calculator':
    print("Starting Feature Calculator Service...")
    subprocess.run([sys.executable, 'scripts/run_feature_calculator.py'])
elif service == 'ml_trainer':
    print("Starting ML Trainer Service...")
    subprocess.run([sys.executable, 'scripts/run_ml_trainer.py'])
else:
    print(f"Unknown service type: {service}")
    sys.exit(1)
