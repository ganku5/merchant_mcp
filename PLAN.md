# Web Doc Ingestion - Implementation Plan

## Goal

Scrape a list of websites, convert their docs into the structured markdown format
the existing `docs_zip_ingester.py` expects, then feed them into the pipeline for
vectorization and storage.

## Architecture

```
URLs (env var + CLI file, merged + deduped)
  │
  ▼
1. Scraper (httpx)            → fetch raw HTML per URL
  │
  ▼
2. HTML → Markdown (markitdown) → already installed
  │
  ▼
3. LLM Transform (litellm)    → classify page (API/callback/multi-endpoint/skip)
   Configurable model           → extract + structure into target format
   Prompt = format spec +       → output one .md file per endpoint/callback
   real example from docs.zip
  │
  ▼
4. Write .md files to gitignored dir (scraped_docs/)
   + _conversion_log.json (source URL, doc type, endpoint IDs, skip reasons)
  │
  ▼
5. Ingest via existing ingest_docs_zip()  → zip the dir, call unchanged ingester
   (auto-detects API vs callback from Source endpoint:/Source callback type: line)
```

## Why write to files

- Inspectable: review LLM output before ingesting
- Re-runnable: ingest without re-scraping
- Zero changes to existing ingester code
- The dir gets zipped and fed to `ingest_docs_zip()` as-is

## Config (src/utils/config.py)

```python
# Web scraping / doc conversion
WEB_SCRAPER_URLS: str = ""           # comma-separated URLs, optional
WEB_SCRAPER_OUTPUT_DIR: str = "scraped_docs"  # gitignored
CONVERSION_LLM_MODEL: str = ""       # defaults to LLM_MODEL if empty
```

## URL sources

- `WEB_SCRAPER_URLS` env var (comma-separated)
- `--urls-file` CLI arg (one URL per line)
- Both merged + deduped

## LLM prompt strategy

The source is arbitrary third-party docs - structure unknown. The prompt:

### Step 1 - Classify the page
LLM reads raw markdown and determines:
- API endpoint doc → use `parse_api_markdown` format
- Callback/webhook doc → use `parse_callback_markdown` format
- Multi-endpoint page → split into multiple files, one per endpoint
- Not an API doc → skip with reason

### Step 2 - Extract and structure
LLM extracts from wherever they are on the page (tables, prose, code samples):
- HTTP method + path → `Source endpoint: \`POST /path\``
- Description/intro → `## Overview`
- Use case context → `## Business Use Case`
- Request fields → `## Request` with markdown field tables
- Response fields → `## Response` with markdown field tables
- JSON examples → fenced ```json blocks
- Callback event type → `Source callback type: \`...\``

### Prompt contents
1. Format spec (both API and callback templates with field table syntax)
2. One real example from docs.zip
3. Instructions: "Convert arbitrary web documentation into structured API spec
   markdown. Read the page, identify what API(s) or callbacks it documents, and
   output one markdown file per endpoint/callback in the exact format below."

The LLM decides the split. One page documenting 3 endpoints → 3 files.

## Target markdown format

### API endpoint doc

```markdown
# {Title} API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/vpas/validity`

## Overview

{description text}

## Business Use Case

{bullet points or prose}

## Integration Flow

1. {numbered steps}

## Endpoint

| Header | Required | Description | Value |
|---|---|---|---|
| Content-Type | required | Request content type | application/json |
| X-API-Key | required | Merchant API key | {api_key} |

## Request

### Field Reference

| Field | Type | Required | Description |
|---|---|---|---|
| customerVpa | string | required | VPA to validate |
| merchantId | string | required | Merchant identifier |

### Required Minimum

```json
{
  "customerVpa": "customer@okhdfcbank",
  "merchantId": "MERCH123"
}
```

## Response

### Response Field Reference

| Field | Type | Required | Description |
|---|---|---|---|
| isCustomerVpaValid | boolean | required | Whether VPA is valid |
| displayName | string | optional | Resolved display name |

### Success Response

```json
{
  "isCustomerVpaValid": true,
  "displayName": "Customer Name"
}
```
```

### Callback doc

```markdown
# {Callback Title} Callback Guide

Source callback type: `payment.captured`

## Overview

{description}

## Business Use Case

{context}

## When Newton Sends It

{trigger conditions}

## Delivery

| Property | Value |
|---|---|
| Category | payment |
| Status | success |
| Payload type | JSON |
| Source builder | Newton |

## Request Body

{description of payload}

```json
{
  "event": "payment.captured",
  "data": {
    "payment_id": "pay_123",
    "amount": 50000
  }
}
```

## Field Reference

| Field | Type | Required | Description |
|---|---|---|---|
| event | string | required | Event type |
| data.payment_id | string | required | Payment identifier |
| data.amount | integer | required | Amount in paise |

## Merchant Response

{what the merchant should return}
```

## Output structure

```
scraped_docs/                               # gitignored
├── post-api-v1-merchants-collect.md
├── post-api-v1-merchants-refund.md
├── post-callbacks-payment-captured.md
└── _conversion_log.json
```

### _conversion_log.json

```json
[
  {
    "source_url": "https://docs.example.com/api/collect",
    "doc_type": "api",
    "endpoint_id": "post-api-v1-merchants-collect",
    "output_file": "post-api-v1-merchants-collect.md",
    "status": "ok"
  },
  {
    "source_url": "https://docs.example.com/overview",
    "doc_type": null,
    "endpoint_id": null,
    "output_file": null,
    "status": "skipped",
    "reason": "No API endpoint or callback documentation found on this page."
  }
]
```

## CLI usage

```bash
# Scrape URLs from env, convert, write to scraped_docs/
uv run python scripts/ingest_web_docs.py

# Scrape from file
uv run python scripts/ingest_web_docs.py --urls-file urls.txt

# Review output
ls scraped_docs/
cat scraped_docs/_conversion_log.json | python -m json.tool

# Ingest (zip dir, call existing ingest_docs_zip)
uv run python scripts/ingest_web_docs.py --ingest

# All in one
uv run python scripts/ingest_web_docs.py --urls-file urls.txt --ingest
```

## Files to create/modify

| Piece | File | Est. lines | New dep? |
|---|---|---|---|
| WebDocIngester class | src/ingestion/web_scraper.py | ~200 | No |
| Config vars | src/utils/config.py | ~5 | No |
| CLI script | scripts/ingest_web_docs.py | ~60 | No |
| Test (mocked LLM + httpx) | tests/test_web_scraper.py | ~100 | No |
| .gitignore | add scraped_docs/ | +2 | No |
| Format spec prompt (embedded) | in web_scraper.py | ~60 lines | No |
| This plan | PLAN.md | reference | No |

~430 lines total, zero new dependencies, zero changes to existing ingester.

## Ingestion (unchanged)

The existing `ingest_docs_zip()` in `src/ingestion/docs_zip_ingester.py`:
- Reads .md files from a zip
- Auto-detects API vs callback from `Source endpoint:` vs `Source callback type:`
- Calls `parse_api_markdown()` or `parse_callback_markdown()`
- Stores in `api_specs_v2`, `endpoint_specs`, `text_chunks` tables with embeddings

We just zip the output dir and call it. No changes.

## PR strategy

Separate PR from `uv-nix-setup` base. No dependency on the opencode-replacement PR.

## Open items

- [ ] Rate limiting between scrapes (simple asyncio.sleep(1))
- [ ] Error handling for unreachable URLs (log + continue)
- [ ] LLM model configurable via CONVERSION_LLM_MODEL (defaults to LLM_MODEL)
- [ ] Test with mocked httpx + litellm, no external deps needed for CI
