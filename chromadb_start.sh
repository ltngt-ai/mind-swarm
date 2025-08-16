#!/bin/bash
# Start ChromaDB server

if [ -f chromadb-docker-compose.yml ]; then
    echo "Starting ChromaDB Docker server..."
    docker-compose -f chromadb-docker-compose.yml up -d
    echo "ChromaDB server started at http://localhost:8000"
else
    echo "ChromaDB Docker not configured. Using embedded mode."
fi
