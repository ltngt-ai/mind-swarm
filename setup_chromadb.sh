#!/bin/bash

# ChromaDB Setup Script for Mind-Swarm
# This script installs and configures ChromaDB for the knowledge system

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=================================${NC}"
echo -e "${BLUE}ChromaDB Setup for Mind-Swarm${NC}"
echo -e "${BLUE}=================================${NC}"
echo

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if running in virtual environment
in_virtualenv() {
    if [ -n "$VIRTUAL_ENV" ]; then
        return 0
    else
        return 1
    fi
}

# Function to activate virtual environment if it exists
activate_venv() {
    if [ -f ".venv/bin/activate" ]; then
        echo -e "${YELLOW}Activating virtual environment...${NC}"
        source .venv/bin/activate
        return 0
    elif [ -f "venv/bin/activate" ]; then
        echo -e "${YELLOW}Activating virtual environment...${NC}"
        source venv/bin/activate
        return 0
    else
        return 1
    fi
}

# Check Python version
echo -e "${BLUE}Checking Python version...${NC}"
if ! command_exists python3; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo -e "${GREEN}Python version: $PYTHON_VERSION${NC}"

# Try to activate virtual environment
if ! in_virtualenv; then
    if ! activate_venv; then
        echo -e "${YELLOW}Warning: Not in a virtual environment${NC}"
        echo -e "${YELLOW}It's recommended to use a virtual environment${NC}"
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

# Installation mode selection
echo
echo -e "${BLUE}Select ChromaDB installation mode:${NC}"
echo "1) Embedded mode (pip install) - Simpler, good for development"
echo "2) Server mode (Docker) - Better performance, production ready"
echo "3) Both - Install pip package and set up Docker"
read -p "Enter choice (1-3): " INSTALL_MODE

# Install ChromaDB via pip
install_chromadb_pip() {
    echo
    echo -e "${BLUE}Installing ChromaDB via pip...${NC}"
    
    # Check if already installed
    if python3 -c "import chromadb" 2>/dev/null; then
        echo -e "${GREEN}ChromaDB is already installed${NC}"
        
        # Get version
        CHROMA_VERSION=$(python3 -c "import chromadb; print(chromadb.__version__)" 2>/dev/null || echo "unknown")
        echo -e "${GREEN}ChromaDB version: $CHROMA_VERSION${NC}"
        
        read -p "Do you want to upgrade ChromaDB? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            pip install --upgrade chromadb
            echo -e "${GREEN}ChromaDB upgraded successfully${NC}"
        fi
    else
        pip install chromadb
        echo -e "${GREEN}ChromaDB installed successfully${NC}"
    fi
    
    # Verify installation
    echo
    echo -e "${BLUE}Verifying ChromaDB installation...${NC}"
    if python3 -c "import chromadb; client = chromadb.Client(); print('ChromaDB embedded mode working')" 2>/dev/null; then
        echo -e "${GREEN}✓ ChromaDB embedded mode is working${NC}"
    else
        echo -e "${RED}✗ ChromaDB embedded mode test failed${NC}"
        return 1
    fi
}

# Set up ChromaDB Docker server
setup_chromadb_docker() {
    echo
    echo -e "${BLUE}Setting up ChromaDB Docker server...${NC}"
    
    # Check if Docker is installed
    if ! command_exists docker; then
        echo -e "${RED}Docker is not installed${NC}"
        echo "Please install Docker first: https://docs.docker.com/get-docker/"
        return 1
    fi
    
    # Check if Docker is running
    if ! docker info >/dev/null 2>&1; then
        echo -e "${RED}Docker is not running${NC}"
        echo "Please start Docker and try again"
        return 1
    fi
    
    # Create docker-compose file
    echo -e "${BLUE}Creating docker-compose.yml for ChromaDB...${NC}"
    cat > chromadb-docker-compose.yml << 'EOF'
version: '3.8'

services:
  chromadb:
    image: chromadb/chroma:latest
    container_name: mind-swarm-chromadb
    ports:
      - "8000:8000"
    volumes:
      - ./chromadb_data:/chroma/chroma
    environment:
      - ANONYMIZED_TELEMETRY=false
      - ALLOW_RESET=true
      - IS_PERSISTENT=true
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/heartbeat"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

networks:
  default:
    name: mind-swarm-network
EOF
    
    echo -e "${GREEN}docker-compose.yml created${NC}"
    
    # Start ChromaDB server
    echo -e "${BLUE}Starting ChromaDB server...${NC}"
    docker-compose -f chromadb-docker-compose.yml up -d
    
    # Wait for server to be ready
    echo -e "${BLUE}Waiting for ChromaDB server to be ready...${NC}"
    MAX_ATTEMPTS=30
    ATTEMPT=0
    
    while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
        if curl -s http://localhost:8000/api/v1/heartbeat >/dev/null 2>&1; then
            echo -e "${GREEN}✓ ChromaDB server is running at http://localhost:8000${NC}"
            break
        fi
        
        ATTEMPT=$((ATTEMPT + 1))
        echo -n "."
        sleep 1
    done
    
    if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
        echo
        echo -e "${RED}✗ ChromaDB server failed to start${NC}"
        echo "Check Docker logs: docker-compose -f chromadb-docker-compose.yml logs"
        return 1
    fi
    
    # Create systemd service (optional)
    echo
    read -p "Do you want to create a systemd service for ChromaDB? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        create_systemd_service
    fi
}

# Create systemd service for ChromaDB
create_systemd_service() {
    echo -e "${BLUE}Creating systemd service...${NC}"
    
    SERVICE_FILE="/tmp/chromadb-mindswarm.service"
    cat > $SERVICE_FILE << EOF
[Unit]
Description=ChromaDB for Mind-Swarm
After=docker.service
Requires=docker.service

[Service]
Type=simple
WorkingDirectory=$(pwd)
ExecStart=/usr/bin/docker-compose -f chromadb-docker-compose.yml up
ExecStop=/usr/bin/docker-compose -f chromadb-docker-compose.yml down
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    echo -e "${YELLOW}Systemd service file created at $SERVICE_FILE${NC}"
    echo "To install it system-wide, run:"
    echo "  sudo cp $SERVICE_FILE /etc/systemd/system/"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable chromadb-mindswarm"
    echo "  sudo systemctl start chromadb-mindswarm"
}

# Create convenience scripts
create_convenience_scripts() {
    echo
    echo -e "${BLUE}Creating convenience scripts...${NC}"
    
    # Start script
    cat > chromadb_start.sh << 'EOF'
#!/bin/bash
# Start ChromaDB server

if [ -f chromadb-docker-compose.yml ]; then
    echo "Starting ChromaDB Docker server..."
    docker-compose -f chromadb-docker-compose.yml up -d
    echo "ChromaDB server started at http://localhost:8000"
else
    echo "ChromaDB Docker not configured. Using embedded mode."
fi
EOF
    chmod +x chromadb_start.sh
    
    # Stop script
    cat > chromadb_stop.sh << 'EOF'
#!/bin/bash
# Stop ChromaDB server

if [ -f chromadb-docker-compose.yml ]; then
    echo "Stopping ChromaDB Docker server..."
    docker-compose -f chromadb-docker-compose.yml down
    echo "ChromaDB server stopped"
else
    echo "No ChromaDB Docker server running"
fi
EOF
    chmod +x chromadb_stop.sh
    
    # Status script
    cat > chromadb_status.sh << 'EOF'
#!/bin/bash
# Check ChromaDB status

echo "ChromaDB Status:"
echo "================"

# Check pip installation
if python3 -c "import chromadb" 2>/dev/null; then
    VERSION=$(python3 -c "import chromadb; print(chromadb.__version__)" 2>/dev/null || echo "unknown")
    echo "✓ ChromaDB package installed (version: $VERSION)"
else
    echo "✗ ChromaDB package not installed"
fi

# Check Docker server
if curl -s http://localhost:8000/api/v1/heartbeat >/dev/null 2>&1; then
    echo "✓ ChromaDB server running at http://localhost:8000"
else
    echo "✗ ChromaDB server not running"
fi

# Check data directory
if [ -d chromadb_data ]; then
    SIZE=$(du -sh chromadb_data 2>/dev/null | cut -f1)
    echo "✓ Data directory exists (size: $SIZE)"
else
    echo "✗ Data directory not found"
fi
EOF
    chmod +x chromadb_status.sh
    
    echo -e "${GREEN}Created convenience scripts:${NC}"
    echo "  ./chromadb_start.sh  - Start ChromaDB server"
    echo "  ./chromadb_stop.sh   - Stop ChromaDB server"
    echo "  ./chromadb_status.sh - Check ChromaDB status"
}

# Test ChromaDB with Mind-Swarm
test_chromadb() {
    echo
    echo -e "${BLUE}Testing ChromaDB with Mind-Swarm...${NC}"
    
    python3 << 'EOF'
import sys
try:
    import chromadb
    
    # Test embedded mode
    print("Testing embedded mode...")
    client = chromadb.Client()
    collection = client.create_collection("test")
    collection.add(
        documents=["test document"],
        ids=["test1"]
    )
    results = collection.query(query_texts=["test"], n_results=1)
    print("✓ Embedded mode works")
    
    # Test server mode if available
    try:
        print("\nTesting server mode...")
        http_client = chromadb.HttpClient(host="localhost", port=8000)
        http_client.heartbeat()
        print("✓ Server mode works (http://localhost:8000)")
    except Exception as e:
        print(f"✗ Server mode not available: {e}")
    
    print("\n✓ ChromaDB is ready for Mind-Swarm!")
    
except ImportError:
    print("✗ ChromaDB is not installed")
    sys.exit(1)
except Exception as e:
    print(f"✗ ChromaDB test failed: {e}")
    sys.exit(1)
EOF
}

# Main installation flow
case $INSTALL_MODE in
    1)
        install_chromadb_pip
        ;;
    2)
        setup_chromadb_docker
        ;;
    3)
        install_chromadb_pip
        setup_chromadb_docker
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

# Create convenience scripts
create_convenience_scripts

# Run tests
test_chromadb

# Final instructions
echo
echo -e "${GREEN}=================================${NC}"
echo -e "${GREEN}ChromaDB Setup Complete!${NC}"
echo -e "${GREEN}=================================${NC}"
echo
echo "Next steps:"
echo "1. Restart the Mind-Swarm server: ./run.sh restart"
echo "2. Check knowledge system status: mind-swarm connect"
echo "   Then type: knowledge stats"
echo
echo "ChromaDB will be used in:"
if [ "$INSTALL_MODE" = "1" ]; then
    echo "  - Embedded mode (data stored in ../subspace/knowledge_db/)"
elif [ "$INSTALL_MODE" = "2" ]; then
    echo "  - Server mode at http://localhost:8000"
    echo "  - Data stored in ./chromadb_data/"
else
    echo "  - Server mode at http://localhost:8000 (if running)"
    echo "  - Falls back to embedded mode if server not available"
fi
echo
echo -e "${BLUE}Enjoy your enhanced Mind-Swarm knowledge system!${NC}"