#!/bin/bash
#
# MCP Server Startup Script
# Usage: ./start_mcp_server.sh [http|sse|stdio] [port]
#

TRANSPORT=${1:-http}
PORT=${2:-8000}
HOST="0.0.0.0"

cd "$(dirname "$0")"

# Get IP address
IP=$(hostname -I | awk '{print $1}')

echo "=========================================="
echo "  Merchant Integration MCP Server"
echo "=========================================="
echo ""
echo "Starting server with:"
echo "  Transport: $TRANSPORT"
echo "  Host: $HOST (all interfaces)"
echo "  Port: $PORT"
echo ""
echo "Network Access:"
echo "  Local:  http://localhost:$PORT"
echo "  Network: http://$IP:$PORT"
echo ""
echo "Client Configuration:"
echo "  Server URL: http://$IP:$PORT"
echo "  Or use SSE endpoint: http://$IP:$PORT/sse"
echo ""
echo "Press Ctrl+C to stop"
echo "=========================================="
echo ""

# Start the server
python3 src/server/mcp_final.py --transport http --host $HOST --port $PORT
