#!/usr/bin/env python3
"""
Python-based process manager with auto-restart capability
Similar to PM2 but without Node.js dependency
"""

import subprocess
import time
import signal
import sys
import os
from datetime import datetime
from pathlib import Path
import threading
import json

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))


class ProcessManager:
    """Manages multiple processes with auto-restart"""

    def __init__(self):
        self.processes = {}
        self.running = True
        self.config = {
            "all-strategies": {
                "script": "scripts/run_all_strategies.py",
                "restart_delay": 5,
                "max_restarts": 100,
                "restart_count": 0,
                "enabled": True,
            },
            "data-collector": {
                "script": "scripts/run_data_collector.py",
                "restart_delay": 5,
                "max_restarts": 100,
                "restart_count": 0,
                "enabled": True,
            },
            # Paper trading removed - using Hummingbot instead
            # 'paper-trading': {
            #     'script': 'scripts/run_paper_trading.py',
            #     'restart_delay': 5,
            #     'max_restarts': 100,
            #     'restart_count': 0,
            #     'enabled': False
            # }
        }

        # Set up signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n{datetime.now()} - Received shutdown signal, stopping all processes...")
        self.running = False
        self.stop_all()
        sys.exit(0)

    def start_process(self, name, config):
        """Start a single process"""
        if not config["enabled"]:
            return None

        script_path = Path(config["script"])
        if not script_path.exists():
            print(f"⚠️  {name}: Script not found at {script_path}")
            return None

        try:
            log_file = open(f"logs/pm_{name}.log", "a")
            process = subprocess.Popen(
                ["python3", config["script"]],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid,  # Create new process group
            )

            print(f"✅ {name}: Started with PID {process.pid}")
            return process

        except Exception as e:
            print(f"❌ {name}: Failed to start - {e}")
            return None

    def monitor_process(self, name, config):
        """Monitor a single process and restart if needed"""
        while self.running and config["restart_count"] < config["max_restarts"]:
            process = self.processes.get(name)

            if process is None or process.poll() is not None:
                # Process is not running
                if process and process.poll() is not None:
                    exit_code = process.poll()
                    print(f"⚠️  {name}: Process exited with code {exit_code}")

                if config["restart_count"] > 0:
                    print(f"   Waiting {config['restart_delay']} seconds before restart...")
                    time.sleep(config["restart_delay"])

                if self.running:  # Check again after sleep
                    config["restart_count"] += 1
                    print(f"🔄 {name}: Restarting (attempt {config['restart_count']}/{config['max_restarts']})")

                    process = self.start_process(name, config)
                    if process:
                        self.processes[name] = process
                    else:
                        print(f"❌ {name}: Failed to restart")
                        time.sleep(config["restart_delay"] * 2)

            time.sleep(1)  # Check every second

        if config["restart_count"] >= config["max_restarts"]:
            print(f"❌ {name}: Max restarts reached, giving up")

    def stop_process(self, name):
        """Stop a single process"""
        process = self.processes.get(name)
        if process and process.poll() is None:
            try:
                # Try graceful shutdown first
                process.terminate()
                time.sleep(2)

                # Force kill if still running
                if process.poll() is None:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)

                print(f"✅ {name}: Stopped")
            except Exception as e:
                print(f"⚠️  {name}: Error stopping - {e}")

    def stop_all(self):
        """Stop all processes"""
        for name in self.processes:
            self.stop_process(name)

    def run(self):
        """Main run loop"""
        print("=" * 60)
        print("🚀 PYTHON PROCESS MANAGER")
        print(f"Time: {datetime.now()}")
        print("=" * 60)
        print("\nStarting services with auto-restart...")
        print("-" * 40)

        # Start all processes
        threads = []
        for name, config in self.config.items():
            if config["enabled"]:
                # Start the process
                process = self.start_process(name, config)
                if process:
                    self.processes[name] = process

                    # Create monitoring thread
                    thread = threading.Thread(target=self.monitor_process, args=(name, config), daemon=True)
                    thread.start()
                    threads.append(thread)

        print("\n" + "=" * 60)
        print("📊 MONITORING DASHBOARD")
        print("=" * 60)
        print("\nPress Ctrl+C to stop all processes")
        print("\nStatus updates every 30 seconds...")

        # Main monitoring loop
        while self.running:
            time.sleep(30)

            if self.running:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Status Check:")
                for name, process in self.processes.items():
                    if process and process.poll() is None:
                        print(f"  ✅ {name}: Running (PID {process.pid})")
                    else:
                        restart_count = self.config[name]["restart_count"]
                        print(f"  ⚠️  {name}: Not running (restarts: {restart_count})")

    def status(self):
        """Print current status"""
        print("\n" + "=" * 40)
        print("PROCESS STATUS")
        print("=" * 40)

        for name, config in self.config.items():
            process = self.processes.get(name)
            if process and process.poll() is None:
                print(f"✅ {name}: Running (PID {process.pid})")
            else:
                print(f"❌ {name}: Stopped (restarts: {config['restart_count']})")


def main():
    """Main entry point"""
    manager = ProcessManager()

    # Check for command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "status":
            manager.status()
        elif command == "stop":
            manager.stop_all()
        else:
            print(f"Unknown command: {command}")
            print("Usage: python3 process_manager.py [status|stop]")
    else:
        # Run the manager
        try:
            manager.run()
        except KeyboardInterrupt:
            print("\n\nShutting down...")
            manager.stop_all()


if __name__ == "__main__":
    main()
