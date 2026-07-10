# MCP Server Setup for OpenCode

## Current Status

✅ MCP Server code is ready at `src/server/mcp_server.py`
✅ 23 hosted tools implemented for client query resolution, integration guidance, testing, debugging, and document retrieval
✅ Database connected and populated
✅ Current database has 431 documents, 7,744 text chunks, 2,702 contextual embeddings, 197 legacy endpoint specs, and 184 v2 API specs

## Starting the Server

### Option 1: Run in Current Terminal (Foreground)

```bash
cd "$HOME/merchant_mcp"
source "$HOME/context_mcp/load.env"
python3 -m uvicorn src.server.mcp_server:app --host 0.0.0.0 --port 8000 --reload
```

Keep this running in a separate terminal/window.

### Option 2: Run as Background Service

```bash
cd "$HOME/merchant_mcp"
source "$HOME/context_mcp/load.env"
nohup python3 -m uvicorn src.server.mcp_server:app --host 0.0.0.0 --port 8000 > /tmp/mcp_server.log 2>&1 &
```

Check status: `curl http://localhost:8000/health`
Stop: `pkill -f uvicorn`

### Option 3: Using PM2 (If Available)

```bash
pm2 start "$HOME/merchant_mcp/start_server.sh" --name mcp-server
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
      "cwd": "/path/to/merchant_mcp",
      "env": {
        "DATABASE_URL": "postgresql://postgres@localhost:5432/mcp_product_context",
        "LITELLM_LLM_API_BASE": "https://grid.ai.juspay.net/",
        "LITELLM_LLM_API_KEY": "<set-from-env>",
        "LITELLM_EMBEDDING_API_BASE": "https://grid.ai.juspay.net/",
        "LITELLM_EMBEDDING_API_KEY": "<set-from-env>"
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

Compatibility endpoint:

```json
{
  "mcpServers": {
    "merchant-mcp": {
      "url": "http://localhost:8000/newton-hs"
    }
  }
}
```

Supported MCP endpoints:

- `/sse`: GET for SSE, POST for JSON-RPC compatibility
- `/newton-hs`: GET for SSE, POST for JSON-RPC compatibility
- `/mcp`: GET for SSE, POST for JSON-RPC compatibility
- `/tools/call`: POST for direct tool calls or JSON-RPC compatibility

## Management Script

Use the consolidated management script for day-to-day operations:

```bash
# Host the HTTP tool server
python3 scripts/manage_mcp.py serve --host 0.0.0.0 --port 8000 --reload

# Ingest a document/API spec into documents, text_chunks, endpoint_specs, and error_codes as applicable
python3 scripts/manage_mcp.py ingest ./docs/API_COOKBOOK.md
python3 scripts/manage_mcp.py ingest ./api_specs/openapi.json --type json

# Ingest generated S2S API documentation from docs.zip into documents, chunks, api_specs_v2, and endpoint_specs
python3 scripts/manage_mcp.py ingest-docs-zip "$HOME/Downloads/docs.zip"
python3 scripts/manage_mcp.py ingest-docs-zip "$HOME/Downloads/docs.zip" --dry-run

# Ingest generated callback documentation. Callback specs are update-only:
# existing newton.callbacks.* records are refreshed; missing callback records are skipped.
python3 scripts/manage_mcp.py ingest-docs-zip "$HOME/Downloads/callback-docs.zip"
python3 scripts/manage_mcp.py ingest-docs-zip "$HOME/Downloads/callback-docs.zip" --skip-embeddings

# Ingest NPCI circular PDFs from this repo's downloads folder into documents/text_chunks
python3 scripts/manage_mcp.py ingest-npci-circulars --directory downloads/npci_circulars
python3 scripts/manage_mcp.py ingest-npci-circulars --directory downloads/npci_circulars --dry-run

# Add/update a rich API specification
python3 scripts/manage_mcp.py add-api-spec ./api_specs/my_api_spec_v2.json

# Add direct context for client Q&A
python3 scripts/manage_mcp.py add-context --title "Merchant onboarding note" --content-file ./notes/onboarding.md

