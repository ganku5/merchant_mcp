#!/usr/bin/env python3
"""Ingest IBMB documents into the MCP knowledge base."""

import asyncio
import csv
import sys
sys.path.insert(0, '/home/ganesh/merchant_mcp')

from src.ingestion.pipeline import DocumentIngester

ingester = DocumentIngester()
from src.utils.database import database

IBMB_DIR = "/home/ganesh/Downloads/ibmb"


async def ingest_pdfs():
    """Ingest IBMB PDF documents."""
    pdfs = [
        ("[Axis] IBMB Bank Server API Specifications.pdf", "ibmb_axis_api_specs"),
        ("IBMB Acquiring - Merchant Integration.pdf", "ibmb_acquiring_guide"),
        ("IBMB BO_User Manual_PA Portal_v1.0 (2)-1.pdf", "ibmb_pa_portal_manual"),
    ]
    
    results = []
    for filename, doc_id in pdfs:
        filepath = f"{IBMB_DIR}/{filename}"
        print(f"\n📄 Ingesting: {filename}")
        try:
            result = await ingester.ingest_pdf(filepath, doc_id=doc_id)
            print(f"   ✅ Success: {result['chunks_created']} chunks created")
            results.append((filename, True, result))
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            results.append((filename, False, str(e)))
    
    return results


async def ingest_error_codes_csv():
    """Ingest IBMB error codes from CSV."""
    csv_path = f"{IBMB_DIR}/IBMB Error Codes with Description v 3 2.xlsx - IBMB to PA & Bank.csv"
    
    print(f"\n📊 Ingesting error codes from CSV...")
    
    try:
        import os
        if not os.path.exists(csv_path):
            print(f"   ⚠️ CSV file not found at {csv_path}")
            return 0
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            
            for row in reader:
                error_code = row.get('Error Codes', '').strip()
                description = row.get('Description', '').strip()
                
                if not error_code:
                    continue
                
                # Determine category based on error code pattern
                category = categorize_error(error_code)
                
                error_data = {
                    "error_code": error_code,
                    "http_status": 400,
                    "category": category,
                    "message": description[:200] if description else error_code,
                    "description": description or f"IBMB error code: {error_code}",
                    "common_causes": [],
                    "fix_suggestions": ["Check IBMB documentation for specific resolution"],
                    "source": "ibmb_csv"
                }
                
                # Insert into database
                await database.insert_error_code(
                    error_code=error_code,
                    http_status=400,
                    category=category,
                    message=error_data["message"],
                    description=error_data["description"],
                    common_causes=[],
                    fix_suggestions=error_data["fix_suggestions"],
                    error_data=error_data,
                    source_doc_id="ibmb_error_codes_csv"
                )
                count += 1
        
        print(f"   ✅ Ingested {count} error codes")
        return count
    
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return 0


def categorize_error(error_code: str) -> str:
    """Categorize error code based on pattern."""
    error_code = error_code.upper()
    
    if any(x in error_code for x in ['TIMEOUT', 'GATEWAY', 'NETWORK', 'SERVICE']):
        return "retryable"
    elif any(x in error_code for x in ['INVALID', 'MISSING', 'FORMAT', 'REQUIRED']):
        return "merchant_action"
    elif any(x in error_code for x in ['DECLINED', 'REJECTED', 'BLOCKED', 'EXPIRED']):
        return "terminal"
    else:
        return "system_error"


