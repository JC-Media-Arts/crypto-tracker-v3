#!/usr/bin/env python3
"""
Railway startup script for crypto-tracker-v3
Runs the data collector as the main service
Version: 2.0.0 - Railway deployment fix
"""

import os
import sys
import subprocess
import traceback

# Force unbuffered output
os.environ['PYTHONUNBUFFERED'] = '1'

# Add the current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Debug: Print environment info
print(f"=== Railway Startup Debug Info ===")
print(f"Python version: {sys.version}")
print(f"Current working directory: {os.getcwd()}")
print(f"Script location: {current_dir}")
print(f"Python path: {sys.path}")
print(f"Directory contents: {sorted(os.listdir('.'))}")

if os.path.exists('scripts'):
    print(f"Scripts directory contents: {sorted(os.listdir('scripts'))}")
else:
    print("ERROR: scripts directory not found!")

if os.path.exists('src'):
    print(f"Src directory contents: {sorted(os.listdir('src'))}")
else:
    print("ERROR: src directory not found!")

# Determine which service to run based on environment variable
service = os.environ.get('SERVICE_TYPE', 'data_collector')
print(f"Service type: {service}")

# Get the absolute path to the scripts directory
base_dir = current_dir
scripts_dir = os.path.join(base_dir, 'scripts')

print("=== Starting Service ===")

try:
    if service == 'data_collector':
        print("Starting Data Collector Service...")
        script_path = os.path.join(scripts_dir, 'run_data_collector.py')
        print(f"Script path: {script_path}")
        print(f"Script exists: {os.path.exists(script_path)}")
        
        if os.path.exists(script_path):
            # Try direct import as fallback
            print("Attempting to run script...")
            result = subprocess.run([sys.executable, script_path], capture_output=False)
            print(f"Script exited with code: {result.returncode}")
        else:
            print(f"ERROR: Script not found at {script_path}")
            print(f"Available files in scripts/: {os.listdir(scripts_dir) if os.path.exists(scripts_dir) else 'DIR NOT FOUND'}")
            sys.exit(1)
            
    elif service == 'feature_calculator':
        print("Starting Feature Calculator Service...")
        script_path = os.path.join(scripts_dir, 'run_feature_calculator.py')
        print(f"Script path: {script_path}")
        print(f"Script exists: {os.path.exists(script_path)}")
        
        if os.path.exists(script_path):
            print("Attempting to run script...")
            result = subprocess.run([sys.executable, script_path], capture_output=False)
            print(f"Script exited with code: {result.returncode}")
        else:
            print(f"ERROR: Script not found at {script_path}")
            sys.exit(1)
            
    elif service == 'ml_trainer':
        print("Starting ML Trainer Service...")
        script_path = os.path.join(scripts_dir, 'run_ml_trainer.py')
        print(f"Script path: {script_path}")
        print(f"Script exists: {os.path.exists(script_path)}")
        
        if os.path.exists(script_path):
            print("Attempting to run script...")
            result = subprocess.run([sys.executable, script_path], capture_output=False)
            print(f"Script exited with code: {result.returncode}")
        else:
            print(f"ERROR: Script not found at {script_path}")
            sys.exit(1)
    else:
        print(f"Unknown service type: {service}")
        sys.exit(1)
        
except Exception as e:
    print(f"ERROR: Failed to start service: {e}")
    print("Traceback:")
    traceback.print_exc()
    sys.exit(1)
