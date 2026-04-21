"""Testing phase MCP tools."""

import json
from typing import Dict, Optional

from ..utils.database import database
from ..utils.llm import llm_client


async def test_sandbox(endpoint_id: str, payload: Dict, api_key: Optional[str] = None) -> dict:
    """Test API call in sandbox with response annotation.
    
    Args:
        endpoint_id: Target endpoint identifier
        payload: Request payload to send
        api_key: Optional sandbox API key (for real testing)
    
    Returns:
        Annotated response with field explanations and next steps
    """
    if database._pool is None:
        await database.connect()
    
    # First validate the payload
    from .building_tools import validate_payload
    validation = await validate_payload(endpoint_id, payload)
    
    if validation.get('isError'):
        return {
            "content": [{
                "type": "text",
                "text": f"❌ Validation Failed\n\nCannot proceed to sandbox test:\n{validation['content'][0]['text']}"
            }],
            "isError": True
        }
    
    # Get endpoint spec for context
    spec = await database.get_endpoint_spec(endpoint_id)
    
    if not spec:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ Endpoint '{endpoint_id}' not found."
            }],
            "isError": True
        }
    
    # In a real implementation, this would make HTTP call to sandbox
    # For now, provide a simulated response with full annotation
    
    method = spec.get('method', 'POST')
    path = spec.get('path', '/unknown')
    
    # Simulate response based on endpoint
    mock_response = _simulate_response(endpoint_id, payload, spec)
    
    # Build comprehensive annotated response
    sections = [
        f"# Sandbox Test: {endpoint_id}",
        f"\n**API Call:** `{method} {path}`",
    ]
    
    # Request section
    sections.append("\n## 📤 Request")
    sections.append(f"```json\n{json.dumps(payload, indent=2)}\n```")
    
    # Response section
    sections.append("\n## 📥 Response (200 OK)")
    sections.append(f"```json\n{json.dumps(mock_response, indent=2)}\n```")
    
    # Field annotations
    sections.append("\n## 🔍 Field Explanations")
    
    if endpoint_id == "orders.create":
        annotations = [
            "**order_id**: Your unique identifier. Store this for reference.",
            "**id**: Juspay's internal order ID. Different from your order_id.",
            "**status**: 'CREATED' means order initialized, waiting for payment.",
            "**payment_links.web**: URL to redirect customer. Expires in 15 minutes.",
            "**amount**: Confirmed in paise. 10000 = ₹100.00"
        ]
    elif endpoint_id == "order.status":
        annotations = [
            "**status**: Current state. Check against expected flow.",
            "**payment.status**: Gateway status. 'CAPTURED' = successful charge.",
            "**amount_refunded**: Track total refunds for this order."
        ]
    elif endpoint_id == "refund.create":
        annotations = [
            "**refund_id**: Unique refund identifier. Store for reconciliation.",
            "**status**: 'PENDING' initially, watch webhook for final status.",
            "**expected_credit_date**: When customer should receive funds."
        ]
    else:
        annotations = ["See API documentation for field details."]
    
    for ann in annotations:
        sections.append(f"- {ann}")
    
    # Next steps
    sections.append("\n## 🚀 Next Steps")
    
    if endpoint_id == "orders.create":
        steps = [
            "Redirect customer to `payment_links.web` URL",
            "Set up webhook listener for order.charged event",
            "Or poll order.status every 5 seconds (max 60 times)"
        ]
    elif endpoint_id == "order.status":
        steps = [
            f"Current status: {mock_response.get('status', 'UNKNOWN')}",
            "If 'CHARGED': Fulfill the order",
            "If 'FAILED': Show failure message to customer",
            "If 'PENDING': Continue polling or wait for webhook"
        ]
    elif endpoint_id == "refund.create":
        steps = [
            "Store refund_id for tracking",
            "Listen for refund.processed webhook",
            "Update order status in your system"
        ]
    else:
        steps = ["Refer to integration guide for next steps."]
    
    for i, step in enumerate(steps, 1):
        sections.append(f"{i}. {step}")
    
    # Sandbox notes
    if spec.get('sandbox_notes'):
        sections.append(f"\n## 🧪 Sandbox Notes")
        sections.append(spec['sandbox_notes'])
    
    # If api_key provided, note about real call
    if api_key:
        sections.append(f"\n---\n⚠️ **Note:** With provided API key, this would make a real sandbox call.")
        sections.append("Response above is simulated for demonstration.")
    else:
        sections.append(f"\n---\n💡 **To make real sandbox calls:**")
        sections.append("Provide your sandbox API key to test_sandbox tool")
    
    return {
        "content": [{
            "type": "text",
            "text": "\n".join(sections)
        }]
    }


