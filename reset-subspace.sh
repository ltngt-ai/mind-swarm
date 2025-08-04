#!/bin/bash

# reset-subspace.sh - Reset the subspace to a clean state for development
# This removes all agent data, messages, and state files

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
CONFIRM_REQUIRED=true
SUBSPACE_ROOT="${SUBSPACE_ROOT:-./subspace}"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --no-confirm)
            CONFIRM_REQUIRED=false
            shift
            ;;
        --subspace-root)
            SUBSPACE_ROOT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --no-confirm        Don't ask for confirmation (for automated usage)"
            echo "  --subspace-root DIR Set the subspace root directory (default: ./subspace)"
            echo "  -h, --help          Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Check if subspace directory exists
if [ ! -d "$SUBSPACE_ROOT" ]; then
    echo -e "${RED}Error: Subspace directory not found at: $SUBSPACE_ROOT${NC}"
    echo "Set SUBSPACE_ROOT environment variable or use --subspace-root option"
    exit 1
fi

# Function to clean a directory but keep the directory itself
clean_directory() {
    local dir="$1"
    if [ -d "$dir" ]; then
        echo "  Cleaning: $dir"
        find "$dir" -mindepth 1 -delete 2>/dev/null || true
    fi
}

# Function to reset the subspace
reset_subspace() {
    echo -e "${YELLOW}Resetting subspace at: $SUBSPACE_ROOT${NC}"
    echo ""
    
    # Clean agents directory
    if [ -d "$SUBSPACE_ROOT/agents" ]; then
        echo "Cleaning agents..."
        for agent_dir in "$SUBSPACE_ROOT/agents"/*; do
            if [ -d "$agent_dir" ]; then
                agent_name=$(basename "$agent_dir")
                echo "  Removing agent: $agent_name"
                rm -rf "$agent_dir"
            fi
        done
    fi
    
    # Clean grid areas
    echo ""
    echo "Cleaning grid areas..."
    clean_directory "$SUBSPACE_ROOT/grid/plaza"
    clean_directory "$SUBSPACE_ROOT/grid/library"
    clean_directory "$SUBSPACE_ROOT/grid/bulletin"
    clean_directory "$SUBSPACE_ROOT/grid/workshop"
    
    # Clean shared directory (includes developer registry)
    echo ""
    echo "Cleaning shared directory..."
    clean_directory "$SUBSPACE_ROOT/shared/directory"
    
    # Clean logs
    echo ""
    echo "Cleaning logs..."
    clean_directory "$SUBSPACE_ROOT/logs"
    clean_directory "$SUBSPACE_ROOT/logs/agents"
    
    # Clean state files
    echo ""
    echo "Cleaning state files..."
    if [ -d "$SUBSPACE_ROOT/state" ]; then
        rm -rf "$SUBSPACE_ROOT/state"
    fi
    
    # Clean agent states
    if [ -d "$SUBSPACE_ROOT/agent_states" ]; then
        echo "  Removing agent state files..."
        rm -rf "$SUBSPACE_ROOT/agent_states"
    fi
    
    # Recreate essential directories
    echo ""
    echo "Recreating directory structure..."
    mkdir -p "$SUBSPACE_ROOT/agents"
    mkdir -p "$SUBSPACE_ROOT/grid/plaza"
    mkdir -p "$SUBSPACE_ROOT/grid/library"
    mkdir -p "$SUBSPACE_ROOT/grid/bulletin"
    mkdir -p "$SUBSPACE_ROOT/grid/workshop"
    mkdir -p "$SUBSPACE_ROOT/logs/agents"
    mkdir -p "$SUBSPACE_ROOT/agent_states"
    mkdir -p "$SUBSPACE_ROOT/shared/directory"
    
    # Create placeholder files
    echo "# Plaza - Community Discussions" > "$SUBSPACE_ROOT/grid/plaza/README.md"
    echo "# Library - Shared Knowledge" > "$SUBSPACE_ROOT/grid/library/README.md"
    echo "# Bulletin - Announcements" > "$SUBSPACE_ROOT/grid/bulletin/README.md"
    echo "# Workshop - Tools and Scripts" > "$SUBSPACE_ROOT/grid/workshop/README.md"
    
    echo ""
    echo -e "${GREEN}Subspace reset complete!${NC}"
    echo ""
    echo "Summary:"
    echo "  - All agents removed"
    echo "  - Grid areas cleaned"
    echo "  - Developer registry cleared"
    echo "  - Logs cleared"
    echo "  - State files removed"
    echo "  - Directory structure recreated"
}

# Main execution
echo -e "${YELLOW}=== Mind-Swarm Subspace Reset ===${NC}"
echo ""

if [ "$CONFIRM_REQUIRED" = true ]; then
    echo -e "${RED}WARNING: This will delete all agent data, messages, and state!${NC}"
    echo "Subspace location: $SUBSPACE_ROOT"
    echo ""
    read -p "Are you sure you want to reset the subspace? (yes/no): " -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        echo "Reset cancelled."
        exit 0
    fi
fi

# Check if server is running
if pgrep -f "mind_swarm.*daemon" > /dev/null; then
    echo -e "${RED}Warning: Mind-Swarm server appears to be running!${NC}"
    echo "It's recommended to stop the server before resetting."
    
    if [ "$CONFIRM_REQUIRED" = true ]; then
        read -p "Continue anyway? (yes/no): " -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
            echo "Reset cancelled."
            exit 0
        fi
    else
        echo "Continuing with reset (--no-confirm mode)..."
    fi
fi

# Perform the reset
reset_subspace

echo ""
echo "You can now start the Mind-Swarm server with a clean subspace."