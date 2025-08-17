#!/bin/bash
# Manage the Cyber rootfs - install packages, update, etc.
# This script requires root privileges

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

show_help() {
    echo -e "${CYAN}Mind-Swarm Cyber Rootfs Manager${NC}"
    echo "=================================="
    echo ""
    echo "Usage: sudo $0 [command] [args]"
    echo ""
    echo "Commands:"
    echo "  shell                    - Enter interactive shell in rootfs"
    echo "  update                   - Update package lists"
    echo "  upgrade                  - Upgrade all packages"
    echo "  install <package>        - Install a system package"
    echo "  pip-install <package>    - Install a Python package"
    echo "  list-packages            - List installed packages"
    echo "  list-python              - List Python packages"
    echo "  exec <command>           - Execute a command in rootfs"
    echo "  size                     - Show rootfs disk usage"
    echo ""
    echo "Examples:"
    echo "  sudo $0 install curl"
    echo "  sudo $0 pip-install requests"
    echo "  sudo $0 exec python3 --version"
    echo "  sudo $0 shell"
}

# Check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then 
        echo -e "${RED}This script must be run as root${NC}"
        echo "Please run: sudo $0 $*"
        exit 1
    fi
}

# Check if rootfs exists
check_rootfs() {
    if [ ! -d "$ROOTFS_DIR" ] || [ ! -f "$ROOTFS_DIR/.mind_swarm_rootfs" ]; then
        echo -e "${RED}Cyber rootfs not found at $ROOTFS_DIR${NC}"
        echo "Please run: sudo ./setup_cyber_rootfs.sh first"
        exit 1
    fi
}

# Execute command in chroot
exec_in_rootfs() {
    # Copy resolv.conf for network
    cp /etc/resolv.conf "$ROOTFS_DIR/etc/resolv.conf" 2>/dev/null || true
    
    # Execute in chroot
    chroot "$ROOTFS_DIR" /usr/bin/env \
        HOME=/root \
        TERM="$TERM" \
        PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
        "$@"
}

# Parse command
COMMAND=${1:-help}

case $COMMAND in
    shell)
        check_root
        check_rootfs
        exec ./enter_cyber_rootfs.sh
        ;;
        
    update)
        check_root
        check_rootfs
        echo -e "${CYAN}Updating package lists...${NC}"
        exec_in_rootfs apt-get update
        echo -e "${GREEN}✓ Package lists updated${NC}"
        ;;
        
    upgrade)
        check_root
        check_rootfs
        echo -e "${CYAN}Upgrading packages...${NC}"
        exec_in_rootfs apt-get update
        exec_in_rootfs apt-get upgrade -y
        echo -e "${GREEN}✓ Packages upgraded${NC}"
        ;;
        
    install)
        check_root
        check_rootfs
        shift
        if [ -z "$1" ]; then
            echo -e "${RED}Please specify package(s) to install${NC}"
            echo "Usage: sudo $0 install <package>"
            exit 1
        fi
        echo -e "${CYAN}Installing package(s): $*${NC}"
        exec_in_rootfs apt-get update
        exec_in_rootfs apt-get install -y "$@"
        echo -e "${GREEN}✓ Package(s) installed${NC}"
        ;;
        
    pip-install|pip_install)
        check_root
        check_rootfs
        shift
        if [ -z "$1" ]; then
            echo -e "${RED}Please specify Python package(s) to install${NC}"
            echo "Usage: sudo $0 pip-install <package>"
            exit 1
        fi
        echo -e "${CYAN}Installing Python package(s): $*${NC}"
        exec_in_rootfs pip3 install --break-system-packages "$@"
        echo -e "${GREEN}✓ Python package(s) installed${NC}"
        ;;
        
    list-packages|list_packages)
        check_root
        check_rootfs
        echo -e "${CYAN}Installed packages:${NC}"
        exec_in_rootfs dpkg -l | grep ^ii | awk '{print $2 "\t" $3}' | column -t
        ;;
        
    list-python|list_python)
        check_root
        check_rootfs
        echo -e "${CYAN}Python packages:${NC}"
        exec_in_rootfs pip3 list
        ;;
        
    exec)
        check_root
        check_rootfs
        shift
        if [ -z "$1" ]; then
            echo -e "${RED}Please specify command to execute${NC}"
            echo "Usage: sudo $0 exec <command>"
            exit 1
        fi
        exec_in_rootfs "$@"
        ;;
        
    size)
        check_rootfs
        echo -e "${CYAN}Cyber rootfs disk usage:${NC}"
        du -sh "$ROOTFS_DIR"
        echo ""
        echo -e "${CYAN}Breakdown by directory:${NC}"
        du -sh "$ROOTFS_DIR"/* 2>/dev/null | sort -h | tail -10
        ;;
        
    help|--help|-h|"")
        show_help
        ;;
        
    *)
        echo -e "${RED}Unknown command: $COMMAND${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac