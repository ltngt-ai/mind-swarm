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
