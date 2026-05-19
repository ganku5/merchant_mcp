# MCP Remote Access Guide

## Server Details

| Setting | Value |
|---------|-------|
| **Server IP** | `10.10.71.79` |
| **Port** | `8000` |
| **Protocol** | HTTP (SSE for streaming) |
| **Base URL** | `http://10.10.71.79:8000` |
| **MCP Endpoint** | `http://10.10.71.79:8000/mcp` |
| **SSE Endpoint** | `http://10.10.71.79:8000/sse` |

## Quick Start

### 1. Start the Server

On the host machine (10.10.71.79):

```bash
cd /home/ganesh/merchant_mcp
./start_mcp_server.sh

# Or with custom port:
./start_mcp_server.sh http 8080
```

### 2. Configure Client (Another Computer on Same Network)

#### For Claude Desktop App

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "merchant-integration": {
      "url": "http://10.10.71.79:8000/mcp"
    }
  }
}
```

#### For Cline VS Code Extension

Add to settings:

```json
{
  "cline.mcpServers": [
    {
      "name": "merchant-integration",
      "url": "http://10.10.71.79:8000/mcp",
      "enabled": true
    }
  ]
}
```

#### For Custom Client (Python)

```python
import httpx

MCP_SERVER_URL = "http://10.10.71.79:8000/mcp"

async def call_tool(tool_name: str, params: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{MCP_SERVER_URL}/tools/{tool_name}",
            json=params
        )
        return response.json()

# Example: Search documents
result = await call_tool("search_documents", {
    "query": "merchant onboarding",
    "top_k": 5
})
```

## Available Tools (40 Total)

### API & Integration
- `get_api_spec` - Get API specification
- `generate_payload` - Generate request payloads
- `get_code_example` - Get SDK code examples
- `validate_payload` - Validate API payloads

### Testing
- `test_sandbox` - Test in sandbox environment
- `run_transaction_lifecycle_test` - Full transaction testing
- `run_load_test` - Performance testing
- `run_stress_test` - Breaking point analysis

### Debugging
- `diagnose_api_error` - Diagnose API errors
- `analyze_issue_with_ai` - AI-powered troubleshooting
- `run_deep_webhook_diagnostics` - Webhook diagnostics

### Documentation (NEW)
- **`search_documents`** - Hybrid search across all documents
- `search_contextual_embeddings` - Semantic Q&A search
- `get_interactive_guide` - Step-by-step guides
- `explain_concept` - Explain integration concepts

### Merchant Operations
- `search_documents` - Find merchant onboarding steps
- `get_step_by_step_walkthrough` - API walkthroughs

## Example Queries

### Merchant Onboarding
```json
{
  "tool": "search_documents",
  "params": {
    "query": "how to onboard merchant PA portal",
    "top_k": 5
  }
}
```

### API Integration
```json
{
  "tool": "search_documents",
  "params": {
    "query": "JWE encryption implementation",
    "doc_id": "api_auth_jwe"
  }
}
```

### Error Resolution
```json
{
  "tool": "diagnose_api_error",
  "params": {
    "error_message": "Transaction declined"
  }
}
```

## Network Requirements

- Both machines must be on the same network (or VPN)
- Firewall must allow TCP port 8000
- Server IP must be reachable from client

## Troubleshooting

### Server Not Accessible

1. Check server is running:
   ```bash
   curl http://10.10.71.79:8000/health
   ```

2. Check firewall:
   ```bash
   sudo ufw allow 8000/tcp
   ```

3. Verify IP address:
   ```bash
   hostname -I
   ```

### Connection Refused

- Ensure server started with `--host 0.0.0.0`
- Check no other process using port 8000

### Slow Responses

- Server may be generating contextual embeddings
- Check server logs for activity

## Security Note

This setup uses HTTP (not HTTPS) for local network access. For production:
1. Use HTTPS with certificates
2. Add authentication
3. Restrict network access
