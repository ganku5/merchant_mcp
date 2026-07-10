#!/usr/bin/env python3
"""Simple IBMB ingestion - CSV only, no heavy PDF processing."""

import asyncio
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.database import database

IBMB_DIR = str(Path.home() / "Downloads/ibmb")


def categorize_error(error_code: str) -> str:
    """Categorize error code based on pattern."""
    error_code = error_code.upper()

    if any(
        x in error_code
        for x in ["TIMEOUT", "GATEWAY", "NETWORK", "SERVICE", "UNAVAILABLE"]
    ):
        return "retryable"
    elif any(
        x in error_code
        for x in ["INVALID", "MISSING", "FORMAT", "REQUIRED", "NOT_FOUND"]
    ):
        return "merchant_action"
    elif any(
        x in error_code
        for x in ["DECLINED", "REJECTED", "BLOCKED", "EXPIRED", "UNAUTHORIZED"]
    ):
        return "terminal"
    else:
        return "system_error"


async def ingest_error_codes_csv():
    """Ingest IBMB error codes from CSV."""
    csv_path = f"{IBMB_DIR}/IBMB Error Codes with Description v 3 2.xlsx - IBMB to PA & Bank.csv"

    print(f"📊 Ingesting error codes from CSV...")

    try:
        import os

        if not os.path.exists(csv_path):
            print(f"   ⚠️ CSV file not found at {csv_path}")
            return 0

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            count = 0

            for row in reader:
                error_code = row.get("Error Codes", "").strip()
                description = row.get("Description", "").strip()

                if not error_code:
                    continue

                category = categorize_error(error_code)

                error_data = {
                    "error_code": error_code,
                    "http_status": 400,
                    "category": category,
                    "message": description[:200] if description else error_code,
                    "description": description or f"IBMB error code: {error_code}",
                    "common_causes": [],
                    "fix_suggestions": [
                        "Check IBMB documentation for specific resolution"
                    ],
                    "source": "ibmb_csv",
                }

                await database.insert_error_code(
                    error_code=error_code,
                    http_status=400,
                    category=category,
                    message=error_data["message"],
                    description=error_data["description"],
                    common_causes=[],
                    fix_suggestions=error_data["fix_suggestions"],
                    error_data=error_data,
                    source_doc_id=None,
                )
                count += 1

                if count % 50 == 0:
                    print(f"   ... ingested {count} error codes")

        print(f"   ✅ Ingested {count} error codes")
        return count

    except Exception as e:
        print(f"   ❌ Failed: {e}")
        import traceback

        traceback.print_exc()
        return 0


