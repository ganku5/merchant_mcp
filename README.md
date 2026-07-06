# Merchant Integration MCP Server

Production-ready Model Context Protocol (MCP) server for Juspay/IBMB payment integration support.

[![Tools](https://img.shields.io/badge/tools-23-blue)](./docs/TOOLS.md)
[![Status](https://img.shields.io/badge/status-production%20ready-success)]()

## Overview

The Merchant Integration MCP Server provides AI coding assistants with 23 specialized tools to help merchants integrate payment APIs effectively. Built for the OpenCode ecosystem, it combines semantic search, intelligent code generation, comprehensive testing, and AI-powered debugging.

### Key Capabilities

- **Semantic Documentation Search** - Find relevant docs using vector embeddings
- **Intelligent Code Generation** - Multi-language SDKs with auth and error handling
- **Comprehensive Testing** - Test suites, lifecycle tracking, sandbox integration
- **AI-Powered Debugging** - Root cause analysis, webhook diagnostics, log analysis
- **Interactive Guides** - Personalized tutorials with visual flow diagrams
- **Security-First** - Signature verification, payload validation, best practices

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+ with pgvector extension
- [uv](https://docs.astral.sh/uv/) (dependency manager)
- Access to LiteLLM proxy (for embeddings)

### Option A: uv (Nix-independent)

Requires `uv` installed on your system. See [uv installation](https://docs.astral.sh/uv/getting-started/installation/).

```bash
# Clone
git clone git@github.com:ganku5/merchant_mcp.git
cd merchant_mcp/latest

# Sync dependencies (creates .venv automatically)
uv sync

# Configure environment
cp .env.example .env  # edit with your DB + LiteLLM credentials

# Run the server (default port 8000, or specify a port)
uv run python -m uvicorn src.server.mcp_server:app --host 0.0.0.0 --port 8001 --reload

# Or via the management script
uv run python scripts/manage_mcp.py serve --host 0.0.0.0 --port 8001

# Import check (no server start)
uv run python -c "from src.server.mcp_server import app; print('OK')"
```

### Option B: Nix + direnv (recommended for Nix users)

Requires [Nix](https://nixos.org/) with flakes enabled and [direnv](https://direnv.net/).

```bash
# Clone
git clone git@github.com:ganku5/merchant_mcp.git
cd merchant_mcp/latest

# direnv auto-loads the dev shell on cd
direnv allow

# Or manually enter the dev shell
nix develop

# Run (uv uses the Nix-provided Python)
uv run python -m uvicorn src.server.mcp_server:app --host 0.0.0.0 --port 8001 --reload
```

The Nix flake also builds a standalone package (no dev shell needed):

```bash
# Build the production package
nix build .#default

# Run the built binary (works from any directory, no uv/nix develop needed)
./result/bin/merchant-mcp
```

The Nix build uses [uv2nix](https://pyproject-nix.github.io/uv2nix/) to read `uv.lock` directly - no manual hash maintenance.

### Option C: Docker (via Nix)

Build a Docker image without a Dockerfile - Nix assembles the image from the same uv2nix venv:

```bash
# Build the image (outputs a tarball path)
nix build .#dockerImage --no-link --print-out-paths

# Load into Docker
docker load < $(nix build .#dockerImage --no-link --print-out-paths)

# Run (use --network host so the container can reach your host PostgreSQL)
docker run --rm -d --name mcp-test \
  --network host \
  -e DATABASE_URL=postgresql://postgres@localhost:5432/mcp_product_context \
  -e MCP_PORT=8002 \
  merchant-mcp:latest

# Test
curl -s http://localhost:8002/health | python -m json.tool

# Stop
docker stop mcp-test

# Or with just
just docker
docker load < result
```

`MCP_PORT` (default 8000) and `MCP_HOST` (default 0.0.0.0) are configurable via env vars.

The image is ~900MB (includes Python 3.11 + all deps from nix store). No Dockerfile needed - the image is defined in `nix/package.nix` using `dockerTools.buildImage`.

### Using just

The project includes a `justfile` for common commands (requires [just](https://github.com/casey/just), available in the Nix dev shell):

```bash
just           # list all commands
just run 8001  # run server on port 8001
just test      # run pytest
just lock      # regenerate uv.lock
just sync      # sync dependencies
just nix-build # nix build .#default
just docker    # build Docker image via nix
just shell     # nix develop
```

### Database Setup

```bash
# Create the database
psql -U postgres -c "CREATE DATABASE mcp_product_context;"

# Run migrations
psql -U postgres -d mcp_product_context -f migrations/create_api_specs_v2.sql
psql -U postgres -d mcp_product_context -f migrations/create_contextual_embeddings.sql

# Full schema init (documents, text_chunks, endpoint_specs, etc.)
uv run python scripts/full_ingest.py
```

### Verifying the Server

```bash
# Health check (DB connected?)
curl -s http://localhost:8001/health | python -m json.tool

# List all tools
curl -s http://localhost:8001/tools | python -m json.tool

# Call a tool
curl -s http://localhost:8001/tools/call \
  -H 'Content-Type: application/json' \
  -d '{"name": "list_api_specs", "arguments": {}}' | python -m json.tool

# SSE endpoint (MCP transport)
curl -s -N http://localhost:8001/sse
```

### Adding Dependencies

Dependencies are managed by `uv` using `pyproject.toml` + `uv.lock`. Nix users don't need to touch any hash - uv2nix reads `uv.lock` dynamically.

```bash
# Add a runtime dependency
uv add <package>

# Add a dev dependency
uv add --dev <package>

# Remove a dependency
uv remove <package>

# Regenerate lock file after manual pyproject.toml edits
uv lock
```

For Nix users: after `uv add`/`uv remove`, just rebuild. No hash update needed:

```bash
uv add httpx
nix build .#default  # picks up the new uv.lock automatically
```

### OpenCode Configuration

Add to your `~/.config/opencode/opencode.json`:

```json
{
  "servers": {
    "merchant-mcp": {
      "type": "local",
      "command": "bash -c 'cd /path/to/merchant_mcp/latest && PYTHONPATH=. uv run python src/server/mcp_server.py'"
    }
  }
}
```

## Tool Reference

The server exposes **37 MCP tools** organized into categories:

### Understanding (8 tools)
| Tool | Purpose |
|------|---------|
| `get_api_spec` | Get API specification for any endpoint |
| `get_api_spec_v2` | Enhanced API specs with headers, conditions, samples |
| `list_api_specs_v2` | List all available API specifications |
| `list_api_versions` | Get version history for an endpoint |
| `search_docs` | Semantic search across documentation |
| `search_contextual_embeddings` | Q&A-based semantic search |
| `generate_contextual_embeddings` | Generate Q&A embeddings for documents |
| `get_flow` | Get API call flow sequences |

### Building (4 tools)
| Tool | Purpose |
|------|---------|
| `generate_payload` | Smart payload generation with defaults |
| `get_code_example` | Production-ready SDK code (Python, Node.js, Java, Go, PHP) |
| `get_webhook_handler` | Webhook handler with signature verification |
| `validate_payload` | Deep validation with business rules |

### Testing (8 tools)
| Tool | Purpose |
|------|---------|
| `test_sandbox` | Test in sandbox (mock/sandbox/record modes) |
| `get_test_cases` | Comprehensive test scenarios |
| `generate_test_suite` | Complete test suite with coverage matrix |
| `run_transaction_lifecycle_test` | End-to-end transaction testing |
| `export_test_suite` | Export to Postman, JMeter, cURL, pytest |
| `run_integration_check` | Automated integration verification |
| `validate_integration_readiness` | Requirement validation |
| `explain_error` | Error code explanations |

### Debugging (8 tools)
| Tool | Purpose |
|------|---------|
| `diagnose_webhook` | Basic webhook diagnosis |
| `run_deep_webhook_diagnostics` | Comprehensive webhook analysis (SSL, DNS, signatures) |
| `analyze_issue_with_ai` | AI-powered root cause analysis |
| `analyze_webhook_logs` | Webhook log trend analysis |
| `diagnose_api_error` | Pattern-based error diagnosis |
| `find_similar_incidents` | Historical incident lookup |
| `lookup_error_map` | Error code context mapping |
| `search_known_issues` | Semantic issue search |

### Guides (6 tools)
| Tool | Purpose |
|------|---------|
| `get_interactive_guide` | Personalized integration tutorials |
| `generate_flow_diagram` | Mermaid API flow diagrams |
| `generate_error_decision_tree` | Visual error handling flows |
| `get_onboarding_wizard` | Progress-tracked onboarding |
| `get_step_by_step_walkthrough` | Detailed endpoint walkthroughs |
| `explain_concept` | In-depth concept explanations |

### System (1 tool)
| Tool | Purpose |
|------|---------|
| `health_check` | Server health and database stats |

## Usage Examples

### Example 1: Generate UPI Payment Payload

```python
# Ask your AI assistant:
"Generate a payload for initiating a UPI collect payment"

# Behind the scenes, the MCP tool generates:
{
  "payeeVpaHandle": "merchant@juspay",
  "payeeName": "Test Merchant",
  "payerVpaHandle": "customer@okaxis",
  "amount": "1000.00",
  "merchantRequestId": "2024090112345678ABCD",
  "merchantId": "TEST123",
  "upiTxnType": "COLLECT",
  "description": "Payment for Order #12345"
}
```

### Example 2: Get Python SDK Code

```python
# Ask your AI assistant:
"Show me Python code to handle webhooks with signature verification"

# The tool generates production-ready code:
import hmac
import hashlib
from flask import request, abort

WEBHOOK_SECRET = "whsec_your_secret_here"

@app.route('/webhook', methods=['POST'])
def webhook_handler():
    # Get raw body (important!)
    body = request.get_data()
    
    # Verify signature
    signature = request.headers.get('X-Juspay-Signature')
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected):
        abort(401, "Invalid signature")
    
    # Process webhook
    event = request.get_json()
    if event['event'] == 'order.charged':
        fulfill_order(event['order_id'])
    
    return 'OK', 200
```

### Example 3: Diagnose Webhook Issues

```python
# Ask your AI assistant:
"My webhook isn't receiving events, can you diagnose it?"

# Provide your webhook URL and the tool will check:
# - DNS resolution
# - SSL certificate validity
# - Endpoint accessibility
# - Signature configuration
# - Response requirements
```

### Example 4: Run Integration Tests

```python
# Ask your AI assistant:
"Generate a test suite for the transaction init endpoint"

# The tool generates:
# - Happy path tests
# - Validation error tests
# - Edge case tests
# - Security tests (SQL injection, XSS)
# - Concurrency tests (idempotency)
# 
# And exports to Postman, JMeter, cURL, or pytest!
```

### Example 5: Visualize Payment Flow

```python
# Ask your AI assistant:
"Show me the UPI payment flow diagram"

# Generates Mermaid sequence diagram:
sequenceDiagram
    participant C as Customer
    participant M as Merchant
    participant J as Juspay/IBMB
    participant U as UPI App
    
    C->>M: Initiate Payment
    M->>J: POST /transaction/initiate
    J-->>M: Response with Intent URL
    M-->>C: Redirect to UPI App
    C->>U: Complete Payment
    U->>J: Payment Confirmation
    J->>M: Webhook: order.charged
    M-->>C: Payment Success Page
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenCode / Claude / Cursor               │
└───────────────────────┬─────────────────────────────────────┘
                        │ MCP Protocol
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                 Merchant MCP Server (FastMCP)               │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Building   │  │   Testing    │  │   Debugging  │      │
│  │    Tools     │  │    Tools     │  │    Tools     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Understanding│  │    Guides    │  │   Advanced   │      │
│  │    Tools     │  │    Tools     │  │    Tools     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└───────────┬─────────────────────────────────────────────────┘
            │
    ┌───────┴───────┐
    ▼               ▼
┌─────────┐   ┌──────────┐
│PostgreSQL│   │ LiteLLM  │
│+pgvector│   │  Proxy   │
└─────────┘   └──────────┘
```

## Database Schema

The system uses PostgreSQL with the following key tables:

- `documents` - Document metadata
- `text_chunks` - Chunked document content with embeddings
- `api_specs_v2` - API specifications
- `api_fields` - API field definitions
- `api_headers` - Request/response headers
- `api_conditions` - Conditional logic
- `api_samples` - Request/response examples
- `contextual_embeddings` - Q&A pairs for semantic search
- `endpoint_specs` - Legacy endpoint specifications
- `error_codes` - Error code definitions
- `test_scenarios` - Test case definitions
- `known_issues` - Known issues and resolutions

## Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/mcp_product_context

# LiteLLM
LITELLM_PROXY_URL=https://grid.ai.juspay.net/
LITELLM_API_KEY=your_api_key
LLM_MODEL=openai/kimi-latest
EMBEDDING_MODEL=openai/embed-marqo-ecommerce-b

# Optional: Real Sandbox
IBMB_SANDBOX_URL=https://sandbox-api.ibmb.example.com
```

### File Ingestion

```bash
# Ingest PDF documentation
uv run python ingest.py docs/ibmb-api-guide.pdf

# Ingest API specs
uv run python scripts/ingest_api_specs.py

# Generate contextual embeddings
uv run python scripts/generate_contextual_embeddings.py --doc-id=ibmb-api-guide
```

## Development

### Running Tests

Smoke tests hit a running server (via Docker or `uv run`). Start the server first, then run pytest:

```bash
# Start server in Docker
docker run --rm -d --name mcp-test --network host \
  -e DATABASE_URL=postgresql://postgres@localhost:5432/mcp_product_context \
  -e MCP_PORT=8002 \
  merchant-mcp:latest

# Run smoke tests against it
MCP_URL=http://localhost:8002 uv run pytest tests/test_smoke.py -v

# Stop the container
docker stop mcp-test
```

Or test against a locally running server:

```bash
# Terminal 1: start server
uv run python -m uvicorn src.server.mcp_server:app --port 8001

# Terminal 2: run tests
MCP_URL=http://localhost:8001 uv run pytest tests/test_smoke.py -v
```

Default URL is `http://localhost:8000` if `MCP_URL` is not set.

### Adding New Tools

1. Create tool implementation in `src/tools/`
2. Register it in `src/server/tool_registry.py`
3. Add test in `tests/`

### Adding Dependencies

See [Quick Start - Adding Dependencies](#adding-dependencies) above. Short version:

```bash
uv add <package>      # add runtime dep
uv add --dev <package> # add dev dep
uv remove <package>    # remove
```

Nix users: `nix build .#default` picks up the change from `uv.lock` automatically. No hash update needed.

### Project Structure

```
merchant_mcp/latest/
├── src/
│   ├── server/
│   │   ├── mcp_server.py          # Main MCP server (FastAPI)
│   │   └── tool_registry.py       # Tool registration
│   ├── tools/                      # Tool implementations
│   │   ├── admin_tools.py
│   │   ├── api_specs_v2_tools.py
│   │   ├── building_tools.py
│   │   ├── code_templates/        # Multi-language SDK generators
│   │   └── ...
│   ├── utils/
│   │   ├── config.py              # Environment config
│   │   ├── database.py            # asyncpg + pgvector
│   │   └── llm.py                 # LiteLLM client
│   ├── ingestion/                  # Document ingestion pipeline
│   └── schema/                    # Pydantic models
├── migrations/                    # SQL migrations
├── scripts/                       # Utility + ingestion scripts
├── tests/
├── pyproject.toml                 # uv-managed dependencies
├── uv.lock                        # Locked dependencies
├── flake.nix                      # Nix flake (uv2nix + devShell)
├── nix/                           # Nix modules (package, devshell, pre-commit)
├── justfile                       # Task runner
└── .envrc                         # direnv config
```

## API Specification Format

### V2 API Spec Structure

```json
{
  "endpoint_id": "ibmb.merchant.transaction.init",
  "method": "POST",
  "path": "/api/merchants/v1/transaction/initiate",
  "api_version": "v1",
  "description": "Initiate a UPI transaction",
  "headers": {
    "request": [
      {"name": "X-API-Key", "required": true, "type": "string"},
      {"name": "Content-Type", "required": true, "value": "application/json"}
    ]
  },
  "request_fields": [
    {
      "name": "payeeVpaHandle",
      "type": "string",
      "required": true,
      "description": "Payee VPA address",
      "pattern": "^[a-zA-Z0-9._-]+@[a-zA-Z]+$"
    }
  ],
  "conditions": [
    {
      "condition": "upiTxnType == 'COLLECT'",
      "required_fields": ["payerVpaHandle"]
    }
  ],
  "samples": {
    "request": {...},
    "response_success": {...},
    "response_error": {...}
  }
}
```

Insert via:
```python
insert_api_spec_v2(spec=json_spec)
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Contribution Guidelines

- Follow PEP 8 for Python code
- Add tests for new tools
- Update documentation
- Ensure backward compatibility

## Support

- **Documentation**: [docs.juspay.net](https://docs.juspay.net)
- **Issues**: [GitHub Issues](https://github.com/juspay/merchant-mcp/issues)
- **Discussions**: [GitHub Discussions](https://github.com/juspay/merchant-mcp/discussions)
- **Email**: merchant-support@juspay.net

## Roadmap

- [x] Phase 1: Building Tools Enhancement
- [x] Phase 2: Testing Infrastructure
- [x] Phase 3: Advanced Debugging
- [x] Phase 4: Documentation & Intelligence
- [x] uv + Nix (uv2nix) build system
- [x] Docker image via nix (dockerTools)
- [ ] More language SDKs (Rust, .NET)
- [ ] Real-time collaboration features

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

- OpenCode team for MCP protocol support
- Juspay/IBMB API team for documentation and specifications
- Contributors and testers from the merchant community

---

**Built with ❤️ by the Juspay Integration Team**
