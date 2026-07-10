#!/usr/bin/env python3
"""
Unified ingestion pipeline for Merchant MCP.

Usage:
    python scripts/ingest_all.py [--endpoints] [--docs] [--errors] [--all]

Options:
    --all       Ingest everything (default)
    --endpoints Ingest endpoint specifications
    --docs      Ingest PDF documents for semantic search
    --errors    Ingest error codes
    --flows     Ingest integration flows
    --test      Run tests after ingestion
"""

import argparse
import asyncio
import csv
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pdfplumber
from src.utils.database import database
from src.utils.llm import llm_client

# Configuration
IBMB_DIR = str(Path.home() / "Downloads/ibmb")
FIXTURES_DIR = str(PROJECT_ROOT / "tests/fixtures/ground_truth")


def load_json(path: str) -> dict:
    """Load JSON file."""
    with open(path) as f:
        return json.load(f)


def load_json_list(path: str) -> list:
    """Load JSON array from file."""
    with open(path) as f:
        data = json.load(f)
        return data if isinstance(data, list) else [data]


# =============================================================================
# ENDPOINT INGESTION
# =============================================================================


async def ingest_ground_truth_endpoints():
    """Ingest ground truth endpoint specifications."""
    print("\n" + "=" * 70)
    print("INGESTING GROUND TRUTH ENDPOINTS")
    print("=" * 70)

    endpoints = [
        ("orders_create_full.json", "orders.create"),
        ("order_status_full.json", "order.status"),
        ("refund_create_full.json", "refund.create"),
    ]

    count = 0
    for filename, endpoint_id in endpoints:
        path = os.path.join(FIXTURES_DIR, filename)
        if not os.path.exists(path):
            print(f"⚠️  File not found: {filename}")
            continue

        data = load_json(path)

        await database.insert_endpoint_spec(
            endpoint_id=data["endpoint_id"],
            method=data["method"],
            path=data["path"],
            description=data["description"],
            auth_type=data.get("auth_type", "bearer"),
            request_schema=data["request_schema"],
            response_schema=data["response_schema"],
            error_responses=data.get("error_responses", []),
            spec_data=data,
            is_ground_truth=True,
            source_doc_id=None,
        )
        count += 1
        print(f"✅ {endpoint_id}")

    print(f"\nIngested {count} ground truth endpoints")
    return count


