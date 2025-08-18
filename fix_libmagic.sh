#!/bin/bash
# Quick fix to install libmagic1 in existing cyber rootfs
# This script requires root privileges

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Configuration
SUBSPACE_ROOT="${SUBSPACE_ROOT:-../subspace}"
ROOTFS_DIR="$SUBSPACE_ROOT/cyber_rootfs"

echo -e "${GREEN}Installing libmagic1 in Cyber rootfs...${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}This script must be run as root${NC}"
    echo "Please run: sudo $0"
    exit 1
fi

# Check if rootfs exists
if [ ! -d "$ROOTFS_DIR" ] || [ ! -f "$ROOTFS_DIR/.mind_swarm_rootfs" ]; then
    echo -e "${RED}Cyber rootfs not found at $ROOTFS_DIR${NC}"
    echo "Please run: sudo ./setup_cyber_rootfs.sh first"
    exit 1
fi

# Install libmagic1 using manage_cyber_rootfs.sh
echo -e "${GREEN}Installing libmagic1...${NC}"
./manage_cyber_rootfs.sh install libmagic1

echo -e "${GREEN}✓ libmagic1 installed successfully!${NC}"
echo "python-magic should now work correctly in cybers"