#!/bin/bash
# Start Merchant MCP Server

# Load environment variables
if [ -f "/home/ganesh/context_mcp/load.env" ]; then
    echo "Loading environment from /home/ganesh/context_mcp/load.env"
    set -a
    source /home/ganesh/context_mcp/load.env
    set +a
else
    echo "Warning: load.env not found"
fi

# Change to project directory
cd /home/ganesh/merchant_mcp

# Start the server
echo "Starting MCP Server on port ${MCP_PORT:-8000}..."
python3 -m uvicorn src.server.mcp_server:app \
    --host 0.0.0.0 \
    --port ${MCP_PORT:-8000} \
    --reload \
    --log-level info
