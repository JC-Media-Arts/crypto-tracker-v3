#!/usr/bin/env python3
"""
Check for errors in the backfill process and identify symbols that may need re-running.
"""

import re
from datetime import datetime
from collections import defaultdict


def analyze_backfill_errors():
    """Analyze backfill log for errors and issues."""

    print("BACKFILL ERROR ANALYSIS")
    print("=" * 60)

    # Track errors by symbol
    symbol_errors = defaultdict(list)
    connection_errors = []
    other_errors = []

    # Read the log file
    try:
        with open("logs/backfill.log", "r") as f:
            for line in f:
                # Check for ERROR lines
                if "ERROR" in line:
                    # Extract symbol if present
                    symbol_match = re.search(r"for ([A-Z]+):", line)
                    if symbol_match:
                        symbol = symbol_match.group(1)
                        # Extract error message
                        error_match = re.search(r"Error.*?: (.+)$", line)
                        if error_match:
                            error_msg = error_match.group(1).strip()
                            timestamp_match = re.search(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
                            timestamp = timestamp_match.group(1) if timestamp_match else "Unknown"
                            symbol_errors[symbol].append({"timestamp": timestamp, "error": error_msg})

                    # Check for connection errors
                    if "ConnectionTerminated" in line or "502 Bad Gateway" in line:
                        connection_errors.append(line.strip())
                    elif "ERROR" in line and not symbol_match:
                        other_errors.append(line.strip())

    except FileNotFoundError:
        print("Error: backfill.log not found")
        return

    # Display results
    if symbol_errors:
        print("\n🚨 SYMBOLS WITH ERRORS:")
        print("-" * 60)
        for symbol, errors in sorted(symbol_errors.items()):
            print(f"\n{symbol}:")
            for error in errors[-3:]:  # Show last 3 errors per symbol
                print(f"  [{error['timestamp']}] {error['error'][:100]}")

    if connection_errors:
        print("\n⚠️  CONNECTION ERRORS (last 5):")
        print("-" * 60)
        for error in connection_errors[-5:]:
            print(f"  {error[:150]}")

    # Check which symbols were successfully completed
    completed_symbols = set()
    try:
        with open("logs/backfill.log", "r") as f:
            for line in f:
                if "Completed backfill for" in line:
                    match = re.search(r"Completed backfill for ([A-Z]+)", line)
                    if match:
                        completed_symbols.add(match.group(1))
    except:
        pass

    # Identify symbols that had errors but weren't completed
    problematic_symbols = []
    for symbol in symbol_errors.keys():
        if symbol not in completed_symbols:
            problematic_symbols.append(symbol)

    if problematic_symbols:
        print("\n❌ SYMBOLS THAT MAY NEED RE-RUNNING:")
        print("-" * 60)
        print(f"  {', '.join(sorted(problematic_symbols))}")

    # Count total errors
    total_errors = sum(len(errors) for errors in symbol_errors.values())
    print(f"\n📊 SUMMARY:")
    print("-" * 60)
    print(f"  Total errors logged: {total_errors}")
    print(f"  Symbols with errors: {len(symbol_errors)}")
    print(f"  Connection errors: {len(connection_errors)}")
    print(f"  Symbols completed: {len(completed_symbols)}")

    return problematic_symbols


if __name__ == "__main__":
    problematic = analyze_backfill_errors()

    if problematic:
        print("\n💡 RECOMMENDATION:")
        print("-" * 60)
        print("After the current backfill completes, you may want to re-run:")
        print(f"python scripts/backfill_historical_data.py --symbols {' '.join(problematic)} --months 12")
