#!/usr/bin/env python3
"""
Ensure only one instance of the data collector is running.
Prevents multiple WebSocket connections to Polygon.
"""

import os
import sys
import psutil
from pathlib import Path


LOCK_FILE = "/tmp/crypto_websocket.lock"


def check_single_instance():
    """Ensure only one instance is running"""

    # Check if lock file exists
    if os.path.exists(LOCK_FILE):
        # Read PID from lock file
        try:
            with open(LOCK_FILE, "r") as f:
                old_pid = int(f.read().strip())

            # Check if process is still running
            if psutil.pid_exists(old_pid):
                # Check if it's actually a Python process (not just any process with that PID)
                try:
                    process = psutil.Process(old_pid)
                    if "python" in process.name().lower():
                        print(
                            f"❌ Another instance is already running (PID: {old_pid})"
                        )
                        print(f"   Process: {process.name()}")
                        print(f"   Command: {' '.join(process.cmdline()[:3])}")
                        sys.exit(1)
                except:
                    pass

            print(f"ℹ️ Removing stale lock file (PID {old_pid} not running)")
            os.remove(LOCK_FILE)

        except Exception as e:
            print(f"⚠️ Error reading lock file: {e}")
            os.remove(LOCK_FILE)

    # Create new lock file with current PID
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

    print(f"✅ Lock acquired (PID: {os.getpid()})")
    return True


def cleanup_lock():
    """Remove lock file on exit"""
    if os.path.exists(LOCK_FILE):
        # Only remove if it's our PID
        try:
            with open(LOCK_FILE, "r") as f:
                lock_pid = int(f.read().strip())

            if lock_pid == os.getpid():
                os.remove(LOCK_FILE)
                print("✅ Lock file removed")
        except:
            pass


def kill_existing_collectors():
    """Kill any existing data collector processes"""
    killed = []

    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = " ".join(proc.info["cmdline"] or [])

            # Check for data collector processes
            if (
                "collector" in cmdline.lower()
                or "websocket" in cmdline.lower()
                or "run_data_collector" in cmdline
            ):
                # Don't kill ourselves
                if proc.info["pid"] != os.getpid():
                    proc.terminate()
                    killed.append(proc.info["pid"])
                    print(f"🛑 Terminated existing collector (PID: {proc.info['pid']})")

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if killed:
        import time

        time.sleep(2)  # Give processes time to terminate

        # Force kill if still running
        for pid in killed:
            if psutil.pid_exists(pid):
                try:
                    psutil.Process(pid).kill()
                    print(f"⚠️ Force killed PID: {pid}")
                except:
                    pass

    return len(killed)


if __name__ == "__main__":
    # Kill existing collectors first
    killed_count = kill_existing_collectors()
    if killed_count > 0:
        print(f"ℹ️ Killed {killed_count} existing collector process(es)")

    # Check single instance
    if check_single_instance():
        print("✅ Ready to start data collector")

    # Note: cleanup_lock() should be called when the main process exits
