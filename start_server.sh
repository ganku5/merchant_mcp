#!/bin/bash
# Start Merchant MCP Server

# Load environment variables
ENV_FILE="$HOME/context_mcp/load.env"
if [ -f "$ENV_FILE" ]; then
    echo "Loading environment from $ENV_FILE"
    set -a
    source "$ENV_FILE"
    set +a
else
    echo "Warning: load.env not found"
fi

# Change to project directory
cd "$(dirname "$0")"

# Start the server
echo "Starting MCP Server on port ${MCP_PORT:-8000}..."
python3 -m uvicorn src.server.mcp_server:app \
    --host 0.0.0.0 \
    --port ${MCP_PORT:-8000} \
    --reload \
    --log-level info
