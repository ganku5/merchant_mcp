#!/usr/bin/env python3
"""Load ground truth fixtures into database."""

import asyncio
import json
import sys
sys.path.insert(0, '/home/ganesh/merchant_mcp')

import asyncpg
from src.utils.config import Config


GROUND_TRUTH_FIXTURES = [
    "/home/ganesh/merchant_mcp/tests/fixtures/ground_truth/orders_create_full.json",
    "/home/ganesh/merchant_mcp/tests/fixtures/ground_truth/order_status_full.json",
    "/home/ganesh/merchant_mcp/tests/fixtures/ground_truth/refund_create_full.json",
    "/home/ganesh/merchant_mcp/tests/fixtures/ground_truth/error_codes_full.json"
]


async def load_endpoints(conn: asyncpg.Connection, fixture_path: str):
    """Load endpoint fixture into database."""
    with open(fixture_path) as f:
        data = json.load(f)
    
    if isinstance(data, list):
        return  # Skip error codes here
    
    # Insert endpoint spec
    await conn.execute("""
        INSERT INTO endpoint_specs 
        (endpoint_id, method, path, description, auth_type, 
         request_schema, response_schema, error_responses,
         spec_data, rate_limit, idempotency, 
         related_webhooks, related_flows, code_examples,
         sandbox_notes, is_ground_truth, version)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
        ON CONFLICT (endpoint_id) DO UPDATE SET
            method = EXCLUDED.method,
            path = EXCLUDED.path,
            description = EXCLUDED.description,
            request_schema = EXCLUDED.request_schema,
            response_schema = EXCLUDED.response_schema,
            error_responses = EXCLUDED.error_responses,
            spec_data = EXCLUDED.spec_data,
            is_ground_truth = EXCLUDED.is_ground_truth
    """, 
        data['endpoint_id'],
        data['method'],
        data['path'],
        data['description'],
        data.get('auth_type', 'bearer'),
        json.dumps(data['request_schema']),
        json.dumps(data['response_schema']),
        json.dumps(data.get('error_responses', [])),
        json.dumps(data),
        json.dumps(data.get('rate_limit')),
        json.dumps(data.get('idempotency')),
        json.dumps(data.get('related_webhooks', [])),
        json.dumps(data.get('related_flows', [])),
        json.dumps(data.get('code_examples', {})),
        data.get('sandbox_notes'),
        True,  # is_ground_truth
        data.get('version', 'v1')
    )
    
    print(f"  ✓ Loaded endpoint: {data['endpoint_id']}")


async def load_error_codes(conn: asyncpg.Connection, fixture_path: str):
    """Load error codes fixture into database."""
    with open(fixture_path) as f:
        data = json.load(f)
    
    if not isinstance(data, list):
        return  # Skip endpoints here
    
    count = 0
    for error in data:
        await conn.execute("""
            INSERT INTO error_codes 
            (error_code, http_status, category, message, description,
             retry_guidance, common_causes, fix_suggestions,
             bank_specific, related_errors, error_data)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (error_code) DO UPDATE SET
                http_status = EXCLUDED.http_status,
                category = EXCLUDED.category,
                message = EXCLUDED.message,
                description = EXCLUDED.description,
                retry_guidance = EXCLUDED.retry_guidance,
                common_causes = EXCLUDED.common_causes,
                fix_suggestions = EXCLUDED.fix_suggestions,
                bank_specific = EXCLUDED.bank_specific,
                related_errors = EXCLUDED.related_errors,
                error_data = EXCLUDED.error_data
        """,
            error['error_code'],
            error['http_status'],
            error['category'],
            error['message'],
            error['description'],
            json.dumps(error.get('retry_guidance')),
            json.dumps(error.get('common_causes', [])),
            json.dumps(error.get('fix_suggestions', [])),
            json.dumps(error.get('bank_specific')),
            json.dumps(error.get('related_errors', [])),
            json.dumps(error)
        )
        count += 1
    
    print(f"  ✓ Loaded {count} error codes")


