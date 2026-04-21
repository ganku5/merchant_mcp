# Production Implementation Plan

## Objective
Build complete, production-ready Merchant Integration MCP - NOT a prototype.

## Critical Path to Production

### Phase A: Ground Truth Foundation (Week 1)
**Goal:** Establish authoritative API specifications that all tools rely on.

#### A1. Hand-Structure 3 Core Endpoints
- **Owner:** Integration Engineer
- **Duration:** 3 days
- **Deliverables:**
  - `/v1/orders/create` - Full EndpointSpec with all fields, constraints, examples
  - `/v1/payments/:id/status` - Complete polling pattern spec
  - `/v1/refunds/create` - Full refund logic with idempotency
  
**Schema completeness requirements:**
- Every field: name, type, required/optional, format, constraints, example
- Nested objects fully expanded
- Bank-specific notes where applicable
- Error codes that can be returned
- Rate limits
- Idempotency behavior
- Related webhooks

#### A2. Cross-Validation
- **Owner:** Second Integration Engineer
- **Duration:** 2 days
- **Process:**
  1. Independently structure same endpoints
  2. Compare and resolve discrepancies
  3. Test generated code against sandbox
  4. Document decisions in `docs/schema-decisions.md`

#### A3. Ground Truth Fixtures
- **Duration:** 1 day
- **Location:** `tests/fixtures/ground_truth/`
- **Files:**
  - `orders_create.json` - Complete EndpointSpec
  - `payment_status.json` - Complete EndpointSpec
  - `refunds_create.json` - Complete EndpointSpec
  - `error_codes_top50.json` - 50 most common errors

#### A4. Schema Sufficiency Test
- **Duration:** 1 day
- **Test:** Give Claude Code ONLY the structured spec, ask to generate payment handler
- **Pass Criteria:** Generated code passes sandbox validation on first try
- **If Fails:** Identify missing info in schema, add it, re-test

**Success Gate:** All 3 endpoints pass sufficiency test.

---

### Phase B: Complete Ingestion Pipeline (Week 2)
**Goal:** Automate population of knowledge store from all sources.

#### B1. OpenAPI Spec Ingestion
- **Duration:** 2 days
- **Requirements:**
  - Fetch from API gateway or Git repo
  - Parse OpenAPI 3.0 JSON/YAML
  - Resolve $ref references
  - Handle oneOf/anyOf unions
  - Map to EndpointSpec Pydantic models
  - Store in `endpoint_specs` table
- **Trigger:** CI hook on API release

#### B2. Error Code Registry Ingestion
- **Duration:** 1 day
- **Requirements:**
  - CSV/spreadsheet parser
  - LLM-assisted retry semantics extraction
  - Bank-specific notes extraction
  - Top 100 error codes minimum
  - Categories: retryable/terminal/merchant_action/system_error
  - Store in `error_codes` table

#### B3. SDK Documentation Ingestion
- **Duration:** 2 days
- **Requirements:**
  - GitHub fetcher for SDK repos
  - Extract README + inline docs
  - Parse code examples per language (Python, Node.js, Java, Go, PHP)
  - Tag examples by endpoint
  - Store in `code_templates` table
  - Both SDK and raw HTTP variants

#### B4. Integration Guide Ingestion
- **Duration:** 2 days
- **Requirements:**
  - Confluence API fetcher
  - MarkItDown parsing
  - Section segmentation by heading hierarchy
  - LLM-assisted flow extraction
  - Store in `integration_flows` table
  - Preserve step ordering

#### B5. Embedding Generation Pipeline
- **Duration:** 2 days
- **Requirements:**
  - LiteLLM + `embed-marqo-ecommerce-b`
  - Chunk text: 1000 chars, 200 overlap
  - Namespaces: guides, faqs, error_descriptions, known_issues
  - Expected volume:
    - Guides: ~200 chunks
    - FAQs: ~500 chunks
    - Error descriptions: ~200 chunks
  - Store in `embeddings` table with HNSW index

#### B6. Validation Pipeline (Stage 5)
- **Duration:** 1 day
- **Checks:**
  1. Schema validation - all entities pass Pydantic strict
  2. Reference integrity - endpoint refs in flows must exist
  3. Error code coverage - all error_responses must have ErrorCode entry
  4. Ground truth comparison - no regressions on 3 reference endpoints
  5. Embedding quality - top-3 recall > 0.8 on benchmark queries
- **Failure Action:** Alert + halt pipeline

---

