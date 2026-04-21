# Roadmap: Merchant Integration MCP

## 12-Week Implementation Timeline

### Phase 0: Schema and Ground Truth (Week 1-2)
**Goal**: Define Pydantic models and hand-structure 3 core endpoints as ground truth

**Deliverables**:
- Pydantic models (EndpointSpec, PayloadField, ErrorCode, WebhookEvent, IntegrationFlow, CodeTemplate, TestScenario)
- 3 ground truth endpoints: orders/create, payments/status, refunds/create
- JSON fixtures in tests/fixtures/
- Schema validation tests
- Schema sufficiency test with Claude Code

**Success Criteria**: LLM given only EndpointSpec generates working payment handler that passes sandbox

---

### Phase 1: Ingestion Pipeline (Week 3-4)
**Goal**: Build ingestion pipeline to transform docs into structured entities

**Deliverables**:
- OpenAPI spec fetcher and parser
- Confluence/Markdown fetcher (MarkItDown integration)
- Error code registry ingestion (CSV -> ErrorCode)
- SDK code example extractor
- Webhook event spec parser
- Support KB fetcher and LLM pattern extractor
- Embedding generation pipeline (LiteLLM + embed-marqo-ecommerce-b)
- PostgreSQL schema with JSONB storage
- Validation pipeline with ground truth comparison

**Success Criteria**: All current API endpoints available as EndpointSpec entities with complete schema

---

### Phase 2: MCP Server Core (Week 5-6)
**Goal**: Implement first 8 tools (Understanding + Building phases)

**Tools to Implement**:
1. get_api_spec - Complete EndpointSpec with all fields
2. get_integration_guide - Step-by-step flow for use cases
3. get_flow - Ordered API call sequence
4. search_docs - Semantic search across guides and FAQs
5. generate_payload - Valid JSON payload generator
6. get_code_example - Working code in 5 languages
7. get_webhook_handler - Handler with signature verification
8. validate_payload - Validation with errors/warnings/suggestions

**Deliverables**:
- FastAPI project with MCP SDK integration
- Query routing and PostgreSQL connection pool
- SSE transport server
- In-memory LRU caching for structured fetches
- MCP Inspector compatibility

**Success Criteria**: Merchant LLM generates working payment handler without opening documentation

---

### Phase 3: Sandbox Integration (Week 7-8)
**Goal**: Add live sandbox interaction tools

**Tools to Implement**:
1. test_sandbox - Proxied API call with response annotation
2. explain_error - Structured error diagnosis
3. get_test_cases - Test scenarios with inputs/outputs
4. check_integration - Pre-production readiness checklist

**Deliverables**:
- Sandbox proxy with httpx async client
- Response annotator using EndpointSpec.response_schema
- Contextual error diagnosis (correlate error with request)
- Session management and credential caching
- Test case data with sandbox-specific notes
- Security review of credential handling

**Success Criteria**: Full cycle: generate code -> test in sandbox -> diagnose errors -> fix -> re-test in one conversation

---

### Phase 4: Debugging and Knowledge Base (Week 9-10)
**Goal**: Build debugging toolkit and ingest support KB

**Tools to Implement**:
1. diagnose_webhook - Identifies signature mismatches and parsing errors
2. lookup_error_map - Structured error definition with retry guidance
3. search_known_issues - Semantic search across resolved support tickets

**Deliverables**:
- Webhook signature verification engine (HMAC-SHA256, HMAC-SHA512)
- Webhook diagnosis logic chain
- Error map lookup with contextual enrichment
- Support ticket export and filtering pipeline
- Ticket clustering (embedding + DBSCAN using embed-marqo-ecommerce-b)
- LLM pattern extraction for KnownIssue entities (kimi-latest via LiteLLM)
- Human review interface for extracted patterns

**Success Criteria**: Webhook issue diagnosed and fixed within 30 seconds via LLM

---

### Phase 5: Distribution and Hardening (Week 11-12)
**Goal**: Production launch preparation

**Deliverables**:
- MCP registry manifest and submission
- Rate limiting (Redis-based sliding window)
- API key authentication for sandbox tools
- Usage analytics event pipeline
- Monitoring dashboard (Grafana + Prometheus)
- Usage analytics dashboard
- Merchant setup documentation (Claude Code, Cursor, VS Code)
- Beta merchant onboarding (3-5 merchants)
- Performance testing (50 concurrent sessions)
- Operational runbook
- Automated freshness checks (CI job)

**Success Criteria**: 3-5 merchants actively using MCP, 50% faster integration, 30% fewer tickets

---

## Dependencies Graph
```
Phase 0 (Schema)
  ↓
Phase 1 (Ingestion)
  ↓
Phase 2 (MCP Core) ←→ Phase 3 (Sandbox)
  ↓                      ↓
Phase 4 (Debugging) ←→ Phase 3 (cont.)
  ↓
Phase 5 (Distribution)
```

## Milestones
- Week 2: Schema validated against real integration task
- Week 4: All API endpoints structured in knowledge store
- Week 6: Merchant LLM generates correct payment handler
- Week 8: End-to-end generate/test/diagnose workflow
- Week 10: Full debugging toolkit operational
- Week 12: 3-5 merchants actively using MCP

## Success Metrics by Phase
- Phase 0: 100% type safety (mypy strict), 0 schema gaps after sufficiency test
- Phase 1: Top-3 semantic search recall > 0.8, < 5% parse failures
- Phase 2: p95 latency < 500ms, MCP Inspector compatible, 80%+ code quality
- Phase 3: 90%+ correct root cause identification, zero credential leakage
- Phase 4: diagnose_webhook resolution rate > 80%, KB coverage gaps < 30%
- Phase 5: p95 < 500ms at 50 concurrent, 3-5 beta merchants, 50% integration time reduction

## Risk Mitigation
| Risk | Mitigation |
|------|-----------|
| API docs stale | Wire ingestion to API release pipeline, CI alert on drift |
| Merchants don't discover MCP | Publish to MCP registry, include in onboarding emails |
| Sandbox rate limits | Dedicated API key pool, intelligent deduplication |
| Code template bugs | Ground truth test suite per language, CI sandbox runs |
| Competitor ships similar product | Focus on depth (error semantics, bank configs) not breadth |