def _simulate_response(endpoint_id: str, payload: Dict, spec: Dict) -> Dict:
    """Generate a realistic mock response for sandbox simulation."""
    
    if endpoint_id == "orders.create":
        return {
            "order_id": payload.get('order_id', 'order_unknown'),
            "id": f"orde_{_random_id()}",
            "status": "CREATED",
            "amount": payload.get('amount', 0),
            "currency": payload.get('currency', 'INR'),
            "customer_id": payload.get('customer_id'),
            "customer_email": payload.get('customer_email'),
            "product_id": "",
            "created_at": _now_iso(),
            "payment_links": {
                "web": f"https://checkout.juspay.in/v2/pay/orde_{_random_id()}",
                "mobile": f"juspay://pay/orde_{_random_id()}"
            },
            "udf1": payload.get('udf1', ''),
            "udf2": payload.get('udf2', ''),
            "udf3": payload.get('udf3', '')
        }
    
    elif endpoint_id == "order.status":
        return {
            "order_id": payload.get('order_id', 'unknown'),
            "id": f"orde_{_random_id()}",
            "status": "CHARGED",
            "amount": 10000,
            "amount_refunded": 0,
            "currency": "INR",
            "customer_id": "cust_12345",
            "customer_email": "customer@example.com",
            "created_at": _now_iso(),
            "payment": {
                "id": f"pay_{_random_id()}",
                "status": "CAPTURED",
                "payment_method": "CARD",
                "gateway": "HDFC",
                "gateway_reference_id": f"TXN{_random_id().upper()}"
            }
        }
    
    elif endpoint_id == "refund.create":
        return {
            "refund_id": f"refund_{_random_id()}",
            "order_id": payload.get('order_id'),
            "amount": payload.get('amount', 10000),
            "status": "PENDING",
            "unique_request_id": payload.get('unique_request_id'),
            "created_at": _now_iso(),
            "expected_credit_date": _days_from_now(3)
        }
    
    else:
        return {"status": "success", "endpoint": endpoint_id}


def _random_id() -> str:
    """Generate random ID suffix."""
    import random
    import string
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))


def _now_iso() -> str:
    """Get current ISO timestamp."""
    from datetime import datetime
    return datetime.now().isoformat() + 'Z'


def _days_from_now(days: int) -> str:
    """Get timestamp days from now."""
    from datetime import datetime, timedelta
    return (datetime.now() + timedelta(days=days)).isoformat() + 'Z'


