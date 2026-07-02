"""Testing phase tools."""

import json
from typing import Optional

from ..utils.db import db
from ..utils.llm import llm_client


# Mock test scenarios for demonstration
TEST_SCENARIOS = {
    "payment": [
        {
            "scenario_id": "payment_success_card",
            "name": "Successful Card Payment",
            "description": "Test a successful card payment with valid details",
            "input_data": {
                "amount": 10000,
                "currency": "INR",
                "card_number": "4111111111111111",
                "card_expiry": "12/25",
                "cvv": "123"
            },
            "expected_http_status": 200,
            "expected_response": {"status": "CHARGED"},
            "sandbox_notes": "Use test card 4111111111111111 for success flow"
        },
        {
            "scenario_id": "payment_failed_insufficient_funds",
            "name": "Failed Payment - Insufficient Funds",
            "description": "Test payment failure due to insufficient funds",
            "input_data": {
                "amount": 1000000,
                "currency": "INR",
                "card_number": "4000000000009995"
            },
            "expected_http_status": 200,
            "expected_response": {"status": "FAILED", "error_code": "INSUFFICIENT_FUNDS"},
            "sandbox_notes": "Use test card 4000000000009995 for insufficient funds error"
        }
    ],
    "refund": [
        {
            "scenario_id": "refund_full",
            "name": "Full Refund",
            "description": "Process a full refund for a completed payment",
            "input_data": {
                "original_order_id": "ord_123",
                "refund_amount": None  # Null means full refund
            },
            "expected_http_status": 200,
            "expected_response": {"status": "REFUND_INITIATED"},
            "sandbox_notes": "Requires existing order in CHARGED state"
        }
    ]
}


async def test_sandbox(endpoint_id: str, payload: dict, api_key: Optional[str] = None) -> dict:
    """Test API call in sandbox with response annotation."""
    # Validate payload first
    from .building import validate_payload
    validation = await validate_payload(endpoint_id, payload)
    
    if validation.get('isError'):
        return {
            "content": [{
                "type": "text",
                "text": f"## Validation Failed\n\nCannot proceed to sandbox test:\n{validation['content'][0]['text']}"
            }],
            "isError": True
        }
    
    # In a real implementation, this would make actual HTTP call to sandbox
    # For demo, we simulate a successful response with annotations
    
    spec = await db.get_endpoint_spec(endpoint_id)
    
    mock_response = {
        "order_id": payload.get('order_id', 'ord_test_123'),
        "status": "PENDING",
        "amount": payload.get('amount', 0),
        "currency": payload.get('currency', 'INR'),
        "created_at": "2024-01-01T00:00:00Z"
    }
    
    annotations = [
        f"**order_id**: Unique identifier for this order. Save this for future reference.",
        f"**status**: Current payment status. 'PENDING' means awaiting customer authentication.",
        f"**amount**: Amount in paise (10000 = ₹100.00)",
        f"**currency**: INR - Indian Rupee",
        f"**created_at**: UTC timestamp when order was created"
    ]
    
    next_steps = [
        "Redirect customer to payment_url from the response",
        "Handle webhook for status updates",
        "Poll status endpoint if webhooks unavailable"
    ]

    annotations_text = "\n".join(f"- {a}" for a in annotations)
    next_steps_text = "\n".join(f"{i+1}. {step}" for i, step in enumerate(next_steps))
    
    response_text = f"""## Sandbox Test Result: {endpoint_id}

### Request Payload
```json
{json.dumps(payload, indent=2)}
```

### Response (200 OK)
```json
{json.dumps(mock_response, indent=2)}
```

### Field Annotations
{annotations_text}

### Next Steps
{next_steps_text}

**Note**: This is a simulated response. In production, connect to actual sandbox API."""
    
    return {
        "content": [{
            "type": "text",
            "text": response_text
        }]
    }