async def create_sample_flows(conn: asyncpg.Connection):
    """Create sample integration flows."""
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
                    "description": "Call orders.create to initialize payment",
                    "endpoint_id": "orders.create",
                    "required_parameters": ["order_id", "amount", "currency", "customer_email", "return_url"],
                    "expected_response": "order_id, id, status=CREATED, payment_links.web",
                    "error_handling": "Handle ORDER_ID_EXISTS with new order_id, validate_amount errors",
                    "decision_point": None,
                    "next_steps": ["Redirect to payment page"]
                },
                {
                    "step_number": 2,
                    "name": "Redirect Customer",
                    "description": "Send customer to payment_links.web URL",
                    "endpoint_id": None,
                    "required_parameters": [],
                    "expected_response": "Customer completes payment on Juspay page",
                    "error_handling": None,
                    "decision_point": "Wait for customer action or webhook",
                    "next_steps": ["Handle webhook", "Poll status"]
                },
                {
                    "step_number": 3,
                    "name": "Handle Webhook",
                    "description": "Receive and process order.charged webhook",
                    "endpoint_id": None,
                    "required_parameters": [],
                    "expected_response": "Webhook with event=order.charged",
                    "error_handling": "Verify signature, handle retries, idempotency check",
                    "decision_point": "Check event status",
                    "next_steps": ["Fulfill order if CHARGED"]
                },
                {
                    "step_number": 4,
                    "name": "Verify Status (fallback)",
                    "description": "Poll order.status if webhook not received",
                    "endpoint_id": "order.status",
                    "required_parameters": ["order_id"],
                    "expected_response": "Full order details with status",
                    "error_handling": "Retry up to 60 times with 5s interval",
                    "decision_point": "status == CHARGED?",
                    "next_steps": ["Fulfill order", "Show failure message"]
                }
            ],
            "prerequisites": ["API key", "Webhook endpoint configured", "Return URL set up"],
            "estimated_duration_minutes": 10
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
                    "description": "Verify order is CHARGED before refund",
                    "endpoint_id": "order.status",
                    "required_parameters": ["order_id"],
                    "expected_response": "status == CHARGED",
                    "error_handling": "Cannot refund if not charged",
                    "decision_point": None,
                    "next_steps": ["Initiate refund"]
                },
                {
                    "step_number": 2,
                    "name": "Create Refund",
                    "description": "Call refund.create with unique_request_id",
                    "endpoint_id": "refund.create",
                    "required_parameters": ["order_id", "unique_request_id"],
                    "expected_response": "refund_id, status=PENDING",
                    "error_handling": "Handle DUPLICATE_REQUEST_ID, INVALID_REFUND_AMOUNT",
                    "decision_point": None,
                    "next_steps": ["Wait for webhook"]
                },
                {
                    "step_number": 3,
                    "name": "Handle Refund Webhook",
                    "description": "Process refund.processed webhook",
                    "endpoint_id": None,
                    "required_parameters": [],
                    "expected_response": "event=refund.processed, status=SUCCESS",
                    "error_handling": "Verify signature, check for failure",
                    "decision_point": "status == SUCCESS?",
                    "next_steps": ["Update order in your system"]
                }
            ],
            "prerequisites": ["Order in CHARGED status", "Refund window not expired"],
            "estimated_duration_minutes": 5
        }
    ]
    
    for flow in flows:
        await conn.execute("""
            INSERT INTO integration_flows 
            (flow_id, name, use_case, description, steps, flow_data, 
             prerequisites, estimated_duration_minutes, version)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (flow_id) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                steps = EXCLUDED.steps,
                flow_data = EXCLUDED.flow_data
        """,
            flow['flow_id'],
            flow['name'],
            flow['use_case'],
            flow['description'],
            json.dumps(flow['steps']),
            json.dumps(flow),
            json.dumps(flow.get('prerequisites', [])),
            flow.get('estimated_duration_minutes'),
            'v1'
        )
    
    print(f"  ✓ Created {len(flows)} integration flows")


async def create_webhook_events(conn: asyncpg.Connection):
    """Create webhook event definitions."""
    events = [
        {
            "event_type": "order.created",
            "description": "Triggered when order is successfully created",
            "payload_schema": {
                "event": "order.created",
                "order_id": "string",
                "id": "string",
                "status": "CREATED",
                "amount": "integer",
                "currency": "string"
            },
            "signature_algorithm": "hmac_sha256",
            "idempotency_key_field": "order_id"
        },
        {
            "event_type": "order.charged",
            "description": "Triggered when payment is successfully charged",
            "payload_schema": {
                "event": "order.charged",
                "order_id": "string",
                "id": "string",
                "status": "CHARGED",
                "amount": "integer",
                "payment": {"id": "string", "status": "CAPTURED"}
            },
            "signature_algorithm": "hmac_sha256",
            "idempotency_key_field": "order_id"
        },
        {
            "event_type": "order.failed",
            "description": "Triggered when payment fails",
            "payload_schema": {
                "event": "order.failed",
                "order_id": "string",
                "id": "string",
                "status": "FAILED",
                "error_code": "string",
                "error_message": "string"
            },
            "signature_algorithm": "hmac_sha256",
            "idempotency_key_field": "order_id"
        },
        {
            "event_type": "refund.processed",
            "description": "Triggered when refund is processed",
            "payload_schema": {
                "event": "refund.processed",
                "refund_id": "string",
                "order_id": "string",
                "status": "SUCCESS",
                "amount": "integer"
            },
            "signature_algorithm": "hmac_sha256",
            "idempotency_key_field": "refund_id"
        }
    ]
    
    for event in events:
        await conn.execute("""
            INSERT INTO webhook_events 
            (event_type, description, payload_schema, signature_algorithm, idempotency_key_field)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (event_type) DO UPDATE SET
                description = EXCLUDED.description,
                payload_schema = EXCLUDED.payload_schema
        """,
            event['event_type'],
            event['description'],
            json.dumps(event['payload_schema']),
            event['signature_algorithm'],
            event['idempotency_key_field']
        )
    
    print(f"  ✓ Created {len(events)} webhook events")