async def create_ibmb_endpoints():
    """Create IBMB-specific endpoints."""
    print("\n🔌 Creating IBMB endpoints...")

    endpoints = [
        {
            "endpoint_id": "ibmb.transaction.initiate",
            "method": "POST",
            "path": "/ibmb/v1/transactions/initiate",
            "description": "Initiate a payment transaction via IBMB (Bharat BillPay)",
            "auth_type": "api_key",
            "request_schema": {
                "fields": [
                    {
                        "field_name": "merchant_id",
                        "json_path": "$.merchant_id",
                        "field_type": "string",
                        "required": True,
                        "description": "IBMB merchant identifier",
                    },
                    {
                        "field_name": "transaction_id",
                        "json_path": "$.transaction_id",
                        "field_type": "string",
                        "required": True,
                        "description": "Unique transaction reference",
                    },
                    {
                        "field_name": "amount",
                        "json_path": "$.amount",
                        "field_type": "number",
                        "required": True,
                        "description": "Transaction amount",
                    },
                    {
                        "field_name": "currency",
                        "json_path": "$.currency",
                        "field_type": "string",
                        "required": True,
                        "description": "Currency code (INR)",
                    },
                    {
                        "field_name": "customer_mobile",
                        "json_path": "$.customer_mobile",
                        "field_type": "string",
                        "required": True,
                        "description": "Customer mobile number",
                    },
                    {
                        "field_name": "callback_url",
                        "json_path": "$.callback_url",
                        "field_type": "string",
                        "required": True,
                        "description": "Webhook callback URL",
                    },
                ]
            },
            "response_schema": {
                "fields": [
                    {
                        "field_name": "transaction_id",
                        "json_path": "$.transaction_id",
                        "field_type": "string",
                        "required": True,
                    },
                    {
                        "field_name": "status",
                        "json_path": "$.status",
                        "field_type": "string",
                        "required": True,
                        "description": "INITIATED, PENDING, COMPLETED, FAILED",
                    },
                    {
                        "field_name": "ibmb_reference",
                        "json_path": "$.ibmb_reference",
                        "field_type": "string",
                        "required": True,
                    },
                ]
            },
            "error_responses": [
                {
                    "error_code": "IBMB001",
                    "http_status": 400,
                    "description": "Request json object is not in standard format",
                },
                {
                    "error_code": "IBMB002",
                    "http_status": 400,
                    "description": "Request is invalid",
                },
                {
                    "error_code": "IBMB003",
                    "http_status": 400,
                    "description": "Reference ID is not sent",
                },
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
                    {
                        "field_name": "transaction_id",
                        "json_path": "$.path.transaction_id",
                        "field_type": "string",
                        "required": True,
                    }
                ]
            },
            "response_schema": {
                "fields": [
                    {
                        "field_name": "status",
                        "json_path": "$.status",
                        "field_type": "string",
                        "required": True,
                    }
                ]
            },
            "error_responses": [
                {
                    "error_code": "IBMB004",
                    "http_status": 404,
                    "description": "Request is not found",
                }
            ],
            "spec_data": {},
            "is_ground_truth": False,
        },
    ]

    count = 0
    for ep in endpoints:
        try:
            existing = await database.get_endpoint_spec(ep["endpoint_id"])
            if existing:
                print(f"   ℹ️  {ep['endpoint_id']} already exists")
                continue

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
                source_doc_id=None,
            )
            count += 1
            print(f"   ✅ Added: {ep['endpoint_id']}")
        except Exception as e:
            print(f"   ❌ Failed {ep['endpoint_id']}: {e}")

    return count


async def create_ibmb_flows():
    """Create IBMB integration flows."""
    print("\n📋 Creating IBMB flows...")

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
                    "required_parameters": [
                        "merchant_id",
                        "transaction_id",
                        "amount",
                        "currency",
                        "customer_mobile",
                    ],
                    "expected_response": "status=INITIATED, ibmb_reference",
                    "error_handling": "Handle IBMB001 (invalid format), IBMB002 (invalid request)",
                    "next_steps": ["Poll for status"],
                },
                {
                    "step_number": 2,
                    "name": "Check Transaction Status",
                    "description": "Poll ibmb.transaction.status until completion",
                    "endpoint_id": "ibmb.transaction.status",
                    "required_parameters": ["transaction_id"],
                    "expected_response": "status=COMPLETED or FAILED",
                    "error_handling": "Handle IBMB004 (not found)",
                    "decision_point": "status == COMPLETED?",
                    "next_steps": ["Fulfill order", "Handle failure"],
                },
            ],
            "prerequisites": ["IBMB merchant account", "API credentials"],
            "estimated_duration_minutes": 10,
        }
    ]

    count = 0
    for flow in flows:
        try:
            existing = await database.get_flow(flow["flow_id"])
            if existing:
                print(f"   ℹ️  {flow['flow_id']} already exists")
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
                source_doc_id=None,
            )
            count += 1
            print(f"   ✅ Added: {flow['flow_id']}")
        except Exception as e:
            print(f"   ❌ Failed: {e}")

    return count


async def main():
    """Main ingestion."""
    print("=" * 60)
    print("IBMB SIMPLE INGESTION")
    print("=" * 60)

    await database.connect()

    # 1. Error codes
    error_count = await ingest_error_codes_csv()

    # 2. Endpoints
    ep_count = await create_ibmb_endpoints()

    # 3. Flows
    flow_count = await create_ibmb_flows()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Error codes: {error_count}")
    print(f"Endpoints: {ep_count}")
    print(f"Flows: {flow_count}")

    stats = await database.get_stats()
    print(f"\n📊 Total in database:")
    print(f"  • endpoint_specs: {stats.get('endpoint_specs', 0)}")
    print(f"  • error_codes: {stats.get('error_codes', 0)}")
    print(f"  • integration_flows: {stats.get('integration_flows', 0)}")

    await database.close()
    print("\n✅ Done!")


if __name__ == "__main__":
    asyncio.run(main())