### Phase C: MCP Server Implementation (Week 3)
**Goal:** Fully functional tool implementations with proper query routing.

#### C1. Query Routing Layer
- **Duration:** 1 day
- **Implementation:**
  - Structured fetch → PostgreSQL key lookup
  - Semantic search → pgvector cosine similarity
  - Parameter validation
  - Response formatting

#### C2. Understanding Tools (4 tools)
- **Duration:** 3 days
- **`get_api_spec`**:
  - Lookup endpoint by ID
  - Return complete EndpointSpec
  - Cache: 5-min LRU
  - Latency target: p95 < 100ms
  
- **`get_integration_guide`**:
  - Query IntegrationFlow by use_case
  - Return step-by-step flow
  - Include decision points
  
- **`get_flow`**:
  - Return ordered API sequence
  - Include branching logic
  
- **`search_docs`**:
  - Generate embedding for query
  - pgvector HNSW search
  - Return top-5 results with similarity scores
  - Latency target: p95 < 500ms

#### C3. Building Tools (4 tools)
- **Duration:** 3 days
- **`generate_payload`**:
  - Fetch EndpointSpec
  - Populate required fields with examples
  - Apply merchant-provided params
  - Return valid JSON
  
- **`get_code_example`**:
  - Lookup CodeTemplate by endpoint + language
  - If not exists, generate from template
  - Support: Python, Node.js, Java, Go, PHP
  - Include error handling
  
- **`get_webhook_handler`**:
  - Fetch WebhookEvent by event_type
  - Generate handler with signature verification
  - Include idempotency check
  
- **`validate_payload`**:
  - Fetch EndpointSpec
  - Type checking, format validation, enum membership
  - Min/max bounds, pattern matching
  - Return errors/warnings/suggestions
  - Bank-specific constraint checking

#### C4. Infrastructure
- **Duration:** 2 days
- FastAPI app with MCP SDK
- SSE transport endpoint `/sse`
- Asyncpg connection pool (10-20 connections)
- In-memory LRU cache (5-min TTL)
- Health check endpoint `/health`

---

### Phase D: Sandbox Integration (Week 4)
**Goal:** Live testing capabilities with real API interactions.

#### D1. Sandbox Proxy
- **Duration:** 2 days
- **Implementation:**
  - httpx async client
  - Forward validated payloads to sandbox API
  - Add authentication headers from session
  - Timeout handling (30s default)
  - Retry logic for transient failures

#### D2. Response Annotator
- **Duration:** 1 day
- Enrich each response field with explanation from EndpointSpec
- Highlight unexpected values
- Suggest next steps based on status

#### D3. Testing Tools (4 tools)
- **Duration:** 2 days
- **`test_sandbox`**:
  - Validate payload before sending
  - Call sandbox via proxy
  - Return annotated response
  - Log request/response for debugging
  
- **`explain_error`**:
  - Lookup ErrorCode by code
  - Correlate with request context
  - Return root cause, fix suggestions, bank notes
  - Include retry guidance
  
- **`get_test_cases`**:
  - Return 15-20 scenarios per flow
  - Include test card numbers
  - Expected inputs/outputs
  - Sandbox-specific notes
  
- **`check_integration`**:
  - Webhook URL reachability check
  - Signature verification test
  - Error handling coverage
  - Retry logic validation

#### D4. Session Management
- **Duration:** 1 day
- In-memory session store
- Sandbox API key per session
- 4-hour session expiry
- Key never exposed in responses

---

### Phase E: Debugging & Support KB (Week 5)
**Goal:** Complete debugging toolkit with known issues.

#### E1. Webhook Signature Engine
- **Duration:** 1 day
- HMAC-SHA256 and HMAC-SHA512 support
- Handle encoding edge cases
- Timestamp validation

#### E2. Webhook Diagnosis Tool
- **Duration:** 1 day
- Parse headers and body
- Verify signature
- Identify common mistakes
- Return ordered fix suggestions

#### E3. Support KB Ingestion
- **Duration:** 2 days
- Fetch from Zendesk/Freshdesk
- Filter resolved integration tickets
- Embedding-based clustering (DBSCAN)
- LLM pattern extraction
- Human review queue
- Store in `known_issues` table

#### E4. Remaining Debug Tools
- **Duration:** 1 day
- **`lookup_error_map`** - Full error context
- **`search_known_issues`** - Semantic search over KB

---

### Phase F: Production Hardening (Week 6)
**Goal:** Production-ready deployment.

