# MCP Server Setup for OpenCode

## Current Status

✅ MCP Server code is ready at `src/server/mcp_server.py`
✅ 15 tools implemented and working
✅ Database connected and populated
✅ All 445 document chunks embedded

## Starting the Server

### Option 1: Run in Current Terminal (Foreground)

```bash
cd /home/ganesh/merchant_mcp
source /home/ganesh/context_mcp/load.env
python3 -m uvicorn src.server.mcp_server:app --host 0.0.0.0 --port 8000 --reload
```

Keep this running in a separate terminal/window.

### Option 2: Run as Background Service

```bash
cd /home/ganesh/merchant_mcp
source /home/ganesh/context_mcp/load.env
nohup python3 -m uvicorn src.server.mcp_server:app --host 0.0.0.0 --port 8000 > /tmp/mcp_server.log 2>&1 &
```

Check status: `curl http://localhost:8000/health`
Stop: `pkill -f uvicorn`

### Option 3: Using PM2 (If Available)

```bash
pm2 start /home/ganesh/merchant_mcp/start_server.sh --name mcp-server
pm2 save
pm2 startup
```

## OpenCode Configuration

Add this to your OpenCode MCP settings:

```json
{
  "mcpServers": {
    "merchant-mcp": {
      "command": "python3",
      "args": [
        "-m", "uvicorn",
        "src.server.mcp_server:app",
        "--host", "0.0.0.0",
        "--port", "8000"
      ],
      "cwd": "/home/ganesh/merchant_mcp",
      "env": {
        "DATABASE_URL": "postgresql://postgres@localhost:5432/mcp_product_context",
        "LITELLM_LLM_API_BASE": "https://grid.ai.juspay.net/",
        "LITELLM_LLM_API_KEY": "sk-SWQkUi_-P4DKnLX6IdowJQ",
        "LITELLM_EMBEDDING_API_BASE": "https://grid.ai.juspay.net/",
        "LITELLM_EMBEDDING_API_KEY": "sk-v9aJ7JUEVd_EQLKdXBMlXw"
      }
    }
  }
}
```

Or use SSE transport:

```json
{
  "mcpServers": {
    "merchant-mcp": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

## Available Tools (15 Total)

### Understanding Phase
- `get_api_spec` - Get complete API specification
- `get_integration_guide` - Get step-by-step integration guide
- `get_flow` - Get ordered API call sequence
- `search_docs` - Search documentation using semantic search

### Building Phase
- `generate_payload` - Generate valid JSON payload
- `get_code_example` - Get working code examples
- `get_webhook_handler` - Get webhook handler with signature verification
- `validate_payload` - Validate payload against schema

### Testing Phase
- `test_sandbox` - Test API calls with annotated responses
- `explain_error` - Explain error codes with fixes
- `get_test_cases` - Get test scenarios
- `check_integration` - Check integration readiness

### Debugging Phase
- `diagnose_webhook` - Diagnose webhook issues
- `lookup_error_map` - Look up error code context
- `search_known_issues` - Search support KB

## Testing the Server

```bash
# Health check
curl http://localhost:8000/health

# List tools
curl http://localhost:8000/tools

# Call a tool
curl -X POST http://localhost:8000/tools/call \
  -H "Content-Type: application/json" \
  -d '{"name": "get_api_spec", "arguments": {"endpoint_id": "orders.create"}}'
```

## Data Ingested

- **3 PDFs** with 445 chunks (100% embedded)
- **10 Endpoints** (3 Juspay + 7 IBMB)
- **253 Error codes** (18 GT + 235 IBMB)
- **3 Integration flows**
- **4 Webhook events**
- **3 Test scenarios**

## Troubleshooting

If server won't start:
1. Check if port 8000 is free: `lsof -i :8000`
2. Check database connection: `psql -h localhost -U postgres -d mcp_product_context`
3. Check environment: `cat /home/ganesh/context_mcp/load.env`

## Logs

Background mode logs: `/tmp/mcp_server.log`
