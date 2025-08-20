#!/bin/bash

# Setup pre-commit hooks for the project
# This will ensure code is properly formatted before commits

echo "Setting up pre-commit hooks..."

# Install pre-commit if not already installed
if ! command -v pre-commit &> /dev/null; then
    echo "Installing pre-commit..."
    pip3 install pre-commit
fi

# Install the git hook scripts
echo "Installing git hooks..."
pre-commit install

# Run against all files to check current state
echo "Checking all files..."
pre-commit run --all-files || true

echo ""
echo "✅ Pre-commit hooks are now installed!"
echo ""
echo "From now on, every time you commit:"
echo "  - Black will automatically format Python files"
echo "  - Flake8 will check for style issues"
echo "  - Various other checks will run"
echo ""
echo "To manually run checks: pre-commit run --all-files"
echo "To skip hooks (emergency only): git commit --no-verify"
