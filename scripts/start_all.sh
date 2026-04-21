#!/bin/bash
# Start all dependencies and run ingestion test

set -e

cd /home/ganesh/merchant_mcp

echo "======================================"
echo "Merchant MCP - Full Setup"
echo "======================================"

# Check if Docker is available
if command -v docker &> /dev/null; then
    echo "Starting PostgreSQL and Redis with Docker Compose..."
    docker-compose up -d postgres redis
    
    # Wait for PostgreSQL to be ready
    echo "Waiting for PostgreSQL to be ready..."
    sleep 5
    
    until docker exec merchant_mcp_postgres pg_isready -U postgres > /dev/null 2>&1; do
        echo "  Waiting..."
        sleep 2
    done
    echo "✓ PostgreSQL is ready"
else
    echo "Docker not found. Assuming PostgreSQL is running locally..."
fi

# Install dependencies
echo ""
echo "Installing Python dependencies..."
pip install -q -r requirements.txt

# Setup database schema
echo ""
echo "Setting up database schema..."
python scripts/setup_db.py

# Ingest IBMB files
echo ""
echo "Ingesting IBMB files..."
python scripts/ingest_ibmb.py

echo ""
echo "======================================"
echo "Setup complete! Starting MCP server..."
echo "======================================"

# Start the MCP server
python -m src.server.server