#### F1. Authentication & Security
- **Duration:** 2 days
- API key validation for sandbox tools
- Production key rejection
- Input sanitization
- Rate limiting middleware
  - Read-only: 100/min per IP
  - Sandbox: 20/min per API key
  - Debug: 50/min per IP
  - Burst allowance: 2x per 10sec window
- Redis sliding window implementation

#### F2. Monitoring & Observability
- **Duration:** 2 days
- Prometheus metrics:
  - Tool call latency (p50, p95, p99)
  - Error rates by tool
  - Active connections
  - DB query latency
  - Embedding search latency
- Grafana dashboards
- Alerts:
  - p95 > 500ms for 5 min
  - Error rate > 1% for 5 min
  - Connection pool > 80%

#### F3. Analytics Pipeline
- **Duration:** 1 day
- Event logging to analytics DB
- Tool call distribution
- Query patterns
- Tool chain sequences
- Error-to-resolution rate
- Zero-result search tracking

#### F4. Deployment Infrastructure
- **Duration:** 1 day
- Dockerfile optimization
- Kubernetes manifests
- Horizontal pod autoscaling (2-4 replicas)
- Ingress with HTTPS
- Read replica for search queries

#### F5. Documentation
- **Duration:** 1 day
- Setup guide for Claude Code
- Setup guide for Cursor
- Setup guide for VS Code
- MCP registry manifest
- Operational runbook

---

## Acceptance Criteria

### Functional Requirements
- [ ] All 14 tools return valid responses
- [ ] 3 ground truth endpoints pass sufficiency test
- [ ] Generated code 80%+ passes sandbox on first try
- [ ] Error diagnosis 90%+ accurate root cause
- [ ] Webhook diagnosis resolves 80%+ issues

### Performance Requirements
- [ ] p95 latency < 500ms for structured fetch
- [ ] p95 latency < 1s for semantic search
- [ ] 50 concurrent sessions supported
- [ ] 99.5% uptime during business hours

### Security Requirements
- [ ] No credential leakage in responses/logs
- [ ] Rate limiting enforced
- [ ] Input sanitization on all params
- [ ] HTTPS only, no plaintext

### Operational Requirements
- [ ] Monitoring dashboards live
- [ ] Alerting configured
- [ ] Runbook documented
- [ ] CI/CD pipeline for updates
- [ ] Schema freshness checks automated

---

## Implementation Order

### Week 1: Ground Truth
1. Hand-structure 3 core endpoints
2. Cross-validation
3. Schema sufficiency test

### Week 2: Ingestion
1. OpenAPI spec ingestion
2. Error code registry
3. SDK documentation
4. Integration guides
5. Embeddings pipeline
6. Validation checks

### Week 3: Core Tools
1. Query routing
2. Understanding tools
3. Building tools
4. Caching layer

### Week 4: Sandbox
1. Sandbox proxy
2. Response annotator
3. Testing tools
4. Session management

### Week 5: Debugging
1. Webhook engine
2. Support KB ingestion
3. Debug tools

### Week 6: Production
1. Auth & rate limiting
2. Monitoring
3. Analytics
4. Deployment
5. Documentation

---

## Resource Requirements

### Personnel
- 1 Backend Engineer (full-time)
- 1 Integration Engineer (Week 1-2, part-time Week 3-6)
- 1 DevOps Engineer (Week 5-6)
- 1 Technical Writer (Week 6)

### Infrastructure
- PostgreSQL 16+ with pgvector
- Redis for rate limiting
- Kubernetes cluster
- Grafana + Prometheus
- LiteLLM proxy access

### External Services
- Juspay Sandbox API access
- Confluence API access
- Zendesk/Freshdesk API access
- GitHub access for SDK repos

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| API docs out of sync | High | CI automation + freshness alerts |
| LLM extraction quality | Medium | Human review + iterative refinement |
| Sandbox rate limits | Medium | Dedicated API key pool + caching |
| Performance under load | High | Load testing + horizontal scaling |
| Security vulnerabilities | Critical | Security review + penetration testing |

---

## Success Metrics

### Technical Metrics
- Schema completeness: 100%
- Tool availability: 99.5%
- Latency p95: < 500ms
- Code generation accuracy: 80%+

### Business Metrics
- Beta merchants: 3-5
- Integration time reduction: 50%
- Support ticket reduction: 30%
- Developer adoption: 100+ in Q1

---

**Start Date:** Immediate
**Target Completion:** 6 weeks from start
**Go-Live Criteria:** All acceptance criteria met
