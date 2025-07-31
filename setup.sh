#!/bin/bash

# Mind-Swarm Setup Script

echo "Mind-Swarm Setup"
echo "================"

# Check Python version
python_version=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
required_version="3.10"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python $required_version or higher is required (found $python_version)"
    exit 1
fi
echo "✓ Python $python_version"

# Check bubblewrap
if ! command -v bwrap &> /dev/null; then
    echo "❌ Bubblewrap (bwrap) not found"
    echo "Please install it: sudo apt install bubblewrap"
    exit 1
fi
echo "✓ Bubblewrap installed"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install package
echo "Installing Mind-Swarm..."
pip install -e ".[dev]"

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your API keys"
fi

# Create default subspace directory
mkdir -p subspace

echo ""
echo "✓ Setup complete!"
echo ""
echo "To start Mind-Swarm:"
echo "  source venv/bin/activate"
echo "  mind-swarm run"