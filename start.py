#!/usr/bin/env python3
"""
Railway startup script for crypto-tracker-v3
Runs the data collector as the main service
Version: 1.0.2
"""

import os
import sys
import subprocess

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Determine which service to run based on environment variable
service = os.environ.get('SERVICE_TYPE', 'data_collector')

# Get the absolute path to the scripts directory
base_dir = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.join(base_dir, 'scripts')

if service == 'data_collector':
    print("Starting Data Collector Service...")
    script_path = os.path.join(scripts_dir, 'run_data_collector.py')
    print(f"Running: {script_path}")
    subprocess.run([sys.executable, script_path])
elif service == 'feature_calculator':
    print("Starting Feature Calculator Service...")
    script_path = os.path.join(scripts_dir, 'run_feature_calculator.py')
    print(f"Running: {script_path}")
    subprocess.run([sys.executable, script_path])
elif service == 'ml_trainer':
    print("Starting ML Trainer Service...")
    script_path = os.path.join(scripts_dir, 'run_ml_trainer.py')
    print(f"Running: {script_path}")
    subprocess.run([sys.executable, script_path])
else:
    print(f"Unknown service type: {service}")
    sys.exit(1)