async def explain_error(error_code: str, context: dict = None, bank: str = None) -> dict:
    """Explain an error code with root cause and fix suggestions."""
    # Try to get from database
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT error_data FROM error_codes WHERE error_code = $1",
            error_code
        )
    
    if row:
        error_data = json.loads(row['error_data'])
    else:
        # Use LLM to explain unknown error
        prompt = f"""Explain the error code '{error_code}' in the context of payment API integration.
Context: {json.dumps(context) if context else 'None'}
Bank: {bank if bank else 'Not specified'}

Provide:
1. What this error means
2. Common causes
3. How to fix it
4. Whether it's retryable"""
        
        explanation = await llm_client.chat([
            {"role": "user", "content": prompt}
        ])
        
        error_data = {
            "error_code": error_code,
            "description": explanation,
            "category": "unknown",
            "common_causes": ["See description above"],
            "fix_suggestions": ["Check API documentation", "Verify request parameters"]
        }
    
    # Build response
    bank_notes = ""
    if bank and error_data.get('bank_specific', {}).get(bank):
        bank_notes = f"\n\n**Bank-Specific Notes ({bank}):**\n{error_data['bank_specific'][bank]}"
    
    category_emoji = {
        "retryable": "🔄",
        "terminal": "❌",
        "merchant_action": "⚠️",
        "system_error": "🔧",
        "unknown": "❓"
    }.get(error_data.get('category', 'unknown'), "❓")

    common_causes_text = "\n".join(
        f"- {cause}" for cause in error_data.get('common_causes', ['Unknown'])
    )
    fix_suggestions_text = "\n".join(
        f"{i+1}. {suggestion}"
        for i, suggestion in enumerate(error_data.get('fix_suggestions', ['Contact support']))
    )
    
    result = f"""## Error Explanation: {error_code} {category_emoji}

**Category:** {error_data.get('category', 'unknown').upper()}

### Description
{error_data.get('description', 'No description available')}

### Common Causes
{common_causes_text}

### Fix Suggestions
{fix_suggestions_text}

### Retry Guidance
{error_data.get('retry_guidance', 'No specific retry guidance available')}
{bank_notes}"""
    
    return {
        "content": [{
            "type": "text",
            "text": result
        }]
    }


async def get_test_cases(flow_type: str, coverage: str = "essential") -> dict:
    """Get test scenarios for a flow type."""
    scenarios = TEST_SCENARIOS.get(flow_type, [])
    
    if coverage == "essential":
        scenarios = scenarios[:5]  # Limit to 5 for essential coverage
    
    if not scenarios:
        return {
            "content": [{
                "type": "text",
                "text": f"No test scenarios found for flow type: {flow_type}. Available: {', '.join(TEST_SCENARIOS.keys())}"
            }],
            "isError": True
        }
    
    scenario_texts = []
    for i, sc in enumerate(scenarios, 1):
        text = f"**{i}. {sc['name']}** ({sc['scenario_id']})\n"
        text += f"- Description: {sc['description']}\n"
        text += f"- Expected Status: {sc['expected_http_status']}\n"
        text += f"- Input: ```json\n{json.dumps(sc['input_data'], indent=2)}\n```\n"
        text += f"- Sandbox Note: {sc['sandbox_notes']}"
        scenario_texts.append(text)
    
    return {
        "content": [{
            "type": "text",
            "text": f"## Test Scenarios: {flow_type} ({coverage})\n\n" + "\n\n".join(scenario_texts)
        }]
    }


async def check_integration(checklist_type: str) -> dict:
    """Check integration readiness against checklist."""
    checklist_items = [
        ("Webhook URL configured", "Check if webhook endpoint is reachable"),
        ("Webhook signature verification", "Verify HMAC-SHA256 signature validation implemented"),
        ("Idempotency key handling", "Check if X-Idempotency-Key is sent for payment creation"),
        ("Error handling", "Verify all terminal error codes are handled"),
        ("Retry logic", "Check exponential backoff for retryable errors"),
        ("Sandbox testing", "At least one successful payment flow tested"),
    ]
    
    # In a real implementation, these would be checked against actual integration
    # For demo, we return the checklist template
    
    checklist_text = "\n".join([
        f"{'☐'} **{item[0]}** - {item[1]}"
        for item in checklist_items
    ])
    
    return {
        "content": [{
            "type": "text",
            "text": f"""## Pre-Production Checklist: {checklist_type}

Complete these checks before going live:

{checklist_text}

### How to verify:
1. Test each scenario in sandbox
2. Review error handling code
3. Check webhook endpoint logs
4. Validate retry logic with forced failures

**Note**: This is a manual checklist. Automate checks with test_sandbox tool for each endpoint."""
        }]
    }