async def ingest_ibmb_endpoints():
    """Ingest IBMB endpoint specifications from PDF analysis."""
    print("\n" + "=" * 70)
    print("INGESTING IBMB ENDPOINTS")
    print("=" * 70)

    # IBMB endpoints extracted from PDF
    ibmb_endpoints = [
        {
            "endpoint_id": "ibmb.axis.sdk.fetch",
            "method": "POST",
            "path": "/api/sdk/v1/fetch",
            "description": "Fetch decrypted transaction details from NBBL server (SDK Flow)",
            "request_fields": [
                {"name": "requestId", "type": "string", "required": True},
                {"name": "requestTs", "type": "string", "required": True},
                {"name": "requestSource", "type": "string", "required": True},
                {"name": "loginToken", "type": "string", "required": True},
                {"name": "url", "type": "string", "required": True},
                {"name": "device", "type": "object", "required": True},
            ],
            "response_fields": [
                {"name": "requestId", "type": "string"},
                {"name": "result", "type": "string"},
                {"name": "responseCode", "type": "string"},
                {"name": "responseMessage", "type": "string"},
            ],
        },
        {
            "endpoint_id": "ibmb.axis.sdk.auth",
            "method": "POST",
            "path": "/api/sdk/v1/auth",
            "description": "Authenticate and authorize transaction (SDK Flow)",
            "request_fields": [
                {"name": "requestId", "type": "string", "required": True},
                {"name": "loginToken", "type": "string", "required": True},
                {"name": "accountNumber", "type": "string", "required": True},
                {"name": "authMethod", "type": "string", "required": True},
            ],
            "response_fields": [
                {"name": "result", "type": "string"},
                {"name": "authToken", "type": "string"},
                {"name": "refId", "type": "string"},
            ],
        },
        {
            "endpoint_id": "ibmb.axis.sdk.pay",
            "method": "POST",
            "path": "/api/sdk/v1/pay",
            "description": "Process payment transaction (SDK Flow)",
            "request_fields": [
                {"name": "requestId", "type": "string", "required": True},
                {"name": "refId", "type": "string", "required": True},
                {"name": "authToken", "type": "string", "required": True},
                {"name": "credBlock", "type": "object", "required": True},
            ],
            "response_fields": [
                {"name": "result", "type": "string"},
                {"name": "txnId", "type": "string"},
                {"name": "status", "type": "string"},
            ],
        },
        {
            "endpoint_id": "ibmb.axis.sdk.status",
            "method": "POST",
            "path": "/api/sdk/v1/status",
            "description": "Check transaction status (SDK Flow)",
            "request_fields": [
                {"name": "requestId", "type": "string", "required": True},
                {"name": "refId", "type": "string", "required": True},
            ],
            "response_fields": [
                {"name": "result", "type": "string"},
                {"name": "status", "type": "string"},
                {"name": "txnId", "type": "string"},
            ],
        },
        {
            "endpoint_id": "ibmb.axis.web.fetch",
            "method": "POST",
            "path": "/api/web/v1/fetch",
            "description": "Fetch transaction details (Web Redirection Flow)",
            "request_fields": [
                {"name": "requestId", "type": "string", "required": True},
                {"name": "url", "type": "string", "required": True},
            ],
            "response_fields": [
                {"name": "result", "type": "string"},
                {"name": "txnDetails", "type": "object"},
            ],
        },
        {
            "endpoint_id": "ibmb.axis.web.pay",
            "method": "POST",
            "path": "/api/web/v1/pay",
            "description": "Process payment (Web Redirection Flow)",
            "request_fields": [
                {"name": "requestId", "type": "string", "required": True},
                {"name": "refId", "type": "string", "required": True},
                {"name": "accountNumber", "type": "string", "required": True},
            ],
            "response_fields": [
                {"name": "result", "type": "string"},
                {"name": "txnId", "type": "string"},
                {"name": "redirectUrl", "type": "string"},
            ],
        },
        {
            "endpoint_id": "ibmb.axis.web.status",
            "method": "POST",
            "path": "/api/web/v1/status",
            "description": "Check status (Web Redirection Flow)",
            "request_fields": [
                {"name": "requestId", "type": "string", "required": True},
                {"name": "refId", "type": "string", "required": True},
            ],
            "response_fields": [
                {"name": "result", "type": "string"},
                {"name": "status", "type": "string"},
            ],
        },
    ]

    count = 0
    for ep in ibmb_endpoints:
        try:
            await database.insert_endpoint_spec(
                endpoint_id=ep["endpoint_id"],
                method=ep["method"],
                path=ep["path"],
                description=ep["description"],
                auth_type="api_key_with_signature",
                request_schema={"fields": ep["request_fields"]},
                response_schema={"fields": ep["response_fields"]},
                error_responses=[
                    {
                        "error_code": "ERR001",
                        "http_status": 400,
                        "description": "Invalid request",
                    },
                    {
                        "error_code": "ERR002",
                        "http_status": 401,
                        "description": "Authentication failed",
                    },
                ],
                spec_data=ep,
                is_ground_truth=False,
                source_doc_id="ibmb_axis_api_specs",
            )
            count += 1
            print(f"✅ {ep['endpoint_id']}")
        except Exception as e:
            print(f"❌ {ep['endpoint_id']}: {e}")

    print(f"\nIngested {count} IBMB endpoints")
    return count


# =============================================================================
# ERROR CODE INGESTION
# =============================================================================


async def ingest_ground_truth_errors():
    """Ingest ground truth error codes."""
    print("\n" + "=" * 70)
    print("INGESTING GROUND TRUTH ERROR CODES")
    print("=" * 70)

    path = os.path.join(FIXTURES_DIR, "error_codes_full.json")
    if not os.path.exists(path):
        print("⚠️  File not found: error_codes_full.json")
        return 0

    errors = load_json_list(path)
    count = 0

    for error in errors:
        try:
            await database.insert_error_code(
                error_code=error["error_code"],
                http_status=error["http_status"],
                category=error["category"],
                message=error["message"],
                description=error.get("description", ""),
                common_causes=error.get("common_causes", []),
                fix_suggestions=error.get("fix_suggestions", []),
                error_data=error,
                source_doc_id=None,
            )
            count += 1
        except Exception as e:
            print(f"❌ {error['error_code']}: {e}")

    print(f"✅ Ingested {count} ground truth error codes")
    return count