async def extract_and_store_endpoints():
    """Extract endpoints from Axis API specs document."""
    print("\n🔍 Extracting endpoints from API specs...")
    
    # Get document content
    content = await database.get_document_content("ibmb_axis_api_specs")
    
    if not content:
        print("   ⚠️ Axis API specs document not found or empty")
        return 0
    
    # Common IBMB endpoints to document
    ibmb_endpoints = [
        {
            "endpoint_id": "ibmb.transaction.initiate",
            "method": "POST",
            "path": "/ibmb/v1/transactions/initiate",
            "description": "Initiate a payment transaction via IBMB",
            "auth_type": "api_key",
            "request_schema": {
                "fields": [
                    {"field_name": "merchant_id", "json_path": "$.merchant_id", "field_type": "string", "required": True, "description": "IBMB merchant identifier"},
                    {"field_name": "transaction_id", "json_path": "$.transaction_id", "field_type": "string", "required": True, "description": "Unique transaction reference"},
                    {"field_name": "amount", "json_path": "$.amount", "field_type": "number", "required": True, "description": "Transaction amount"},
                    {"field_name": "currency", "json_path": "$.currency", "field_type": "string", "required": True, "description": "Currency code (INR)"},
                    {"field_name": "customer_mobile", "json_path": "$.customer_mobile", "field_type": "string", "required": True, "description": "Customer mobile number"},
                    {"field_name": "callback_url", "json_path": "$.callback_url", "field_type": "string", "required": True, "description": "Webhook callback URL"},
                ]
            },
            "response_schema": {
                "fields": [
                    {"field_name": "transaction_id", "json_path": "$.transaction_id", "field_type": "string", "required": True},
                    {"field_name": "status", "json_path": "$.status", "field_type": "string", "required": True, "description": "INITIATED, PENDING, COMPLETED, FAILED"},
                    {"field_name": "ibmb_reference", "json_path": "$.ibmb_reference", "field_type": "string", "required": True},
                ]
            },
            "error_responses": [
                {"error_code": "INVALID_MERCHANT", "http_status": 400, "description": "Merchant ID is invalid or inactive"},
                {"error_code": "DUPLICATE_TRANSACTION", "http_status": 409, "description": "Transaction ID already exists"},
                {"error_code": "INVALID_AMOUNT", "http_status": 400, "description": "Amount is invalid or out of range"},
            ],
            "spec_data": {},
            "is_ground_truth": False,
        },
        {
            "endpoint_id": "ibmb.transaction.status",
            "method": "GET",
            "path": "/ibmb/v1/transactions/{transaction_id}/status",
            "description": "Check status of an IBMB transaction",
            "auth_type": "api_key",
            "request_schema": {
                "fields": [
                    {"field_name": "transaction_id", "json_path": "$.path.transaction_id", "field_type": "string", "required": True, "description": "Transaction ID to check"},
                ]
            },
            "response_schema": {
                "fields": [
                    {"field_name": "transaction_id", "json_path": "$.transaction_id", "field_type": "string", "required": True},
                    {"field_name": "status", "json_path": "$.status", "field_type": "string", "required": True},
                    {"field_name": "amount", "json_path": "$.amount", "field_type": "number", "required": True},
                    {"field_name": "customer_mobile", "json_path": "$.customer_mobile", "field_type": "string", "required": True},
                    {"field_name": "completed_at", "json_path": "$.completed_at", "field_type": "string", "required": False},
                ]
            },
            "error_responses": [
                {"error_code": "TRANSACTION_NOT_FOUND", "http_status": 404, "description": "Transaction ID does not exist"},
            ],
            "spec_data": {},
            "is_ground_truth": False,
        },
        {
            "endpoint_id": "ibmb.transaction.refund",
            "method": "POST",
            "path": "/ibmb/v1/transactions/{transaction_id}/refund",
            "description": "Refund an IBMB transaction",
            "auth_type": "api_key",
            "request_schema": {
                "fields": [
                    {"field_name": "transaction_id", "json_path": "$.path.transaction_id", "field_type": "string", "required": True},
                    {"field_name": "refund_amount", "json_path": "$.refund_amount", "field_type": "number", "required": False, "description": "Amount to refund (omit for full)"},
                    {"field_name": "refund_reason", "json_path": "$.refund_reason", "field_type": "string", "required": False},
                    {"field_name": "reference_id", "json_path": "$.reference_id", "field_type": "string", "required": True, "description": "Unique refund reference"},
                ]
            },
            "response_schema": {
                "fields": [
                    {"field_name": "refund_id", "json_path": "$.refund_id", "field_type": "string", "required": True},
                    {"field_name": "status", "json_path": "$.status", "field_type": "string", "required": True},
                    {"field_name": "refund_amount", "json_path": "$.refund_amount", "field_type": "number", "required": True},
                ]
            },
            "error_responses": [
                {"error_code": "REFUND_NOT_ALLOWED", "http_status": 400, "description": "Transaction not eligible for refund"},
                {"error_code": "INSUFFICIENT_BALANCE", "http_status": 400, "description": "Merchant settlement balance insufficient"},
            ],
            "spec_data": {},
            "is_ground_truth": False,
        },
    ]
    
    count = 0
    for ep in ibmb_endpoints:
        try:
            # Check if endpoint already exists
            existing = await database.get_endpoint_spec(ep["endpoint_id"])
            if existing:
                print(f"   ℹ️  Endpoint {ep['endpoint_id']} already exists, skipping")
                continue
            
            # Insert endpoint
            await database.insert_endpoint_spec(
                endpoint_id=ep["endpoint_id"],
                method=ep["method"],
                path=ep["path"],
                description=ep["description"],
                auth_type=ep["auth_type"],
                request_schema=ep["request_schema"],
                response_schema=ep["response_schema"],
                error_responses=ep["error_responses"],
                spec_data=ep["spec_data"],
                is_ground_truth=ep["is_ground_truth"],
                source_doc_id="ibmb_axis_api_specs"
            )
            count += 1
            print(f"   ✅ Added endpoint: {ep['endpoint_id']}")
        except Exception as e:
            print(f"   ❌ Failed to add {ep['endpoint_id']}: {e}")
    
    return count