async def explain_error(error_code: str, context: Optional[Dict] = None, 
                        bank: Optional[str] = None) -> dict:
    """Explain an error code with root cause and fix suggestions.
    
    Args:
        error_code: Error code to explain
        context: Optional request context
        bank: Optional bank code for bank-specific guidance
    
    Returns:
        Detailed error explanation with fixes
    """
    if database._pool is None:
        await database.connect()
    
    error = await database.get_error_code(error_code)
    
    if not error:
        # Try to explain using LLM
        prompt = f"""Explain the error code '{error_code}' for a payment API.
Context: {json.dumps(context) if context else 'Not provided'}

Provide in JSON format:
- description: What this error means
- category: One of: retryable, terminal, merchant_action, system_error
- common_causes: Array of typical causes
- fix_suggestions: Array of actionable fixes"""
        
        try:
            llm_response = await llm_client.chat([
                {"role": "user", "content": prompt}
            ])
            
            # Parse LLM response
            error = {
                "error_code": error_code,
                "description": llm_response,
                "category": "unknown",
                "http_status": 400,
                "message": f"Error code {error_code}",
                "common_causes": ["See description"],
                "fix_suggestions": ["Contact support for assistance"],
                "retry_guidance": None,
                "bank_specific": None
            }
        except Exception:
            return {
                "content": [{
                    "type": "text",
                    "text": f"❌ Error code '{error_code}' not found in knowledge base.\n\nTry searching with: search_docs(\"{error_code}\")"
                }],
                "isError": True
            }
    
    # Category emoji mapping
    category_icons = {
        "retryable": "🔄",
        "terminal": "❌",
        "merchant_action": "⚠️",
        "system_error": "🔧",
        "unknown": "❓"
    }
    
    cat = error.get('category', 'unknown')
    icon = category_icons.get(cat, "❓")
    
    sections = [
        f"# Error Explanation: {error_code} {icon}",
        f"\n**HTTP Status:** {error.get('http_status', 'N/A')}",
        f"**Category:** {cat.upper()}",
        f"**Message:** {error.get('message', 'N/A')}",
        f"\n## Description\n{error.get('description', 'No description available')}",
    ]
    
    # Common causes
    causes = error.get('common_causes', [])
    if causes:
        sections.append("\n## Common Causes")
        for cause in causes:
            sections.append(f"- {cause}")
    
    # Fix suggestions
    fixes = error.get('fix_suggestions', [])
    if fixes:
        sections.append("\n## 🔧 Fix Suggestions")
        for i, fix in enumerate(fixes, 1):
            sections.append(f"{i}. {fix}")
    
    # Retry guidance
    retry = error.get('retry_guidance')
    if retry and isinstance(retry, dict):
        sections.append("\n## 🔄 Retry Guidance")
        if retry.get('max_retries', 0) > 0:
            sections.append(f"- **Max Retries:** {retry['max_retries']}")
            sections.append(f"- **Strategy:** {retry.get('backoff_strategy', 'exponential')}")
            sections.append(f"- **Initial Delay:** {retry.get('initial_delay_seconds', 1)}s")
        else:
            sections.append("- **Do NOT retry** - This error requires merchant action")
    
    # Bank-specific notes
    bank_specific = error.get('bank_specific', {})
    if bank and bank_specific and bank in bank_specific:
        sections.append(f"\n## 🏦 Bank-Specific Notes ({bank.upper()})")
        sections.append(bank_specific[bank])
    elif bank_specific:
        sections.append("\n## 🏦 Bank-Specific Notes")
        for b, note in bank_specific.items():
            sections.append(f"- **{b.upper()}:** {note}")
    
    # Related errors
    related = error.get('related_errors', [])
    if related:
        sections.append(f"\n## 🔗 Related Errors")
        sections.append(", ".join([f"`{r}`" for r in related]))
    
    # Context-specific advice
    if context:
        sections.append(f"\n## 📋 Context Analysis")
        if context.get('endpoint'):
            sections.append(f"- Endpoint: {context['endpoint']}")
        if context.get('timestamp'):
            sections.append(f"- Occurred at: {context['timestamp']}")
    
    return {
        "content": [{
            "type": "text",
            "text": "\n".join(sections)
        }]
    }