# Inspect database state
python3 scripts/manage_mcp.py tables
python3 scripts/manage_mcp.py stats
```

## Agent-Facing Tools (23 Total)

### Understanding Phase
- `get_api_spec` - Get complete API specification
- `get_integration_guide` - Get step-by-step integration guide
- `get_flow` - Get ordered API call sequence
- `search_docs` - Search documentation chunks using semantic search. For NPCI circulars, pass `namespace: "npci_circulars"`.

### Building Phase
- `generate_payload` - Generate valid JSON payload
- `get_code_example` - Get working code examples
- `get_webhook_handler` - Get webhook handler with signature verification
- `validate_payload` - Validate payload against schema

### Testing Phase
- `test_sandbox` - Test API calls with annotated responses
- `explain_error` - Explain error codes with fixes
- `get_test_cases` - Get test scenarios
- `run_integration_check` - Check integration readiness

### Debugging Phase
- `diagnose_webhook` - Diagnose webhook issues
- `lookup_error_map` - Look up error code context
- `search_known_issues` - Search support KB

### API Specs
- `list_api_specs` - List available latest API specs
- `search_api_use_cases` - Find the right API for a business scenario using business-use-case vector search
- `get_api_spec` - Read the latest available rich API spec for an endpoint

### Document Search & Client Q&A
- `search_documents` - Hybrid document and contextual search
- `search_contextual_embeddings` - Search generated Q&A context
- `answer_question` - Answer client questions from ingested context

### NPCI Circulars
- NPCI circulars use the existing `documents` and `text_chunks` tables.
- Use `search_docs` with `namespace: "npci_circulars"` to retrieve circular chunks and their parent `doc_id`.

Ingestion and context-loading are intentionally not exposed as MCP tools. Use `scripts/manage_mcp.py ingest`, `ingest-docs-zip`, `ingest-npci-circulars`, `add-api-spec`, and `add-context` from an operator shell instead.

## Testing the Server

The integration agent UI at `/agent` is a ChatGPT-style chatbox. The app sends the user message to OpenCode and returns OpenCode's final response. OpenCode uses its configured MCP servers directly; the app does not parse tool-call JSON or pass MCP tool results back to OpenCode.

The integration agent uses OpenCode CLI by default for the synthesis/tool-command loop:

```bash
export AGENT_RESPONSE_BACKEND="opencode"
export OPENCODE_BIN_DIR="$HOME/.opencode/bin"
export OPENCODE_CLI_COMMAND="opencode run --dir /tmp/merchant_mcp_opencode --model litellm/open-fast --no-replay {prompt}"
export OPENCODE_CLI_TIMEOUT_SECONDS="600"
export OPENCODE_WORKDIR="/tmp/merchant_mcp_opencode"
```

The command is executed without a shell. `{prompt}` is replaced with the agent prompt as one command argument. `OPENCODE_BIN_DIR` is prepended to the child process `PATH`, so `OPENCODE_CLI_COMMAND` can use `opencode` without an absolute path. OpenCode runs from `/tmp/merchant_mcp_opencode` so it does not start repo file watchers on `.git`; this avoids `inotify_add_watch ... No space left on device` failures. The OpenCode config uses `JUSPAY_API_KEY`; the server maps the MCP `LITELLM_LLM_API_KEY` to that env var for the child process.

```bash
# Health check
curl http://localhost:8000/health

# Open the integration agent UI
# http://localhost:8000/agent

# List tools
curl http://localhost:8000/tools

# Call a tool
curl -X POST http://localhost:8000/tools/call \
  -H "Content-Type: application/json" \
  -d '{"name": "get_api_spec", "arguments": {"endpoint_id": "orders.create"}}'

# MCP JSON-RPC call
curl -X POST http://localhost:8000/newton-hs \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"search_api_use_cases","arguments":{"query":"debit customer UPI account for QR payment","limit":3}}}'

curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

## Data Ingested

- **431 documents**
- **7,744 text chunks**
- **2,702 contextual embeddings**
- **197 legacy endpoint specs**
- **184 v2 API specs**
- **254 error codes**
- **0 integration flows**

## Troubleshooting

If server won't start:
1. Check if port 8000 is free: `lsof -i :8000`
2. Check database connection: `psql -h localhost -U postgres -d mcp_product_context`
3. Check environment: `cat "$HOME/context_mcp/load.env"`

## Logs

Background mode logs: `/tmp/mcp_server.log`
