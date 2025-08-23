#!/usr/bin/env python3
"""
Helper script to get the correct database connection string from Supabase.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.config.settings import get_settings


def get_connection_info():
    """Extract connection info and provide instructions."""
    settings = get_settings()
    project_ref = settings.supabase_url.split("//")[1].split(".")[0]

    print("\n" + "=" * 60)
    print("DATABASE CONNECTION HELPER")
    print("=" * 60)

    print(f"\n📌 Your Project Reference: {project_ref}")

    print("\n" + "=" * 60)
    print("GET YOUR CONNECTION STRING FROM SUPABASE")
    print("=" * 60)

    print("\n1. Go to your Supabase Dashboard:")
    print(f"   https://supabase.com/dashboard/project/{project_ref}/settings/database")

    print("\n2. Look for 'Connection string' section")

    print("\n3. Find the connection string that looks like ONE of these formats:")
    print("\n   Format A (Direct Connection - Port 5432):")
    print(
        "   postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres"
    )

    print("\n   Format B (Pooled Connection - Port 6543):")
    print(
        "   postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres"
    )

    print("\n   Format C (Legacy Format):")
    print(
        "   postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres"
    )

    print("\n4. Copy the ENTIRE connection string")

    print("\n" + "=" * 60)
    print("PASTE YOUR CONNECTION STRING")
    print("=" * 60)

    print("\nPaste your full connection string here:")
    print("(It should start with postgresql:// and include your password)")
    print()

    connection_string = input("Connection string: ").strip()

    if not connection_string.startswith("postgresql://"):
        print("\n❌ Invalid connection string. It should start with postgresql://")
        return None

    # Test the connection
    print("\n🔄 Testing connection...")

    import subprocess

    # Add psql to PATH
    import os

    os.environ["PATH"] = "/opt/homebrew/opt/postgresql@16/bin:" + os.environ.get(
        "PATH", ""
    )

    try:
        result = subprocess.run(
            ["psql", connection_string, "-c", "SELECT version();"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            print("✅ Connection successful!")

            # Save to a temporary file for the other scripts
            with open(".db_connection_string.tmp", "w") as f:
                f.write(connection_string)

            print("\n" + "=" * 60)
            print("CONNECTION SAVED")
            print("=" * 60)
            print("\nYour connection string has been saved temporarily.")
            print("\nYou can now run:")
            print("  python3 scripts/create_indexes_with_connection.py")
            print("\nOr monitor with:")
            print("  python3 scripts/monitor_with_connection.py")

            return connection_string
        else:
            print(f"\n❌ Connection failed: {result.stderr}")
            print("\nPossible issues:")
            print("1. Password is incorrect (try resetting it again)")
            print("2. Connection string format is wrong")
            print("3. Database is not accepting connections")
            print(
                "\nTry copying the connection string directly from Supabase Dashboard"
            )
            return None

    except subprocess.TimeoutExpired:
        print("\n❌ Connection timed out")
        print("The database might be unreachable or the connection string is incorrect")
        return None
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return None


if __name__ == "__main__":
    get_connection_info()