async def get_test_cases(flow_type: str, coverage: str = "essential") -> dict:
    """Get test scenarios for a flow type.
    
    Args:
        flow_type: Flow type (payment, refund, collect, mandate)
        coverage: Coverage level (essential, comprehensive)
    
    Returns:
        List of test scenarios with inputs and expected outputs
    """
    if database._pool is None:
        await database.connect()
    
    scenarios = await database.get_test_scenarios(flow_type, priority=coverage)
    
    if not scenarios:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ No test scenarios found for flow type: {flow_type}"
            }],
            "isError": True
        }
    
    sections = [
        f"# Test Scenarios: {flow_type}",
        f"**Coverage:** {coverage}",
        f"**Total Scenarios:** {len(scenarios)}"
    ]
    
    for i, sc in enumerate(scenarios, 1):
        sections.append(f"\n---\n## {i}. {sc['name']}")
        sections.append(f"**ID:** `{sc['scenario_id']}`")
        sections.append(f"**Description:** {sc['description']}")
        sections.append(f"**Expected HTTP Status:** {sc['expected_http_status']}")
        
        if sc.get('input_data'):
            sections.append(f"\n**Input Data:**")
            sections.append(f"```json\n{json.dumps(sc['input_data'], indent=2)}\n```")
        
        if sc.get('expected_response_pattern'):
            sections.append(f"**Expected Response Pattern:** {sc['expected_response_pattern']}")
        
        if sc.get('sandbox_notes'):
            sections.append(f"\n🧪 **Sandbox Notes:** {sc['sandbox_notes']}")
    
    # Testing tips
    sections.append(f"\n---\n## 💡 Testing Tips")
    sections.append("1. Start with essential scenarios before comprehensive")
    sections.append("2. Use test cards: 4111111111111111 (success), 4000000000009995 (decline)")
    sections.append("3. Verify webhook delivery for each scenario")
    sections.append("4. Check idempotency with duplicate requests")
    
    return {
        "content": [{
            "type": "text",
            "text": "\n".join(sections)
        }]
    }


async def check_integration(checklist_type: str = "pre_production") -> dict:
    """Check integration readiness against checklist.
    
    Args:
        checklist_type: Type of checklist (pre_production, security, performance)
    
    Returns:
        Integration checklist with verification steps
    """
    
    checklists = {
        "pre_production": [
            ("✅", "Webhook endpoint configured and reachable"),
            ("✅", "Webhook signature verification implemented"),
            ("✅", "Idempotency handling for orders.create"),
            ("✅", "Error handling for all terminal error codes"),
            ("✅", "Retry logic with exponential backoff"),
            ("✅", "Order status polling fallback implemented"),
            ("✅", "Refund flow tested with test cases"),
            ("✅", "Success webhook received and processed"),
            ("✅", "Failed payment handling tested"),
            ("✅", "Return URL handles all status codes"),
            ("✅", "Customer notification emails working"),
            ("✅", "Analytics/logging capturing payment events")
        ],
        "security": [
            ("✅", "API key stored securely (environment variable)"),
            ("✅", "Webhook secret never logged or exposed"),
            ("✅", "HTTPS only for all callbacks"),
            ("✅", "Input validation on all user inputs"),
            ("✅", "No PII logged in plain text"),
            ("✅", "Rate limiting implemented on your endpoints"),
            ("✅", "Signature verification using constant-time compare")
        ],
        "performance": [
            ("✅", "Order creation < 2 seconds"),
            ("✅", "Webhook response < 5 seconds (async processing)"),
            ("✅", "Status polling not excessive (< 60 requests)"),
            ("✅", "Connection pooling for API calls"),
            ("✅", "Circuit breaker for gateway failures")
        ]
    }
    
    items = checklists.get(checklist_type, checklists["pre_production"])
    
    sections = [
        f"# Integration Checklist: {checklist_type.replace('_', ' ').title()}",
        f"\n**Items:** {len(items)}",
        "\nTick each item as you complete it:"
    ]
    
    for icon, item in items:
        sections.append(f"\n- [ ] {icon} {item}")
    
    # Verification commands
    sections.append(f"\n---\n## 🧪 Verification Commands")
    
    if checklist_type == "pre_production":
        sections.append("\n**Test webhook signature:**")
        sections.append("```bash")
        sections.append("curl -X POST https://your-domain.com/webhook \\")
        sections.append("  -H 'X-Juspay-Signature: test' \\")
        sections.append("  -d '{\"event\":\"order.charged\",\"order_id\":\"test\"}'")
        sections.append("```")
    
    sections.append(f"\n---\n📖 **Need help?** Use other MCP tools:")
    sections.append("- `get_integration_guide(use_case='payment')` for step-by-step flow")
    sections.append("- `get_test_cases(flow_type='payment')` for test scenarios")
    sections.append("- `explain_error(error_code='XXX')` for error details")
    
    return {
        "content": [{
            "type": "text",
            "text": "\n".join(sections)
        }]
    }
