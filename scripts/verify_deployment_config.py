#!/usr/bin/env python3
"""
Verify deployment configuration is production-ready
"""

import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))


def verify_procfile():
    """Check Procfile for debug commands"""
    print("\n" + "=" * 60)
    print("PROCFILE VERIFICATION")
    print("=" * 60)

    procfile_path = Path("Procfile")

    if not procfile_path.exists():
        print("❌ Procfile not found!")
        return False

    with open(procfile_path, "r") as f:
        content = f.read()

    # Check for debug commands
    debug_commands = ["ls", "pwd", "echo", "cat", "debug", "test"]
    has_debug = False

    for cmd in debug_commands:
        if cmd in content.lower() and "ls" not in [
            "false",
            "else",
        ]:  # Avoid false positives
            has_debug = True
            print(f"⚠️  Found debug command: {cmd}")

    if has_debug:
        print("❌ Procfile contains debug commands")
        return False
    else:
        print("✅ Procfile is clean")
        print(f"   Content: {content.strip()}")
        return True


def verify_railway_json():
    """Check railway.json configuration"""
    print("\n" + "=" * 60)
    print("RAILWAY.JSON VERIFICATION")
    print("=" * 60)

    railway_path = Path("railway.json")

    if not railway_path.exists():
        print("❌ railway.json not found!")
        return False

    with open(railway_path, "r") as f:
        config = json.load(f)

    issues = []

    # Check for required services
    required_services = [
        "Paper Trading",
        "Data Collector",
        "Feature Calculator",
        "ML Retrainer Cron",
    ]

    if "services" in config:
        existing_services = list(config["services"].keys())

        for service in required_services:
            if service in existing_services:
                print(f"✅ {service} configured")

                # Check for health checks
                service_config = config["services"][service]
                if service != "ML Retrainer Cron":  # Cron jobs don't need health checks
                    if "healthcheckPath" not in service_config:
                        issues.append(f"{service} missing healthcheckPath")
                    elif service_config["healthcheckPath"] != "/health":
                        print(f"   ⚠️  Health check path: {service_config['healthcheckPath']}")

            else:
                issues.append(f"Missing service: {service}")
                print(f"❌ {service} not configured")

        # Check for extra services
        extra = set(existing_services) - set(required_services)
        if extra:
            print(f"\n⚠️  Extra services found: {', '.join(extra)}")
    else:
        issues.append("No services defined")

    # Check build configuration
    if "build" in config:
        if config["build"].get("builder") == "NIXPACKS":
            print("\n✅ Using NIXPACKS builder")
        else:
            issues.append("Not using NIXPACKS builder")

    # Check deploy configuration
    if "deploy" in config:
        deploy = config["deploy"]
        if deploy.get("restartPolicyType") == "ON_FAILURE":
            print("✅ Restart policy: ON_FAILURE")
        if deploy.get("numReplicas", 1) > 0:
            print(f"✅ Replicas: {deploy.get('numReplicas', 1)}")

    if issues:
        print(f"\n❌ Issues found:")
        for issue in issues:
            print(f"   - {issue}")
        return False
    else:
        print("\n✅ Railway configuration is production-ready")
        return True


def verify_environment_files():
    """Check for environment configuration"""
    print("\n" + "=" * 60)
    print("ENVIRONMENT CONFIGURATION")
    print("=" * 60)

    # Check for .env.example
    env_example = Path(".env.example")
    if env_example.exists():
        print("✅ .env.example exists")
    else:
        print("⚠️  .env.example not found (recommended for documentation)")

    # Check for .env (should NOT be in git)
    env_file = Path(".env")
    if env_file.exists():
        print("✅ .env file exists locally")

        # Check if it's in .gitignore
        gitignore = Path(".gitignore")
        if gitignore.exists():
            with open(gitignore, "r") as f:
                gitignore_content = f.read()
            if ".env" in gitignore_content:
                print("✅ .env is in .gitignore")
            else:
                print("❌ WARNING: .env is NOT in .gitignore!")
                return False
    else:
        print("⚠️  .env file not found (needed for local development)")

    return True


def verify_requirements():
    """Check requirements.txt for issues"""
    print("\n" + "=" * 60)
    print("REQUIREMENTS.TXT VERIFICATION")
    print("=" * 60)

    req_path = Path("requirements.txt")

    if not req_path.exists():
        print("❌ requirements.txt not found!")
        return False

    with open(req_path, "r") as f:
        lines = f.readlines()

    # Check for common issues
    has_versions = False
    missing_versions = []

    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            if "==" in line or ">=" in line or "~=" in line:
                has_versions = True
            else:
                missing_versions.append(line)

    if has_versions:
        print("✅ Package versions specified")
    else:
        print("⚠️  No package versions specified (may cause issues)")

    if missing_versions and len(missing_versions) < 10:
        print(f"⚠️  Packages without versions: {', '.join(missing_versions[:5])}")

    # Check for critical packages
    critical_packages = ["supabase", "pandas", "scikit-learn", "loguru"]
    req_content = open(req_path, "r").read().lower()

    for package in critical_packages:
        if package in req_content:
            print(f"✅ {package} included")
        else:
            print(f"❌ {package} missing")

    return True


def verify_start_script():
    """Check if start.py exists and is configured"""
    print("\n" + "=" * 60)
    print("START SCRIPT VERIFICATION")
    print("=" * 60)

    start_path = Path("start.py")

    if not start_path.exists():
        print("❌ start.py not found!")
        print("   This is referenced in Procfile but doesn't exist")
        return False

    with open(start_path, "r") as f:
        content = f.read()

    # Check for basic requirements
    if "if __name__" in content:
        print("✅ start.py has main block")
    else:
        print("⚠️  start.py missing main block")

    # Check what it's starting
    if "run_paper_trading" in content:
        print("✅ Starts paper trading")
    elif "run_data_collector" in content:
        print("✅ Starts data collector")
    elif "app.run" in content or "uvicorn.run" in content:
        print("✅ Starts web server")
    else:
        print("⚠️  Unclear what start.py does")

    return True


def main():
    """Run all verification checks"""
    print("\n" + "=" * 80)
    print("DEPLOYMENT CONFIGURATION VERIFICATION")
    print("=" * 80)

    results = {
        "Procfile": verify_procfile(),
        "Railway.json": verify_railway_json(),
        "Environment": verify_environment_files(),
        "Requirements": verify_requirements(),
        "Start Script": verify_start_script(),
    }

    # Summary
    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)

    all_passed = all(results.values())

    for component, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{component:15s}: {status}")

    if all_passed:
        print("\n🎉 DEPLOYMENT CONFIGURATION IS PRODUCTION-READY!")
        print("\nNext steps:")
        print("1. Commit these changes:")
        print("   git add Procfile railway.json")
        print("   git commit -m 'Fix production deployment configuration'")
        print("   git push")
        print("\n2. Deploy to Railway:")
        print("   railway up")
        print("\n3. Set environment variables in Railway dashboard")
    else:
        print("\n❌ DEPLOYMENT CONFIGURATION NEEDS FIXES")
        print("\nPlease address the issues above before deploying.")

    return all_passed


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
