#!/usr/bin/env python3
"""
Script to find where position_size_multiplier is being accessed incorrectly
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import traceback
from loguru import logger

# Test different access patterns that might cause the error
test_dict = {"key1": "value1", "key2": {"nested": "value"}}

print("Testing different error scenarios to match Slack error...")

# Scenario 1: Accessing non-existent key directly
try:
    value = test_dict["position_size_multiplier"]
except KeyError as e:
    print(f"Scenario 1 - Direct access KeyError: {e}")
    print(f"Error string representation: '{e}'")


# Scenario 2: Accessing attribute that doesn't exist
class TestObj:
    pass


try:
    obj = TestObj()
    value = obj.position_size_multiplier
except AttributeError as e:
    print(f"\nScenario 2 - AttributeError: {e}")

# Scenario 3: String used as key
try:
    key = "position_size_multiplier"
    value = test_dict[key]
except KeyError as e:
    print(f"\nScenario 3 - String key access: {e}")
    error_matches = str(e) == "'position_size_multiplier'"
    print(f"Error matches Slack: {error_matches}")

# Now let's check actual code patterns
print("\n" + "=" * 60)
print("Checking actual code patterns...")

# Import actual modules to test
try:
    from src.strategies.swing.detector import SwingDetector
    from src.strategies.dca.detector import DCADetector
    from src.strategies.swing.analyzer import SwingAnalyzer

    print("\n✅ Successfully imported strategy modules")

    # Test creating setups
    print("\nTesting setup creation...")

    # Mock data
    test_data = [
        {
            "close": 100,
            "high": 105,
            "low": 95,
            "volume": 1000,
            "timestamp": "2025-01-01",
        }
    ] * 20

    # Test DCA detector
    from src.data.supabase_client import SupabaseClient
    from src.config.settings import Settings

    settings = Settings()
    supabase = SupabaseClient()

    dca_detector = DCADetector(supabase)
    dca_setup = dca_detector.detect_setup("TEST", test_data)

    if dca_setup:
        print(f"\nDCA Setup created with fields: {list(dca_setup.keys())}")
        print(
            f"Has position_size_multiplier: {'position_size_multiplier' in dca_setup}"
        )
        if "position_size_multiplier" in dca_setup:
            print(f"Value: {dca_setup['position_size_multiplier']}")

except Exception as e:
    print(f"\nError during import/test: {e}")
    traceback.print_exc()

# Check for problematic patterns in code
print("\n" + "=" * 60)
print("Searching for problematic access patterns...")

import os
import re


def find_problematic_patterns(directory):
    """Find code that might cause position_size_multiplier errors"""
    problematic = []

    for root, dirs, files in os.walk(directory):
        # Skip venv and other non-source directories
        if "venv" in root or "__pycache__" in root or ".git" in root:
            continue

        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r") as f:
                        content = f.read()
                        lines = content.split("\n")

                    for i, line in enumerate(lines, 1):
                        # Look for direct dictionary access
                        if re.search(
                            r'\[[\'"]position_size_multiplier[\'"]\](?!\s*=)', line
                        ):
                            if ".get(" not in line:  # Not using safe access
                                problematic.append(
                                    {
                                        "file": filepath,
                                        "line": i,
                                        "code": line.strip(),
                                        "type": "direct_access",
                                    }
                                )

                        # Look for attribute access
                        if re.search(r"\.position_size_multiplier(?!\s*=)", line):
                            problematic.append(
                                {
                                    "file": filepath,
                                    "line": i,
                                    "code": line.strip(),
                                    "type": "attribute_access",
                                }
                            )

                except Exception as e:
                    pass

    return problematic


# Search src directory
src_issues = find_problematic_patterns("src")
if src_issues:
    print("\nFound potential issues in src/:")
    for issue in src_issues:
        print(f"  {issue['file']}:{issue['line']}")
        print(f"    Type: {issue['type']}")
        print(f"    Code: {issue['code']}")

# Search scripts directory
script_issues = find_problematic_patterns("scripts")
if script_issues:
    print("\nFound potential issues in scripts/:")
    for issue in script_issues:
        print(f"  {issue['file']}:{issue['line']}")
        print(f"    Type: {issue['type']}")
        print(f"    Code: {issue['code']}")

print("\n" + "=" * 60)
print("Analysis complete")
