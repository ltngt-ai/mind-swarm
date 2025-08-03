#!/bin/bash
# Reset subspace to clean state from template

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default subspace location
SUBSPACE_ROOT="${SUBSPACE_ROOT:-$PROJECT_ROOT/subspace}"

echo "=== Mind-Swarm Subspace Reset ==="
echo "Subspace root: $SUBSPACE_ROOT"
echo ""

# Confirm with user
read -p "This will DELETE all agents and data in the subspace. Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 1
fi

# Stop server if running
if pgrep -f "mind_swarm.*daemon" > /dev/null; then
    echo "Stopping Mind-Swarm server..."
    pkill -f "mind_swarm.*daemon" || true
    sleep 2
fi

# Remove existing subspace
if [ -d "$SUBSPACE_ROOT" ]; then
    echo "Removing existing subspace..."
    rm -rf "$SUBSPACE_ROOT"
fi

# Create fresh directory
echo "Creating fresh subspace..."
mkdir -p "$SUBSPACE_ROOT"

# The template will be copied automatically when SubspaceManager initializes
echo ""
echo "Subspace reset complete!"
echo "The template will be applied when you next start the server."
echo ""
echo "To start fresh:"
echo "  source .venv/bin/activate"
echo "  mind-swarm server"