async def ingest_ibmb_csv_errors():
    """Ingest IBMB error codes from CSV."""
    print("\n" + "=" * 70)
    print("INGESTING IBMB ERROR CODES FROM CSV")
    print("=" * 70)

    csv_path = os.path.join(
        IBMB_DIR, "IBMB Error Codes with Description v 3 2.xlsx - IBMB to PA & Bank.csv"
    )

    if not os.path.exists(csv_path):
        print(f"⚠️  CSV not found: {csv_path}")
        return 0

    count = 0
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            error_code = row.get("Error Codes", "").strip()
            description = row.get("Description", "").strip()

            if not error_code:
                continue

            # Determine category
            error_code_upper = error_code.upper()
            if any(
                x in error_code_upper
                for x in ["TIMEOUT", "GATEWAY", "NETWORK", "SERVICE", "UNAVAILABLE"]
            ):
                category = "retryable"
            elif any(
                x in error_code_upper
                for x in ["INVALID", "MISSING", "FORMAT", "REQUIRED", "NOT_FOUND"]
            ):
                category = "merchant_action"
            elif any(
                x in error_code_upper
                for x in ["DECLINED", "REJECTED", "BLOCKED", "EXPIRED", "UNAUTHORIZED"]
            ):
                category = "terminal"
            else:
                category = "system_error"

            error_data = {
                "error_code": error_code,
                "http_status": 400,
                "category": category,
                "message": description[:200] if description else error_code,
                "description": description or f"IBMB error code: {error_code}",
                "common_causes": [],
                "fix_suggestions": ["Check IBMB documentation for specific resolution"],
                "source": "ibmb_csv",
            }

            try:
                await database.insert_error_code(
                    error_code=error_code,
                    http_status=400,
                    category=category,
                    message=error_data["message"],
                    description=error_data["description"],
                    common_causes=[],
                    fix_suggestions=error_data["fix_suggestions"],
                    error_data=error_data,
                    source_doc_id="ibmb_error_codes_csv",
                )
                count += 1
                if count % 50 == 0:
                    print(f"  ... {count} error codes")
            except Exception as e:
                print(f"❌ {error_code}: {e}")

    print(f"✅ Ingested {count} IBMB error codes from CSV")
    return count


# =============================================================================
# DOCUMENT INGESTION (SEMANTIC SEARCH)
# =============================================================================


def clean_text(text: str) -> str:
    """Clean extracted text."""
    text = text.replace("\x00", "").replace("  ", " ")
    text = re.sub(r"\n\n\n+", "\n\n", text)
    return text.strip()