async def create_test_scenarios(conn: asyncpg.Connection):
    """Create test scenarios."""
    scenarios = [
        {
            "scenario_id": "payment.success.card",
            "flow_type": "payment",
            "name": "Successful Card Payment",
            "description": "Test standard card payment flow with test card",
            "input_data": {
                "order_id": "test_order_card_001",
                "amount": 10000,
                "currency": "INR",
                "customer_email": "test@example.com",
                "return_url": "https://example.com/callback",
                "test_card": "4111111111111111"
            },
            "expected_http_status": 200,
            "expected_response_pattern": "status=CREATED, payment_links present",
            "sandbox_notes": "Use test card 4111111111111111, any future expiry, any CVV"
        },
        {
            "scenario_id": "payment.decline.insufficient",
            "flow_type": "payment",
            "name": "Declined - Insufficient Funds",
            "description": "Test card decline scenario",
            "input_data": {
                "order_id": "test_order_decline_001",
                "amount": 10000,
                "currency": "INR",
                "customer_email": "test@example.com",
                "return_url": "https://example.com/callback",
                "test_card": "4000000000009995"
            },
            "expected_http_status": 200,
            "expected_response_pattern": "order created, but payment will fail",
            "sandbox_notes": "Payment will show failed status after attempt"
        },
        {
            "scenario_id": "refund.full.success",
            "flow_type": "refund",
            "name": "Full Refund Success",
            "description": "Test full refund of charged order",
            "input_data": {
                "order_id": "existing_charged_order",
                "unique_request_id": "refund_test_001"
            },
            "expected_http_status": 200,
            "expected_response_pattern": "refund_id present, status=PENDING then SUCCESS",
            "sandbox_notes": "First create a charged order, then initiate refund"
        }
    ]
    
    for scenario in scenarios:
        await conn.execute("""
            INSERT INTO test_scenarios 
            (scenario_id, flow_type, name, description, input_data,
             expected_http_status, expected_response_pattern, sandbox_notes)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (scenario_id) DO UPDATE SET
                description = EXCLUDED.description,
                input_data = EXCLUDED.input_data
        """,
            scenario['scenario_id'],
            scenario['flow_type'],
            scenario['name'],
            scenario['description'],
            json.dumps(scenario['input_data']),
            scenario['expected_http_status'],
            scenario['expected_response_pattern'],
            scenario['sandbox_notes']
        )
    
    print(f"  ✓ Created {len(scenarios)} test scenarios")


async def main():
    """Main entry point."""
    print("Loading ground truth fixtures into database...")
    print(f"Database: {Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}")
    
    conn = await asyncpg.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        database=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD
    )
    
    try:
        print("\n=== Loading Endpoints ===")
        for fixture in GROUND_TRUTH_FIXTURES:
            if 'error' not in fixture.lower():
                await load_endpoints(conn, fixture)
        
        print("\n=== Loading Error Codes ===")
        for fixture in GROUND_TRUTH_FIXTURES:
            if 'error' in fixture.lower():
                await load_error_codes(conn, fixture)
        
        print("\n=== Creating Flows ===")
        await create_sample_flows(conn)
        
        print("\n=== Creating Webhook Events ===")
        await create_webhook_events(conn)
        
        print("\n=== Creating Test Scenarios ===")
        await create_test_scenarios(conn)
        
        print("\n=== Verification ===")
        endpoints = await conn.fetchval("SELECT COUNT(*) FROM endpoint_specs")
        errors = await conn.fetchval("SELECT COUNT(*) FROM error_codes")
        flows = await conn.fetchval("SELECT COUNT(*) FROM integration_flows")
        webhooks = await conn.fetchval("SELECT COUNT(*) FROM webhook_events")
        tests = await conn.fetchval("SELECT COUNT(*) FROM test_scenarios")
        
        print(f"  • Endpoints: {endpoints}")
        print(f"  • Error codes: {errors}")
        print(f"  • Integration flows: {flows}")
        print(f"  • Webhook events: {webhooks}")
        print(f"  • Test scenarios: {tests}")
        
        print("\n✅ Ground truth loaded successfully!")
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
