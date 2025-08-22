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

# Get SUBSPACE_ROOT from environment or use default
SUBSPACE_ROOT="${SUBSPACE_ROOT:-/home/mind/subspace}"

echo -e "${YELLOW}Mind-Swarm Subspace Cleanup Script${NC}"
echo "======================================="
echo ""

# Check if running with sudo
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}This script must be run with sudo${NC}"
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

# Fix ownership if needed (ensure mind user owns everything)
echo ""
echo "Fixing ownership..."
chown -R mind:mind "$SUBSPACE_ROOT"

echo ""
echo -e "${GREEN}✓ Subspace cleanup complete${NC}"
echo ""
echo "Next steps:"
echo "1. Restart the mind-swarm server: ./run.sh restart"
echo "2. Create new cybers as needed: mind-swarm create"