def chunk_text(text: str, size: int = 600, overlap: int = 100) -> List[str]:
    """Split text into chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        piece = text[start:end].strip()
        if len(piece) > 30:
            chunks.append(piece[:1200])
        start = max(end - overlap, start + 1)
    return chunks


async def ingest_pdf_document(pdf_path: str, doc_id: str):
    """Ingest a PDF document with embeddings for semantic search."""
    fname = os.path.basename(pdf_path)
    print(f"\n📄 {fname}")

    # Extract text
    print("   Extracting...")
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join([p.extract_text() or "" for p in pdf.pages])

    text = clean_text(text)
    print(f"   ✓ {len(text):,} chars")

    # Store document
    async with database.pool.acquire() as conn:
        await conn.execute("DELETE FROM text_chunks WHERE doc_id = $1", doc_id)
        await conn.execute("DELETE FROM documents WHERE doc_id = $1", doc_id)

        await conn.execute(
            """
            INSERT INTO documents (doc_id, filename, content, num_pages, total_chars, source_type)
            VALUES ($1, $2, $3, $4, $5, $6)
        """,
            doc_id,
            fname,
            text[:100000],
            0,
            len(text),
            "pdf",
        )

    # Chunk and embed
    chunks = chunk_text(text)
    print(f"   Chunking into {len(chunks)} chunks...")

    async with database.pool.acquire() as conn:
        for i in range(0, len(chunks), 2):
            batch = chunks[i : i + 2]

            try:
                embeds = await llm_client.embed(batch)
                for j, (ct, emb) in enumerate(zip(batch, embeds)):
                    await conn.execute(
                        """
                        INSERT INTO text_chunks (doc_id, chunk_index, chunk_text, embedding, namespace)
                        VALUES ($1, $2, $3, $4::jsonb, $5)
                    """,
                        doc_id,
                        i + j,
                        ct,
                        json.dumps(emb),
                        f"pdf_{doc_id}",
                    )
            except Exception as e:
                # Store without embeddings
                for j, ct in enumerate(batch):
                    await conn.execute(
                        """
                        INSERT INTO text_chunks (doc_id, chunk_index, chunk_text, embedding, namespace)
                        VALUES ($1, $2, $3, $4, $5)
                    """,
                        doc_id,
                        i + j,
                        ct,
                        None,
                        f"pdf_{doc_id}",
                    )

            await asyncio.sleep(0.3)

    total = await database.pool.fetchval(
        "SELECT COUNT(*) FROM text_chunks WHERE doc_id = $1", doc_id
    )
    embedded = await database.pool.fetchval(
        "SELECT COUNT(*) FROM text_chunks WHERE doc_id = $1 AND embedding IS NOT NULL",
        doc_id,
    )

    print(f"   ✓ Stored: {total} chunks ({embedded} with embeddings)")
    return len(chunks), embedded


async def ingest_all_documents():
    """Ingest all PDF documents."""
    print("\n" + "=" * 70)
    print("INGESTING DOCUMENTS FOR SEMANTIC SEARCH")
    print("=" * 70)

    pdfs = [
        ("[Axis] IBMB Bank Server API Specifications.pdf", "ibmb_axis_api_specs"),
        ("IBMB Acquiring - Merchant Integration.pdf", "ibmb_acquiring_guide"),
        ("IBMB BO_User Manual_PA Portal_v1.0 (2)-1.pdf", "ibmb_pa_portal_manual"),
    ]

    results = []
    for fname, doc_id in pdfs:
        path = os.path.join(IBMB_DIR, fname)
        if os.path.exists(path):
            try:
                chunks, embedded = await ingest_pdf_document(path, doc_id)
                results.append((doc_id, chunks, embedded))
            except Exception as e:
                print(f"   ❌ Failed: {e}")
        else:
            print(f"   ⚠️  Not found: {fname}")

    return results


# =============================================================================
# FLOW & WEBHOOK INGESTION
# =============================================================================


async def create_flows():
    """Create integration flows."""
    print("\n" + "=" * 70)
    print("CREATING INTEGRATION FLOWS")
    print("=" * 70)

    flows = [
        {
            "flow_id": "payment.standard",
            "name": "Standard Payment Flow",
            "use_case": "payment",
            "description": "Complete payment flow for web checkout",
            "steps": [
                {
                    "step_number": 1,
                    "name": "Create Order",
                    "description": "Call orders.create",
                    "endpoint_id": "orders.create",
                },
                {
                    "step_number": 2,
                    "name": "Redirect Customer",
                    "description": "Send to payment page",
                },
                {
                    "step_number": 3,
                    "name": "Handle Webhook",
                    "description": "Process order.charged webhook",
                },
            ],
            "prerequisites": ["API key", "Webhook endpoint"],
        },
        {
            "flow_id": "refund.standard",
            "name": "Standard Refund Flow",
            "use_case": "refund",
            "description": "Process refund for charged order",
            "steps": [
                {
                    "step_number": 1,
                    "name": "Check Order Status",
                    "description": "Verify CHARGED status",
                },
                {
                    "step_number": 2,
                    "name": "Create Refund",
                    "description": "Call refund.create",
                },
            ],
            "prerequisites": ["Order in CHARGED status"],
        },
        {
            "flow_id": "ibmb.payment.standard",
            "name": "IBMB Standard Payment Flow",
            "use_case": "payment",
            "description": "IBMB Bharat BillPay payment flow",
            "steps": [
                {
                    "step_number": 1,
                    "name": "Fetch Transaction",
                    "description": "Call ibmb.axis.sdk.fetch",
                },
                {
                    "step_number": 2,
                    "name": "Authenticate",
                    "description": "Call ibmb.axis.sdk.auth",
                },
                {
                    "step_number": 3,
                    "name": "Process Payment",
                    "description": "Call ibmb.axis.sdk.pay",
                },
            ],
            "prerequisites": ["IBMB merchant account"],
        },
    ]

    count = 0
    for flow in flows:
        try:
            await database.insert_integration_flow(
                flow_id=flow["flow_id"],
                name=flow["name"],
                use_case=flow["use_case"],
                description=flow["description"],
                steps=flow["steps"],
                flow_data=flow,
                prerequisites=flow.get("prerequisites"),
                source_doc_id=None,
            )
            count += 1
            print(f"✅ {flow['flow_id']}")
        except Exception as e:
            print(f"❌ {flow['flow_id']}: {e}")

    print(f"\nCreated {count} flows")
    return count


async def create_webhook_events():
    """Create webhook event definitions."""
    print("\n" + "=" * 70)
    print("CREATING WEBHOOK EVENTS")
    print("=" * 70)

    events = [
        {
            "event_type": "order.created",
            "description": "Triggered when order is successfully created",
            "payload_schema": {"order_id": "string", "status": "CREATED"},
        },
        {
            "event_type": "order.charged",
            "description": "Triggered when payment is successfully charged",
            "payload_schema": {
                "order_id": "string",
                "status": "CHARGED",
                "payment": {},
            },
        },
        {
            "event_type": "order.failed",
            "description": "Triggered when payment fails",
            "payload_schema": {
                "order_id": "string",
                "status": "FAILED",
                "error_code": "string",
            },
        },
        {
            "event_type": "refund.processed",
            "description": "Triggered when refund is processed",
            "payload_schema": {
                "refund_id": "string",
                "order_id": "string",
                "status": "SUCCESS",
            },
        },
    ]

    count = 0
    async with database.pool.acquire() as conn:
        for event in events:
            try:
                await conn.execute(
                    """
                    INSERT INTO webhook_events (event_type, description, payload_schema)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (event_type) DO UPDATE SET
                        description = EXCLUDED.description,
                        payload_schema = EXCLUDED.payload_schema
                """,
                    event["event_type"],
                    event["description"],
                    json.dumps(event["payload_schema"]),
                )
                count += 1
                print(f"✅ {event['event_type']}")
            except Exception as e:
                print(f"❌ {event['event_type']}: {e}")

    print(f"\nCreated {count} webhook events")
    return count


async def create_test_scenarios():
    """Create test scenarios."""
    print("\n" + "=" * 70)
    print("CREATING TEST SCENARIOS")
    print("=" * 70)

    scenarios = [
        {
            "scenario_id": "payment.success.card",
            "flow_type": "payment",
            "name": "Successful Card Payment",
            "description": "Test standard card payment flow",
            "input_data": {"order_id": "test_001", "amount": 10000, "currency": "INR"},
            "expected_http_status": 200,
        },
        {
            "scenario_id": "payment.decline.insufficient",
            "flow_type": "payment",
            "name": "Declined - Insufficient Funds",
            "description": "Test card decline scenario",
            "input_data": {"order_id": "test_decline", "amount": 1000000},
            "expected_http_status": 200,
        },
        {
            "scenario_id": "refund.full.success",
            "flow_type": "refund",
            "name": "Full Refund Success",
            "description": "Test full refund of charged order",
            "input_data": {
                "order_id": "existing_order",
                "unique_request_id": "refund_001",
            },
            "expected_http_status": 200,
        },
    ]

    count = 0
    async with database.pool.acquire() as conn:
        for sc in scenarios:
            try:
                await conn.execute(
                    """
                    INSERT INTO test_scenarios (scenario_id, flow_type, name, description, input_data, expected_http_status)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (scenario_id) DO UPDATE SET
                        description = EXCLUDED.description,
                        input_data = EXCLUDED.input_data
                """,
                    sc["scenario_id"],
                    sc["flow_type"],
                    sc["name"],
                    sc["description"],
                    json.dumps(sc["input_data"]),
                    sc["expected_http_status"],
                )
                count += 1
                print(f"✅ {sc['scenario_id']}")
            except Exception as e:
                print(f"❌ {sc['scenario_id']}: {e}")

    print(f"\nCreated {count} test scenarios")
    return count


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


async def show_summary():
    """Show final database summary."""
    print("\n" + "=" * 70)
    print("FINAL DATABASE SUMMARY")
    print("=" * 70)

    async with database.pool.acquire() as conn:
        stats = {
            "Documents": await conn.fetchval("SELECT COUNT(*) FROM documents"),
            "Text chunks": await conn.fetchval("SELECT COUNT(*) FROM text_chunks"),
            "Chunks with embeddings": await conn.fetchval(
                "SELECT COUNT(*) FROM text_chunks WHERE embedding IS NOT NULL"
            ),
            "Endpoints": await conn.fetchval("SELECT COUNT(*) FROM endpoint_specs"),
            "Error codes": await conn.fetchval("SELECT COUNT(*) FROM error_codes"),
            "Integration flows": await conn.fetchval(
                "SELECT COUNT(*) FROM integration_flows"
            ),
            "Webhook events": await conn.fetchval(
                "SELECT COUNT(*) FROM webhook_events"
            ),
            "Test scenarios": await conn.fetchval(
                "SELECT COUNT(*) FROM test_scenarios"
            ),
        }

        for key, value in stats.items():
            print(f"  {key}: {value}")

        # Show documents detail
        print("\n📄 Documents:")
        docs = await conn.fetch("""
            SELECT d.doc_id, d.filename, COUNT(tc.chunk_id) as chunks
            FROM documents d
            LEFT JOIN text_chunks tc ON d.doc_id = tc.doc_id
            GROUP BY d.doc_id, d.filename
            ORDER BY d.doc_id
        """)
        for d in docs:
            print(f"  • {d['doc_id']}: {d['chunks']} chunks ({d['filename'][:40]}...)")

        # Show endpoints
        print("\n🔌 Endpoints:")
        eps = await conn.fetch(
            "SELECT endpoint_id, method, path FROM endpoint_specs ORDER BY endpoint_id"
        )
        for e in eps:
            gt = (
                "GT"
                if e["endpoint_id"].startswith(("orders.", "order.", "refund."))
                else "IBMB"
            )
            print(f"  [{gt}] {e['method']:<6} {e['path']}")


async def main():
    parser = argparse.ArgumentParser(description="Unified ingestion for Merchant MCP")
    parser.add_argument(
        "--all", action="store_true", help="Ingest everything (default)"
    )
    parser.add_argument("--endpoints", action="store_true", help="Ingest endpoints")
    parser.add_argument("--docs", action="store_true", help="Ingest documents")
    parser.add_argument("--errors", action="store_true", help="Ingest error codes")
    parser.add_argument(
        "--flows", action="store_true", help="Ingest flows/webhooks/tests"
    )
    parser.add_argument(
        "--clear", action="store_true", help="Clear existing data first"
    )
    args = parser.parse_args()

    # Default to --all if nothing specified
    if not any([args.endpoints, args.docs, args.errors, args.flows]):
        args.all = True

    print("=" * 70)
    print("MERCHANT MCP - UNIFIED INGESTION PIPELINE")
    print("=" * 70)

    await database.connect()

    # Clear if requested
    if args.clear:
        print("\n⚠️  Clearing existing data...")
        async with database.pool.acquire() as conn:
            # Delete in correct order (child tables first)
            await conn.execute("DELETE FROM text_chunks")
            await conn.execute(
                "UPDATE endpoint_specs SET source_doc_id = NULL WHERE source_doc_id IS NOT NULL"
            )
            await conn.execute(
                "UPDATE error_codes SET source_doc_id = NULL WHERE source_doc_id IS NOT NULL"
            )
            await conn.execute(
                "UPDATE integration_flows SET source_doc_id = NULL WHERE source_doc_id IS NOT NULL"
            )
            await conn.execute("DELETE FROM documents")
            await conn.execute(
                "DELETE FROM endpoint_specs WHERE is_ground_truth = false"
            )
            await conn.execute(
                "DELETE FROM error_codes WHERE source_doc_id = 'ibmb_error_codes_csv'"
            )
            await conn.execute("DELETE FROM integration_flows")
            await conn.execute("DELETE FROM webhook_events")
            await conn.execute("DELETE FROM test_scenarios")
        print("   Cleared")

    results = {}

    # Ingest based on flags
    if args.all or args.endpoints:
        results["ground_truth_endpoints"] = await ingest_ground_truth_endpoints()
        results["ibmb_endpoints"] = await ingest_ibmb_endpoints()

    if args.all or args.errors:
        results["ground_truth_errors"] = await ingest_ground_truth_errors()
        results["ibmb_csv_errors"] = await ingest_ibmb_csv_errors()

    if args.all or args.flows:
        results["flows"] = await create_flows()
        results["webhooks"] = await create_webhook_events()
        results["test_scenarios"] = await create_test_scenarios()

    if args.all or args.docs:
        doc_results = await ingest_all_documents()
        results["documents"] = len(doc_results)
        results["total_chunks"] = sum(r[1] for r in doc_results)
        results["embedded_chunks"] = sum(r[2] for r in doc_results)

    # Show summary
    await show_summary()

    await database.close()
    print("\n✅ Ingestion complete!")

    return results


if __name__ == "__main__":
    results = asyncio.run(main())

    # Exit with error if nothing was ingested
    if results and sum(v for v in results.values() if isinstance(v, int)) == 0:
        sys.exit(1)
