#!/bin/bash
# Mind-Swarm quick start script

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Load environment variables from .env if it exists
if [ -f ".env" ]; then
    # Use a more robust method to load .env
    set -a  # Mark variables for export
    source .env
    set +a  # Stop marking for export
fi

# Check if package is installed in dev mode
if ! pip show mind-swarm > /dev/null 2>&1; then
    echo -e "${YELLOW}Installing Mind-Swarm in development mode...${NC}"
    pip install -e ".[dev]"
fi

# Function to show usage
show_usage() {
    echo -e "${CYAN}Mind-Swarm Quick Start${NC}"
    echo ""
    echo "Usage: ./run.sh [command]"
    echo ""
    echo "Commands:"
    echo "  server [--debug] [--llm-debug]  - Start the Mind-Swarm server"
    echo "                     --debug for debug logging"
    echo "                     --llm-debug for LLM API call logging"
    echo "  client            - Connect to the server (interactive mode)"
    echo "  status            - Check server and system status"
    echo "  stop              - Stop the server"
    echo "  restart [--debug] [--llm-debug] - Restart the server"
    echo "  logs              - View server logs"
    echo "  demo              - Start server and create 3 agents"
    echo "  export-knowledge  - Export knowledge from ChromaDB for review"
    echo "  import-knowledge  - Import knowledge into ChromaDB"
    echo ""
    echo "Example workflow:"
    echo "  1. ./run.sh server           # Start the server"
    echo "  2. ./run.sh server --debug   # Start with debug logging"
    echo "  3. ./run.sh client           # Connect and interact"
}

# Parse command
COMMAND=${1:-help}

case $COMMAND in
    server|start)
        echo -e "${GREEN}Starting Mind-Swarm server...${NC}"
        # Build command with optional flags
        CMD="mind-swarm server"
        if [[ " $@ " =~ " --debug " ]]; then
            echo -e "${YELLOW}Debug mode enabled${NC}"
            CMD="$CMD --debug"
        fi
        if [[ " $@ " =~ " --llm-debug " ]]; then
            echo -e "${YELLOW}LLM debug mode enabled${NC}"
            CMD="$CMD --llm-debug"
        fi
        CMD="$CMD start"
        $CMD
        RESULT=$?
        
        if [ $RESULT -eq 0 ]; then
            # Wait a moment for server to start
            sleep 2
            
            # Check if server is actually running
            # We need to use the full command since mind-swarm might not be in PATH
            if python3 -m mind_swarm.cli status --quiet 2>/dev/null || mind-swarm status --quiet 2>/dev/null; then
                echo ""
                echo -e "${GREEN}✓ Server started successfully!${NC}"
                echo "View logs with: ./run.sh logs"
                echo "Connect with: ./run.sh client"
            else
                echo ""
                echo -e "${RED}✗ Server failed to start properly${NC}"
                echo "Check logs with: ./run.sh logs"
                echo "Or try: tail -n 50 mind-swarm.log"
                exit 1
            fi
        else
            echo ""
            echo -e "${RED}✗ Failed to start server (exit code: $RESULT)${NC}"
            echo "Check logs with: ./run.sh logs"
            exit 1
        fi
        ;;
    
    client|connect)
        echo -e "${GREEN}Connecting to Mind-Swarm server...${NC}"
        mind-swarm connect --interactive
        ;;
    
    status)
        mind-swarm status
        ;;
    
    stop)
        echo -e "${YELLOW}Stopping Mind-Swarm server...${NC}"
        mind-swarm server stop
        ;;
    
    restart)
        echo -e "${YELLOW}Restarting Mind-Swarm server...${NC}"
        # Build command with optional flags
        CMD="mind-swarm server"
        if [[ " $@ " =~ " --debug " ]]; then
            echo -e "${YELLOW}Debug mode enabled${NC}"
            CMD="$CMD --debug"
        fi
        if [[ " $@ " =~ " --llm-debug " ]]; then
            echo -e "${YELLOW}LLM debug mode enabled${NC}"
            CMD="$CMD --llm-debug"
        fi
        CMD="$CMD restart"
        $CMD
        ;;
    
    logs)
        mind-swarm server logs
        ;;
    
    demo)
        echo -e "${GREEN}Starting Mind-Swarm demo...${NC}"
        echo "1. Starting server..."
        mind-swarm server start
        sleep 3
        echo "2. Creating 3 agents..."
        mind-swarm connect --create 3 --no-interactive
        echo ""
        echo -e "${GREEN}Demo ready!${NC}"
        echo "Connect with: ./run.sh client"
        ;;
    
    export-knowledge)
        echo -e "${GREEN}Exporting knowledge from ChromaDB...${NC}"
        shift  # Remove 'export-knowledge' from arguments
        python scripts/export_knowledge.py "$@"
        ;;
    
    import-knowledge)
        echo -e "${GREEN}Importing knowledge to ChromaDB...${NC}"
        shift  # Remove 'import-knowledge' from arguments
        python scripts/import_knowledge.py "$@"
        ;;
    
    help|*)
        show_usage
        ;;
esac