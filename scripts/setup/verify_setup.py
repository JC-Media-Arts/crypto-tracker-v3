#!/usr/bin/env python3
"""Verify that the crypto-tracker-v3 setup is complete and working."""

import os
import sys
import importlib
from pathlib import Path
from rich.console import Console
from rich.table import Table


# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

console = Console()


def check_environment_file():
    """Check if .env file exists."""
    env_file = project_root / ".env"
    if env_file.exists():
        return True, "✅ .env file found"
    else:
        return (
            False,
            "❌ .env file not found. Copy .env.example to .env and add your API keys",
        )


def check_python_version():
    """Check Python version."""
    version = sys.version_info
    if version.major == 3 and version.minor >= 9:
        return True, f"✅ Python {version.major}.{version.minor}.{version.micro}"
    else:
        return (
            False,
            f"❌ Python {version.major}.{version.minor}.{version.micro} (Need 3.9+)",
        )


def check_dependencies():
    """Check if key dependencies are installed."""
    required_packages = [
        "pandas",
        "numpy",
        "xgboost",
        "supabase",
        "polygon",
        "slack_sdk",
        "krakenex",
        "loguru",
        "pydantic",
    ]

    missing = []
    for package in required_packages:
        try:
            importlib.import_module(package)
        except ImportError:
            missing.append(package)

    if missing:
        return False, f"❌ Missing packages: {', '.join(missing)}"
    else:
        return True, "✅ All required packages installed"


def check_directory_structure():
    """Check if all required directories exist."""
    required_dirs = [
        "src/config",
        "src/data",
        "src/ml",
        "src/trading",
        "src/monitoring",
        "src/notifications",
        "src/utils",
        "scripts/setup",
        "scripts/data",
        "scripts/ml",
        "tests/unit",
        "tests/integration",
        "migrations",
        "configs",
        "docs",
        "logs",
        "data",
    ]

    missing = []
    for dir_path in required_dirs:
        full_path = project_root / dir_path
        if not full_path.exists():
            missing.append(dir_path)

    if missing:
        return False, f"❌ Missing directories: {', '.join(missing[:3])}..."
    else:
        return True, "✅ All directories present"


def check_api_keys():
    """Check if API keys are configured (without revealing them)."""
    try:
        from dotenv import load_dotenv

        load_dotenv()

        required_keys = [
            "POLYGON_API_KEY",
            "SUPABASE_URL",
            "SUPABASE_KEY",
            "KRAKEN_API_KEY",
            "KRAKEN_API_SECRET",
            "SLACK_WEBHOOK_URL",
            "SLACK_BOT_TOKEN",
        ]

        missing = []
        for key in required_keys:
            value = os.getenv(key)
            if not value or value.startswith("your_"):
                missing.append(key)

        if missing:
            return False, f"❌ Missing API keys: {', '.join(missing[:3])}..."
        else:
            return True, "✅ All API keys configured"
    except ImportError:
        return False, "❌ python-dotenv not installed"


def main():
    """Run all verification checks."""
    console.print("\n[bold cyan]Crypto Tracker v3 - Setup Verification[/bold cyan]\n")

    # Create results table
    table = Table(title="Setup Status", show_header=True, header_style="bold magenta")
    table.add_column("Component", style="cyan", width=25)
    table.add_column("Status", width=60)

    # Run checks
    checks = [
        ("Python Version", check_python_version()),
        ("Environment File", check_environment_file()),
        ("Dependencies", check_dependencies()),
        ("Directory Structure", check_directory_structure()),
        ("API Keys", check_api_keys()),
    ]

    all_passed = True
    for name, (passed, message) in checks:
        table.add_row(name, message)
        if not passed:
            all_passed = False

    console.print(table)

    # Summary
    if all_passed:
        console.print(
            "\n[bold green]✅ All checks passed! Your setup is complete.[/bold green]"
        )
        console.print("\nNext steps:")
        console.print("1. Run [cyan]make setup[/cyan] to initialize the database")
        console.print("2. Run [cyan]make backfill[/cyan] to load historical data")
        console.print("3. Run [cyan]make train[/cyan] to train the ML model")
        console.print("4. Run [cyan]make run-all[/cyan] to start the system")
        return 0
    else:
        console.print(
            "\n[bold red]❌ Some checks failed. Please fix the issues above.[/bold red]"
        )
        console.print("\nFor help, see the MASTER_PLAN.md documentation.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
