#!/bin/bash

# Clean Subspace Script
# This script removes everything from the subspace directory except:
# - .mind-swarm (promotion rules and model pool)
# - cyber_rootfs (cyber runtime template)
# - .gitignore

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Load environment variables from .env if it exists
if [ -f ".env" ]; then
    set -a  # Mark variables for export
    source .env
    set +a  # Stop marking for export
fi

# Get SUBSPACE_ROOT from environment or use default relative to script location
if [ -z "$SUBSPACE_ROOT" ]; then
    # Default to ../subspace relative to the mind-swarm directory
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    SUBSPACE_ROOT="$(dirname "$SCRIPT_DIR")/subspace"
    echo -e "${YELLOW}Warning: SUBSPACE_ROOT not set in environment or .env${NC}"
    echo -e "${YELLOW}Using default: $SUBSPACE_ROOT${NC}"
fi

echo -e "${YELLOW}Mind-Swarm Subspace Cleanup Script${NC}"
echo "======================================="
echo ""

# Check if we have write permissions to the subspace directory
if [ ! -w "$SUBSPACE_ROOT" ]; then 
    echo -e "${RED}No write permission for: $SUBSPACE_ROOT${NC}"
    echo "You may need to run this script with sudo"
    echo "Usage: sudo ./clean_subspace.sh"
    exit 1
fi

# Verify subspace directory exists
if [ ! -d "$SUBSPACE_ROOT" ]; then
    echo -e "${RED}Subspace directory not found: $SUBSPACE_ROOT${NC}"
    exit 1
fi

echo "Subspace location: $SUBSPACE_ROOT"
echo ""
echo "This will DELETE everything in the subspace except:"
echo "  - .mind-swarm (promotion rules and model pool)"
echo "  - cyber_rootfs (cyber runtime template)"
echo "  - .gitignore"
echo ""

# Ask for confirmation
read -p "Are you sure you want to proceed? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo -e "${YELLOW}Operation cancelled${NC}"
    exit 0
fi

echo ""
echo "Starting cleanup..."

# Count items before cleanup
total_before=$(find "$SUBSPACE_ROOT" -mindepth 1 -maxdepth 1 | wc -l)
echo "Items in subspace before cleanup: $total_before"

# Navigate to subspace directory
cd "$SUBSPACE_ROOT"

# Remove everything except the specified directories/files
# Using find to get all items, then filter out what we want to keep
find . -mindepth 1 -maxdepth 1 \
    ! -name '.mind-swarm' \
    ! -name 'cyber_rootfs' \
    ! -name '.gitignore' \
    -exec rm -rf {} + 2>/dev/null || true

# Also clean up any cbr_db if it exists (will be recreated)
if [ -d "cbr_db" ]; then
    rm -rf cbr_db
    echo "Removed cbr_db (will be recreated on server start)"
fi

# Count items after cleanup
total_after=$(find "$SUBSPACE_ROOT" -mindepth 1 -maxdepth 1 | wc -l)
items_removed=$((total_before - total_after))

echo ""
echo -e "${GREEN}Cleanup completed successfully!${NC}"
echo "Items removed: $items_removed"
echo "Items remaining: $total_after"

# List remaining items
echo ""
echo "Remaining items in subspace:"
ls -la "$SUBSPACE_ROOT" | grep -v '^total'

# Fix ownership if needed (ensure current user owns everything)
# Only attempt if running as root/sudo
if [ "$EUID" -eq 0 ]; then
    echo ""
    echo "Fixing ownership..."
    # Get the actual user who ran sudo (or current user if not sudo)
    ACTUAL_USER="${SUDO_USER:-$USER}"
    if [ -n "$ACTUAL_USER" ]; then
        chown -R "$ACTUAL_USER:$ACTUAL_USER" "$SUBSPACE_ROOT"
    fi
fi

echo ""
echo -e "${GREEN}✓ Subspace cleanup complete${NC}"
echo ""
echo "Next steps:"
echo "1. Restart the mind-swarm server: ./run.sh restart"
echo "2. Create new cybers as needed: mind-swarm create"