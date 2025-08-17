#!/bin/bash
# Enter the Cyber rootfs environment for maintenance and package management
# This script requires root privileges for chroot

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SUBSPACE_ROOT="${SUBSPACE_ROOT:-../subspace}"
ROOTFS_DIR="$SUBSPACE_ROOT/cyber_rootfs"

echo -e "${CYAN}Mind-Swarm Cyber Rootfs Shell${NC}"
echo "================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}This script must be run as root (for chroot)${NC}"
    echo "Please run: sudo $0"
    exit 1
fi

# Check if rootfs exists
if [ ! -d "$ROOTFS_DIR" ]; then
    echo -e "${RED}Cyber rootfs not found at $ROOTFS_DIR${NC}"
    echo "Please run: sudo ./setup_cyber_rootfs.sh first"
    exit 1
fi

# Check for marker file
if [ ! -f "$ROOTFS_DIR/.mind_swarm_rootfs" ]; then
    echo -e "${RED}Invalid rootfs at $ROOTFS_DIR (missing marker file)${NC}"
    echo "Please run: sudo ./setup_cyber_rootfs.sh"
    exit 1
fi

echo -e "${GREEN}Entering Cyber rootfs at: $ROOTFS_DIR${NC}"
echo ""
echo "You are now in the Cyber environment. Available commands:"
echo "  - apt update          # Update package lists"
echo "  - apt install <pkg>   # Install a package"
echo "  - pip3 install <pkg>  # Install Python package"
echo "  - python3             # Run Python"
echo "  - exit                # Leave the rootfs"
echo ""

# Mount necessary filesystems for chroot
echo -e "${YELLOW}Mounting filesystems...${NC}"

# Check if already mounted to avoid errors
if ! mountpoint -q "$ROOTFS_DIR/proc"; then
    mount -t proc proc "$ROOTFS_DIR/proc"
fi

if ! mountpoint -q "$ROOTFS_DIR/sys"; then
    mount -t sysfs sys "$ROOTFS_DIR/sys"
fi

if ! mountpoint -q "$ROOTFS_DIR/dev"; then
    mount --bind /dev "$ROOTFS_DIR/dev"
fi

if ! mountpoint -q "$ROOTFS_DIR/dev/pts"; then
    mount --bind /dev/pts "$ROOTFS_DIR/dev/pts"
fi

# Create a cleanup function
cleanup() {
    echo ""
    echo -e "${YELLOW}Cleaning up...${NC}"
    
    # Unmount in reverse order
    umount "$ROOTFS_DIR/dev/pts" 2>/dev/null || true
    umount "$ROOTFS_DIR/dev" 2>/dev/null || true
    umount "$ROOTFS_DIR/sys" 2>/dev/null || true
    umount "$ROOTFS_DIR/proc" 2>/dev/null || true
    
    echo -e "${GREEN}Exited Cyber rootfs${NC}"
}

# Set up trap to cleanup on exit
trap cleanup EXIT

# Copy resolv.conf for network access
cp /etc/resolv.conf "$ROOTFS_DIR/etc/resolv.conf"

# Enter the chroot with a nice prompt
echo -e "${GREEN}Entering chroot environment...${NC}"
echo ""

# Use chroot with bash and a custom prompt
chroot "$ROOTFS_DIR" /usr/bin/env \
    PS1="\[\033[1;36m\][cyber-rootfs]\[\033[0m\] \[\033[1;32m\]\u@\h\[\033[0m\]:\[\033[1;34m\]\w\[\033[0m\]# " \
    HOME=/root \
    TERM="$TERM" \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    /bin/bash --norc

echo ""
echo -e "${GREEN}✓ Successfully exited Cyber rootfs${NC}"