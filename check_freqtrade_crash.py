#!/usr/bin/env python3
"""
Debug script to check why Freqtrade is crashing after data sync
"""

import subprocess
import sys
import os
from pathlib import Path

def check_python_version():
    """Check Python version in the Docker container"""
    print("Checking Python version in Freqtrade 2024.8 container...")
    try:
        result = subprocess.run(
            ["docker", "run", "--rm", "freqtradeorg/freqtrade:2024.8", "python", "--version"],
            capture_output=True,
            text=True
        )
        print(f"Python version: {result.stdout.strip()}")
        return result.stdout.strip()
    except Exception as e:
        print(f"Error checking Python version: {e}")
        return None

def check_psycopg2_compatibility():
    """Test if psycopg2-binary can be imported"""
    print("\nTesting psycopg2-binary import in container...")
    try:
        result = subprocess.run(
            ["docker", "run", "--rm", "freqtradeorg/freqtrade:2024.8", 
             "python", "-c", "import sys; print(f'Python {sys.version}'); import psycopg2; print('psycopg2 import successful!')"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("✅ psycopg2 can be imported!")
            print(result.stdout)
        else:
            print("❌ psycopg2 import failed!")
            print(result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"Error testing psycopg2: {e}")
        return False

def test_psycopg2_install():
    """Test installing psycopg2-binary in the container"""
    print("\nTesting psycopg2-binary installation...")
    try:
        result = subprocess.run(
            ["docker", "run", "--rm", "freqtradeorg/freqtrade:2024.8", 
             "sh", "-c", "python -m pip install --user psycopg2-binary==2.9.9 && python -c 'import psycopg2; print(\"Success!\")'"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("✅ psycopg2-binary installed and imported successfully!")
            print(result.stdout)
        else:
            print("❌ Installation or import failed!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"Error: {e}")
        return False

def main():
    print("=" * 60)
    print("FREQTRADE CRASH DIAGNOSIS")
    print("=" * 60)
    
    # Check Python version
    python_version = check_python_version()
    
    # Check if psycopg2 is already installed
    has_psycopg2 = check_psycopg2_compatibility()
    
    if not has_psycopg2:
        # Try installing it
        can_install = test_psycopg2_install()
        
        if can_install:
            print("\n✅ psycopg2-binary CAN be installed in Freqtrade 2024.8")
            print("The issue might be something else in the startup process.")
        else:
            print("\n❌ psycopg2-binary CANNOT be installed in Freqtrade 2024.8")
            print("We need to try a different approach.")
    
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS:")
    print("=" * 60)
    
    if "3.13" in str(python_version):
        print("⚠️  Freqtrade 2024.8 still uses Python 3.13!")
        print("   → Try an older version like 2024.6 or 2024.4")
    elif "3.12" in str(python_version):
        print("✅ Python 3.12 detected - should be compatible")
        print("   → Check the actual crash logs for the real error")
    elif "3.11" in str(python_version):
        print("✅ Python 3.11 detected - definitely compatible")
        print("   → The issue is likely not psycopg2 related")

if __name__ == "__main__":
    main()
