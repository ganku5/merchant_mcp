# Requirements: Merchant Integration MCP

## Functional Requirements

### FR-01: Schema Definition (Phase 0)
- Define EndpointSpec Pydantic model covering all merchant API surface
- Define PayloadField model with JSON schema constraints
- Define ErrorCode model with retry semantics
- Define WebhookEvent model with signature algorithm
- Define IntegrationFlow model with step sequences
- Hand-structure 3 core endpoints as ground truth

### FR-02: Ingestion Pipeline (Phase 1)
- Ingest OpenAPI/Swagger specs into EndpointSpec entities
- Ingest integration guides into IntegrationFlow step sequences
- Ingest error code registry into ErrorCode entities
- Ingest SDK code examples into CodeTemplate entities
- Generate embeddings using LiteLLM with embed-marqo-ecommerce-b model
- Ingest webhook event definitions into WebhookEvent entities
- Ingest support ticket patterns into KnownIssue entities
- Ingest sandbox test matrix into TestScenario entities
- Use LiteLLM with kimi-latest for LLM-powered extraction and generation tasks

### FR-03: MCP Server Core (Phase 2)
- Implement get_api_spec(endpoint_id, version?) tool
- Implement get_integration_guide(use_case) tool
- Implement get_flow(flow_type, scenario?) tool
- Implement search_docs(query) tool
- Implement generate_payload(endpoint_id, params) tool
- Implement get_code_example(endpoint_id, language) tool
- Implement get_webhook_handler(event_type, language) tool
- Implement validate_payload(endpoint_id, payload) tool
- MCP server accepts SSE transport connections
- Query routing: structured fetch vs semantic search

### FR-04: Sandbox Integration (Phase 3)
- Implement test_sandbox(endpoint, payload) tool with response annotation
- Implement explain_error(error_code, context?) tool
- Implement get_test_cases(flow_type) tool
- Implement check_integration(checklist_type) tool
- Sandbox credential management via MCP auth
- Request/response logging for debugging
- Sandbox-specific behavior annotations

### FR-05: Debugging and KB (Phase 4)
- Implement diagnose_webhook(headers, body, expected_sig) tool
- Implement lookup_error_map(error_code) tool
- Implement search_known_issues(description) tool
- Ingest support ticket patterns into KnownIssue entities (using kimi-latest for LLM pattern extraction)
- Build webhook signature verification engine
- Build error correlation engine

### FR-06: Distribution and Hardening (Phase 5)
- Publish MCP server to MCP registry
- Implement API key authentication for sandbox tools
- Implement rate limiting (per IP and per API key)
- Build usage analytics dashboard
- Create merchant-facing setup documentation
- Onboard 3-5 beta merchants with hands-on support
- Implement feedback collection mechanism
- Performance hardening to meet SLAs under load
- Automated integration freshness checks
- Operational runbook for on-call team

## Non-Functional Requirements

### NFR-01: Latency
- Tool response time (p95) < 500ms for structured fetch
- Tool response time (p95) < 1s for semantic search

### NFR-02: Availability
- MCP server uptime 99.5% during business hours

### NFR-03: Concurrency
- Support 50 concurrent MCP sessions

### NFR-04: Compatibility
- MCP protocol version: 2024-11-05 or later

### NFR-05: Security
- Read-only tools require no credentials
- Sandbox tools require authenticated session
- Production keys rejected for sandbox tools
- Session expires after 4 hours of inactivity

### NFR-06: Code Generation Quality
- 80%+ generated code passes sandbox on first attempt
- Support Python, Node.js, Java, Go, PHP

### NFR-07: Documentation Coverage
- 100% field documentation coverage
- Complete merchant setup guides for 3 AI tools

## Constraints
- Use PostgreSQL 16+ with pgvector for embeddings
- Python 3.11+ for implementation
- FastAPI + MCP SDK for server
- Docker containerization for deployment
- CI/CD via GitHub Actions

## LLM and Embedding Configuration
- **Embedding Model**: embed-marqo-ecommerce-b via LiteLLM
- **LLM**: kimi-latest via LiteLLM
- **Configuration**: Environment variables loaded from `context_mcp/load.env`
- **Libraries**: litellm >= 1.0.0 for unified API access

## Dependencies
```
litellm>=1.0.0
pgvector>=0.2.5
```
