#!/bin/bash

# Clean Subspace Dry Run Script
# This script shows what would be deleted without actually deleting anything

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

echo -e "${YELLOW}Mind-Swarm Subspace Cleanup - DRY RUN${NC}"
echo "========================================="
echo ""

# Verify subspace directory exists
if [ ! -d "$SUBSPACE_ROOT" ]; then
    echo -e "${RED}Subspace directory not found: $SUBSPACE_ROOT${NC}"
    exit 1
fi

echo "Subspace location: $SUBSPACE_ROOT"
echo ""
echo -e "${BLUE}This is a DRY RUN - nothing will be deleted${NC}"
echo ""

# Navigate to subspace directory
cd "$SUBSPACE_ROOT"

echo "Items that will be KEPT:"
echo "------------------------"
for item in .mind-swarm cyber_rootfs .gitignore; do
    if [ -e "$item" ]; then
        echo -e "${GREEN}✓${NC} $item"
        if [ -d "$item" ]; then
            size=$(du -sh "$item" 2>/dev/null | cut -f1)
            echo "  Size: $size"
        fi
    else
        echo -e "${YELLOW}✗${NC} $item (not found)"
    fi
done

echo ""
echo "Items that will be DELETED:"
echo "---------------------------"

# Find and list all items that would be deleted
items_to_delete=$(find . -mindepth 1 -maxdepth 1 \
    ! -name '.mind-swarm' \
    ! -name 'cyber_rootfs' \
    ! -name '.gitignore' \
    2>/dev/null | sort)

if [ -z "$items_to_delete" ]; then
    echo -e "${GREEN}Nothing to delete - subspace is already clean${NC}"
else
    for item in $items_to_delete; do
        item_name=$(basename "$item")
        if [ -d "$item" ]; then
            size=$(du -sh "$item" 2>/dev/null | cut -f1)
            file_count=$(find "$item" -type f 2>/dev/null | wc -l)
            echo -e "${RED}✗${NC} $item_name (directory)"
            echo "  Size: $size, Files: $file_count"
        else
            size=$(du -sh "$item" 2>/dev/null | cut -f1)
            echo -e "${RED}✗${NC} $item_name (file, $size)"
        fi
    done
    
    # Calculate total size that would be freed
    total_size=$(du -ch $items_to_delete 2>/dev/null | grep total | cut -f1)
    echo ""
    echo "Total space that would be freed: $total_size"
fi

echo ""
echo "----------------------------------------"
echo "To actually perform the cleanup, run:"
echo -e "${YELLOW}./clean_subspace.sh${NC}"
echo "(You may need to use sudo if you don't have write permissions)"