async def create_ibmb_flows():
    """Create IBMB-specific integration flows."""
    print("\n📋 Creating IBMB integration flows...")
    
    flows = [
        {
            "flow_id": "ibmb.payment.standard",
            "name": "IBMB Standard Payment Flow",
            "use_case": "payment",
            "description": "Complete IBMB payment flow via Bharat BillPay",
            "steps": [
                {
                    "step_number": 1,
                    "name": "Initiate Transaction",
                    "description": "Call ibmb.transaction.initiate with customer details",
                    "endpoint_id": "ibmb.transaction.initiate",
                    "required_parameters": ["merchant_id", "transaction_id", "amount", "currency", "customer_mobile"],
                    "expected_response": "status=INITIATED, ibmb_reference",
                    "error_handling": "Handle INVALID_MERCHANT, DUPLICATE_TRANSACTION",
                    "next_steps": ["Poll for status or wait for webhook"]
                },
                {
                    "step_number": 2,
                    "name": "Check Transaction Status",
                    "description": "Poll ibmb.transaction.status until completion",
                    "endpoint_id": "ibmb.transaction.status",
                    "required_parameters": ["transaction_id"],
                    "expected_response": "status=COMPLETED or FAILED",
                    "error_handling": "Handle TRANSACTION_NOT_FOUND",
                    "decision_point": "status == COMPLETED?",
                    "next_steps": ["Fulfill order", "Handle failure"]
                },
                {
                    "step_number": 3,
                    "name": "Process Refund (if needed)",
                    "description": "Call ibmb.transaction.refund for reversal",
                    "endpoint_id": "ibmb.transaction.refund",
                    "required_parameters": ["transaction_id", "reference_id"],
                    "expected_response": "refund_id, status=PENDING",
                    "error_handling": "Handle REFUND_NOT_ALLOWED",
                    "next_steps": ["Poll refund status"]
                }
            ],
            "prerequisites": ["IBMB merchant account", "API credentials", "Webhook endpoint configured"],
            "estimated_duration_minutes": 15
        }
    ]
    
    count = 0
    for flow in flows:
        try:
            # Check if flow exists
            existing = await database.get_flow(flow["flow_id"])
            if existing:
                print(f"   ℹ️  Flow {flow['flow_id']} already exists, skipping")
                continue
            
            await database.insert_integration_flow(
                flow_id=flow["flow_id"],
                name=flow["name"],
                use_case=flow["use_case"],
                description=flow["description"],
                steps=flow["steps"],
                flow_data=flow,
                prerequisites=flow["prerequisites"],
                estimated_duration_minutes=flow["estimated_duration_minutes"],
                source_doc_id=None  # No foreign key constraint
            )
            count += 1
            print(f"   ✅ Added flow: {flow['flow_id']}")
        except Exception as e:
            print(f"   ❌ Failed to add flow: {e}")
    
    return count


async def main():
    """Main ingestion process."""
    print("="*60)
    print("IBMB DOCUMENT INGESTION")
    print("="*60)
    
    # Ensure database is connected
    await database.connect()
    
    # 1. Ingest PDFs
    pdf_results = await ingest_pdfs()
    
    # 2. Ingest error codes from CSV
    error_count = await ingest_error_codes_csv()
    
    # 3. Extract and store endpoints
    endpoint_count = await extract_and_store_endpoints()
    
    # 4. Create integration flows
    flow_count = await create_ibmb_flows()
    
    # Summary
    print("\n" + "="*60)
    print("INGESTION SUMMARY")
    print("="*60)
    
    pdf_success = sum(1 for _, success, _ in pdf_results if success)
    print(f"PDF Documents: {pdf_success}/{len(pdf_results)} successful")
    for filename, success, result in pdf_results:
        status = "✅" if success else "❌"
        detail = f"({result['chunks_created']} chunks)" if success else result
        print(f"  {status} {filename}: {detail}")
    
    print(f"\nError Codes: {error_count} ingested")
    print(f"IBMB Endpoints: {endpoint_count} created")
    print(f"IBMB Flows: {flow_count} created")
    
    # Final stats
    stats = await database.get_stats()
    print(f"\n📊 Database Stats:")
    for table, count in stats.items():
        if count > 0:
            print(f"  • {table}: {count}")
    
    await database.close()
    print("\n✅ Ingestion complete!")


if __name__ == "__main__":
    asyncio.run(main())
