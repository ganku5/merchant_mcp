# Merchant Integration MCP

## Overview
A Merchant Integration MCP (Model Context Protocol) server that enables merchant developers using AI coding assistants (Claude Code, Cursor, Copilot) to integrate Juspay's payment APIs with the accuracy and speed of an experienced Juspay integration engineer.

## Value Proposition
The merchant's LLM understands Juspay's APIs with the same depth as an experienced integration engineer. It generates correct payloads, debugs errors by looking up exact error codes, handles webhooks correctly, and validates integration completeness — without the merchant reading a single documentation page.

## Architecture

### Four-Phase Tool Surface
1. **Understanding**: get_api_spec, get_integration_guide, get_flow, search_docs
2. **Building**: generate_payload, get_code_example, get_webhook_handler, validate_payload
3. **Testing**: test_sandbox, explain_error, get_test_cases, check_integration
4. **Debugging**: diagnose_webhook, lookup_error_map, search_known_issues

### Technology Stack
- **Language**: Python 3.11+
- **Framework**: FastAPI + MCP SDK
- **Database**: PostgreSQL 16+ with pgvector extension
- **Transport**: SSE (Server-Sent Events)
- **Deployment**: Docker + Kubernetes

## Competitive Positioning
| Capability | Razorpay MCP | PayU MCP | Juspay Integration MCP |
|-----------|--------------|----------|------------------------|
| API operations | Yes | Yes | Not primary — separate operational MCP |
| Integration context (schemas, constraints) | No | No | Yes — full structured specs |
| Code generation per language | No | No | Yes — tested templates |
| Error diagnosis with retry semantics | No | No | Yes — structured error maps |
| Webhook handler generation | No | No | Yes — production-grade |
| Pre-production validation | No | No | Yes — automated checklist |
| Sandbox proxy with annotations | No | No | Yes — response explanations |
| Support KB search | No | No | Yes — semantic search |

## Key Design Principles
- **Vectorless-first retrieval**: API specs via exact key lookup, semantic search for guides only
- **Merchant-centric naming**: Tools map to developer workflow phases
- **Progressive trust**: Read-only tools require no credentials; sandbox tools require API key
- **Fail-safe validation**: Catch errors before production
- **Language-aware code generation**: Tested templates, not LLM improvisation

## Timeline
12-week implementation across 6 phases:
- Phase 0 (Week 1-2): Schema and ground truth
- Phase 1 (Week 3-4): Ingestion pipeline
- Phase 2 (Week 5-6): MCP server core
- Phase 3 (Week 7-8): Sandbox integration
- Phase 4 (Week 9-10): Debugging and KB
- Phase 5 (Week 11-12): Distribution and hardening

## Success Metrics
- 50% faster merchant integration time
- 30% fewer support tickets for integration issues
- 80%+ generated code passes sandbox on first attempt

## Project Files
- `requirements.md` — Scoped technical requirements
- `roadmap.md` — 12-week phase breakdown
- `state.md` — Current project status

## Created
2026-04-17
