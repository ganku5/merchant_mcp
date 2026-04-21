# Merchant Integration MCP

A production-ready Model Context Protocol (MCP) server for Juspay payment integration support. Enables AI coding assistants to provide accurate, context-aware help for merchant developers integrating payment APIs.

## Features

- **14 MCP Tools** across 4 phases: Understanding, Building, Testing, Debugging
- **Ground Truth Data** for 3 core endpoints: orders.create, order.status, refund.create
- **18 Error Codes** with full context, retry guidance, and fix suggestions
- **Semantic Search** with embeddings for documentation lookup
- **Multi-language Support** for code examples (Python, Node.js, Java, Go, PHP)
- **Webhook Diagnostics** with HMAC-SHA256 signature verification
- **Production Ready** with Docker, K8s, health checks, and monitoring

## Quick Start

### Using Docker Compose

```bash
# Start the server with PostgreSQL
docker-compose up -d

# Verify health
curl http://localhost:8000/health

# List available tools
curl http://localhost:8000/tools
```

### Manual Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Initialize database
python scripts/init_full_database.py

# 3. Load ground truth data
python scripts/load_ground_truth.py

# 4. Start server
python -m uvicorn src.server.mcp_server:app --host 0.0.0.0 --port 8000
```

## Available Tools

### Understanding Phase (4 tools)

| Tool | Description |
|------|-------------|
| `get_api_spec` | Get complete API spec with fields, schemas, examples |
| `get_integration_guide` | Step-by-step integration guide for use cases |
| `get_flow` | Ordered API sequence with decision points |
| `search_docs` | Semantic search across documentation |

### Building Phase (4 tools)

| Tool | Description |
|------|-------------|
| `generate_payload` | Generate valid JSON payload for endpoints |
| `get_code_example` | Working code examples in multiple languages |
| `get_webhook_handler` | Webhook handler with signature verification |
| `validate_payload` | Validate payload against schema |

### Testing Phase (4 tools)

| Tool | Description |
|------|-------------|
| `test_sandbox` | Test API calls with annotated responses |
| `explain_error` | Error code explanation with fix suggestions |
| `get_test_cases` | Test scenarios for flow types |
| `check_integration` | Pre-production checklist |

### Debugging Phase (2 tools)

| Tool | Description |
|------|-------------|
| `diagnose_webhook` | Webhook diagnostics with signature check |
| `lookup_error_map` | Error code with full context map |
| `search_known_issues` | Search support KB for issues |

## API Examples

### Get API Specification
```bash
curl -X POST http://localhost:8000/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "name": "get_api_spec",
    "arguments": {"endpoint_id": "orders.create"}
  }'
```

### Generate Payload
```bash
curl -X POST http://localhost:8000/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_payload",
    "arguments": {
      "endpoint_id": "orders.create",
      "params": {"amount": 5000}
    }
  }'
```

### Validate Payload
```bash
curl -X POST http://localhost:8000/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "name": "validate_payload",
    "arguments": {
      "endpoint_id": "orders.create",
      "payload": {
        "order_id": "test_123",
        "amount": 10000,
        "currency": "INR",
        "customer_email": "test@example.com",
        "return_url": "https://example.com/callback"
      }
    }
  }'
```

### Diagnose Webhook
```bash
curl -X POST http://localhost:8000/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "name": "diagnose_webhook",
    "arguments": {
      "headers": {
        "X-Juspay-Signature": "abc123...",
        "Content-Type": "application/json"
      },
      "body": "{\"event\":\"order.charged\",\"order_id\":\"ord_123\"}",
      "webhook_secret": "whsec_..."
    }
  }'
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql://postgres@localhost:5432/merchant_mcp` |
| `DB_HOST` | Database host | `localhost` |
| `DB_PORT` | Database port | `5432` |
| `DB_NAME` | Database name | `merchant_mcp` |
| `DB_USER` | Database user | `postgres` |
| `DB_PASSWORD` | Database password | `` |
| `LITELLM_LLM_API_KEY` | LLM API key | - |
| `LITELLM_EMBEDDING_API_KEY` | Embedding API key | - |
| `MCP_PORT` | Server port | `8000` |

## Testing

```bash
# Run comprehensive test suite
python scripts/test_all_tools.py

# Test specific tool groups
pytest tests/unit/test_understanding.py
pytest tests/unit/test_building.py
```

## Architecture

```
┌─────────────────┐
│   MCP Client    │  ← Claude/Cursor/VS Code
│  (AI Assistant) │
└────────┬────────┘
         │ MCP Protocol (SSE/HTTP)
         ▼
┌─────────────────┐
│  MCP Server     │  ← FastAPI + SSE
│  (this repo)    │
└────────┬────────┘
         │ SQL + Embeddings
         ▼
┌─────────────────┐
│   PostgreSQL    │  ← Ground truth + vectors
│   (pgvector)    │
└─────────────────┘
```

## Project Structure

```
merchant_mcp/
├── src/
│   ├── server/
│   │   └── mcp_server.py      # Main MCP server
│   ├── tools/
│   │   ├── understanding_tools.py  # 4 understanding tools
│   │   ├── building_tools.py       # 4 building tools
│   │   ├── testing_tools.py        # 4 testing tools
│   │   └── debugging_tools.py      # 3 debugging tools
│   ├── utils/
│   │   ├── database.py        # Unified DB layer
│   │   ├── llm.py             # LLM client
│   │   └── config.py          # Configuration
│   ├── schema/
│   │   └── *.py               # Pydantic models
│   └── ingestion/
│       └── pipeline.py        # Document ingestion
├── tests/
│   └── fixtures/ground_truth/ # Ground truth JSON files
├── scripts/
│   ├── init_full_database.py  # DB initialization
│   ├── load_ground_truth.py   # Load fixtures
│   └── test_all_tools.py      # Test suite
├── k8s/
│   └── deployment.yaml        # Kubernetes manifests
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## License

MIT
