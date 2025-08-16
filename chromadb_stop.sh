#!/bin/bash
# Stop ChromaDB server

if [ -f chromadb-docker-compose.yml ]; then
    echo "Stopping ChromaDB Docker server..."
    docker-compose -f chromadb-docker-compose.yml down
    echo "ChromaDB server stopped"
else
    echo "No ChromaDB Docker server running"
fi
