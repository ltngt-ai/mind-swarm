#!/bin/bash
# Setup Debian rootfs for Mind-Swarm cybers
# This script requires root privileges

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SUBSPACE_ROOT="${SUBSPACE_ROOT:-../subspace}"
ROOTFS_DIR="$SUBSPACE_ROOT/cyber_rootfs"
DEBIAN_RELEASE="bookworm"  # Debian 12
DEBIAN_MIRROR="http://deb.debian.org/debian"

echo -e "${GREEN}Mind-Swarm Cyber Environment Setup${NC}"
echo "======================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}This script must be run as root (for debootstrap)${NC}"
    echo "Please run: sudo $0"
    exit 1
fi

# Check for debootstrap
if ! command -v debootstrap &> /dev/null; then
    echo -e "${YELLOW}debootstrap not found. Installing...${NC}"
    apt-get update && apt-get install -y debootstrap
fi

# Create subspace directory if it doesn't exist
mkdir -p "$SUBSPACE_ROOT"

# Check if rootfs already exists
if [ -d "$ROOTFS_DIR" ]; then
    echo -e "${YELLOW}Rootfs already exists at $ROOTFS_DIR${NC}"
    read -p "Do you want to rebuild it? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Keeping existing rootfs"
        exit 0
    fi
    echo "Removing existing rootfs..."
    rm -rf "$ROOTFS_DIR"
fi

echo -e "${GREEN}Creating minimal Debian rootfs...${NC}"
echo "Target: $ROOTFS_DIR"
echo "Release: $DEBIAN_RELEASE"
echo ""

# Create minimal Debian system
debootstrap --variant=minbase \
    --include=python3,python3-pip,python3-venv,ca-certificates,python3-dev,build-essential \
    "$DEBIAN_RELEASE" \
    "$ROOTFS_DIR" \
    "$DEBIAN_MIRROR"

echo -e "${GREEN}Configuring rootfs...${NC}"

# Create basic configuration files
cat > "$ROOTFS_DIR/etc/resolv.conf" << EOF
nameserver 8.8.8.8
nameserver 8.8.4.4
EOF

# Create a minimal /etc/hosts
cat > "$ROOTFS_DIR/etc/hosts" << EOF
127.0.0.1   localhost
::1         localhost
EOF

# Create cyber user (uid 1000) - cybers will run as this user inside the rootfs
chroot "$ROOTFS_DIR" /bin/bash -c "useradd -m -u 1000 -s /bin/bash cyber || true"

# Create directories that will be bind-mounted
mkdir -p "$ROOTFS_DIR/personal"
mkdir -p "$ROOTFS_DIR/grid"

# Install Python packages that cybers need
echo -e "${GREEN}Installing Python packages for cybers...${NC}"

# Create requirements file in rootfs
cat > "$ROOTFS_DIR/tmp/cyber_requirements.txt" << 'EOF'
# Core packages for cybers
pyyaml>=6.0
python-dotenv
aiofiles>=23.0.0
jsonschema>=4.0

# File type detection
python-magic>=0.4.27

# Data processing
pandas>=2.0.0
numpy>=1.24.0

# Text processing
markdown>=3.4
beautifulsoup4>=4.12.0

# Date/time utilities
python-dateutil>=2.8.2
EOF

# Install packages in the rootfs
chroot "$ROOTFS_DIR" /bin/bash -c "pip3 install --break-system-packages -r /tmp/cyber_requirements.txt"

# Clean up apt cache to save space
chroot "$ROOTFS_DIR" /bin/bash -c "apt-get clean && rm -rf /var/lib/apt/lists/*"
rm -f "$ROOTFS_DIR/tmp/cyber_requirements.txt"

# Set permissions
chown -R 1000:1000 "$ROOTFS_DIR/home/cyber"

# Create a marker file to indicate successful setup
touch "$ROOTFS_DIR/.mind_swarm_rootfs"

# Calculate size
ROOTFS_SIZE=$(du -sh "$ROOTFS_DIR" | cut -f1)

echo ""
echo -e "${GREEN}✓ Cyber rootfs created successfully!${NC}"
echo "  Location: $ROOTFS_DIR"
echo "  Size: $ROOTFS_SIZE"
echo ""
echo "The rootfs includes:"
echo "  - Minimal Debian $DEBIAN_RELEASE"
echo "  - Python 3 with pip"
echo "  - Required Python packages"
echo "  - User 'cyber' (uid 1000)"
echo ""
echo -e "${YELLOW}Note: The Mind-Swarm server will use this rootfs for all cybers${NC}"
echo -e "${YELLOW}      Cybers will be completely isolated from the host system${NC}"