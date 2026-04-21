"""Debugging phase MCP tools."""

import hmac
import hashlib
import json
from typing import Dict, Optional

from ..utils.database import database
from ..utils.llm import llm_client


async def diagnose_webhook(headers: Dict, body: str, 
                           expected_signature: Optional[str] = None,
                           webhook_secret: Optional[str] = None) -> dict:
    """Diagnose webhook issues from request data.
    
    Args:
        headers: HTTP headers from webhook request
        body: Raw request body (NOT parsed JSON)
        expected_signature: Expected signature for comparison
        webhook_secret: Your webhook secret for verification
    
    Returns:
        Diagnosis with issues found and fix suggestions
    """
    issues = []
    checks_passed = []
    
    # Normalize headers to lowercase keys
    headers_lower = {k.lower(): v for k, v in headers.items()}
    
    # Check 1: Signature header presence
    sig_header = headers_lower.get('x-juspay-signature')
    if not sig_header:
        issues.append("❌ Missing `X-Juspay-Signature` header")
    else:
        checks_passed.append(f"✅ Found signature header: `{sig_header[:20]}...`")
    
    # Check 2: Content-Type
    content_type = headers_lower.get('content-type', '')
    if 'application/json' not in content_type:
        issues.append(f"⚠️ Content-Type is `{content_type}`, expected `application/json`")
    else:
        checks_passed.append("✅ Correct Content-Type: application/json")
    
    # Check 3: Body parsing
    try:
        payload = json.loads(body)
        checks_passed.append("✅ Body parses as valid JSON")
        
        # Check 4: Event type present
        event_type = payload.get('event')
        if event_type:
            checks_passed.append(f"✅ Event type present: `{event_type}`")
            
            # Check if event type is valid
            if database._pool is None:
                await database.connect()
            event = await database.get_webhook_event(event_type)
            if event:
                checks_passed.append(f"✅ Event type `{event_type}` is recognized")
            else:
                issues.append(f"⚠️ Event type `{event_type}` not found in known events")
        else:
            issues.append("❌ No `event` field in payload")
        
        # Check 5: Order ID present (for order events)
        if event_type and 'order' in event_type:
            order_id = payload.get('order_id')
            if order_id:
                checks_passed.append(f"✅ Order ID present: `{order_id}`")
            else:
                issues.append("⚠️ Order events should have `order_id` field")
    
    except json.JSONDecodeError as e:
        issues.append(f"❌ Body is not valid JSON: {e}")
        issues.append("   💡 Make sure you're using raw body, not parsed/form-encoded")
    
    # Check 6: Signature verification
    if webhook_secret and sig_header:
        # Compute expected signature
        expected = hmac.new(
            webhook_secret.encode('utf-8'),
            body.encode('utf-8') if isinstance(body, str) else body,
            hashlib.sha256
        ).hexdigest()
        
        # Constant-time comparison
        if hmac.compare_digest(sig_header, expected):
            checks_passed.append("✅ Signature verification PASSED")
        else:
            issues.append("❌ Signature verification FAILED")
            issues.append(f"   Received: `{sig_header[:30]}...`")
            issues.append(f"   Computed: `{expected[:30]}...`")
            issues.append("   💡 Common causes:")
            issues.append("      - Wrong webhook secret")
            issues.append("      - Using parsed JSON instead of raw body")
            issues.append("      - Encoding mismatch (must be UTF-8)")
    elif webhook_secret:
        issues.append("⚠️ Cannot verify: missing signature header")
    elif sig_header:
        issues.append("ℹ️ Signature present but no secret provided for verification")
    
    # Build response
    sections = [
        "# 🔍 Webhook Diagnosis Report",
        f"\n**Timestamp:** {__import__('datetime').datetime.now().isoformat()}"
    ]
    
    # Issues section
    if issues:
        sections.append(f"\n## ❌ Issues Found ({len(issues)})")
        for issue in issues:
            sections.append(issue)
    
    # Passed checks
    if checks_passed:
        sections.append(f"\n## ✅ Checks Passed ({len(checks_passed)})")
        for check in checks_passed:
            sections.append(check)
    
    # Fix suggestions
    sections.append("\n## 🔧 Recommended Fixes")
    
    if "Missing `X-Juspay-Signature`" in str(issues):
        sections.append("1. **Add signature header:** Check webhook settings in dashboard")
    
    if "not valid JSON" in str(issues):
        sections.append("2. **Use raw body:** Configure server to provide raw bytes, not parsed JSON")
        sections.append("   - Express: `app.use(express.raw({type: 'application/json'}))`")
        sections.append("   - Flask: `request.get_data()` not `request.json`")
        sections.append("   - Django: `request.body` not `request.POST`")
    
    if "Signature verification FAILED" in str(issues):
        sections.append("3. **Fix signature verification:**")
        sections.append("   ```python")
        sections.append("   import hmac, hashlib")
        sections.append("   ")
        sections.append("   signature = request.headers.get('X-Juspay-Signature')")
        sections.append("   payload = request.get_data()  # RAW body")
        sections.append("   expected = hmac.new(")
        sections.append("       WEBHOOK_SECRET.encode(),")
        sections.append("       payload,")
        sections.append("       hashlib.sha256")
        sections.append("   ")
        sections.append("   if not hmac.compare_digest(signature, expected):")
        sections.append("       raise Unauthorized()")
        sections.append("   ```")
    
    # Raw data dump
    sections.append("\n## 📄 Raw Request Data")
    sections.append("\n**Headers:**")
    sections.append(f"```json\n{json.dumps(headers, indent=2)}\n```")
    sections.append(f"\n**Body (first 500 chars):**")
    sections.append(f"```\n{body[:500]}{'...' if len(body) > 500 else ''}\n```")
    
    return {
        "content": [{
            "type": "text",
            "text": "\n".join(sections)
        }]
    }


async def lookup_error_map(error_code: str, bank: Optional[str] = None,
                           include_related: bool = True) -> dict:
    """Look up error code with full context map.
    
    Args:
        error_code: Error code to look up
        bank: Optional bank for bank-specific context
        include_related: Include related errors in response
    
    Returns:
        Comprehensive error context with affected flows
    """
    if database._pool is None:
        await database.connect()
    
    # Get error code details
    error = await database.get_error_code(error_code)
    
    if not error:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ Error code '{error_code}' not found.\n\nTry: search_docs(\"{error_code}\")"
            }],
            "isError": True
        }
    
    # Find endpoints that can return this error
    all_endpoints = await database.list_endpoints()
    affected_endpoints = []
    
    for ep in all_endpoints:
        spec = await database.get_endpoint_spec(ep['endpoint_id'])
        if spec and spec.get('error_responses'):
            for err in spec['error_responses']:
                if err.get('error_code') == error_code:
                    affected_endpoints.append({
                        'endpoint_id': ep['endpoint_id'],
                        'path': ep.get('path', 'N/A'),
                        'description': err.get('description', 'No description')
                    })
    
    # Get related errors
    related_errors = []
    if include_related and error.get('related_errors'):
        for related_code in error['related_errors']:
            related = await database.get_error_code(related_code)
            if related:
                related_errors.append({
                    'error_code': related_code,
                    'category': related.get('category', 'unknown'),
                    'message': related.get('message', 'No message')
                })
    
    # Build response
    sections = [
        f"# Error Map: {error_code}",
        f"\n**Message:** {error.get('message', 'N/A')}",
        f"**Category:** {error.get('category', 'unknown').upper()}",
        f"**HTTP Status:** {error.get('http_status', 'N/A')}",
        f"\n## Description\n{error.get('description', 'No description')}",
    ]
    
    # Affected endpoints
    if affected_endpoints:
        sections.append(f"\n## 🔌 Affected Endpoints ({len(affected_endpoints)})")
        for ep in affected_endpoints:
            sections.append(f"- **{ep['endpoint_id']}** `{ep['path']}`")
            sections.append(f"  {ep['description']}")
    
    # Common causes
    causes = error.get('common_causes', [])
    if causes:
        sections.append(f"\n## 🔍 Common Causes")
        for cause in causes:
            sections.append(f"- {cause}")
    
    # Fix suggestions
    fixes = error.get('fix_suggestions', [])
    if fixes:
        sections.append(f"\n## 🔧 Fix Suggestions")
        for i, fix in enumerate(fixes, 1):
            sections.append(f"{i}. {fix}")
    
    # Bank-specific notes
    bank_specific = error.get('bank_specific', {})
    if bank and bank in bank_specific:
        sections.append(f"\n## 🏦 Bank-Specific Notes ({bank.upper()})")
        sections.append(bank_specific[bank])
    elif bank_specific:
        sections.append(f"\n## 🏦 Bank-Specific Notes")
        for b, note in bank_specific.items():
            sections.append(f"- **{b.upper()}:** {note}")
    
    # Related errors
    if related_errors:
        sections.append(f"\n## 🔗 Related Errors")
        for rel in related_errors:
            sections.append(f"- **{rel['error_code']}** ({rel['category']}) - {rel['message']}")
    
    # Integration impact
    sections.append(f"\n---\n## 📊 Integration Impact")
    
    category = error.get('category', '')
    if category == 'retryable':
        sections.append("- **Impact:** Temporary - retry with backoff")
        sections.append("- **Customer Effect:** Slight delay")
        sections.append("- **Action Required:** Automatic retry")
    elif category == 'terminal':
        sections.append("- **Impact:** Final failure - customer must act")
        sections.append("- **Customer Effect:** Payment failed, needs alternative")
        sections.append("- **Action Required:** Present alternative payment options")
    elif category == 'merchant_action':
        sections.append("- **Impact:** Configuration/data issue")
        sections.append("- **Customer Effect:** Unable to complete payment")
        sections.append("- **Action Required:** Fix integration code")
    elif category == 'system_error':
        sections.append("- **Impact:** Juspay/platform issue")
        sections.append("- **Customer Effect:** Unpredictable")
        sections.append("- **Action Required:** Contact support if persists")
    
    return {
        "content": [{
            "type": "text",
            "text": "\n".join(sections)
        }]
    }


async def search_known_issues(description: str, category: Optional[str] = None,
                              limit: int = 5) -> dict:
    """Search known issues from support KB.
    
    Args:
        description: Natural language description of the issue
        category: Optional category filter
        limit: Maximum results to return
    
    Returns:
        Similar known issues with solutions
    """
    if database._pool is None:
        await database.connect()
    
    # Try semantic search first
    try:
        embeddings = await llm_client.embed([description])
        query_embedding = embeddings[0]
        
        results = await database.search_known_issues(
            query_embedding=query_embedding,
            limit=limit
        )
        
        if results:
            sections = [
                f"# Known Issues Search: \"{description[:60]}...\"",
                f"\n**Found:** {len(results)} similar issues\n"
            ]
            
            for i, result in enumerate(results, 1):
                sim_pct = result.get('similarity', 0) * 100
                sections.append(f"\n## Match {i} ({sim_pct:.0f}% similar)")
                sections.append(f"**Title:** {result.get('title', 'Untitled')}")
                
                if result.get('symptoms'):
                    sections.append(f"\n**Symptoms:** {result['symptoms']}")
                
                if result.get('root_cause'):
                    sections.append(f"**Root Cause:** {result['root_cause']}")
                
                if result.get('solution'):
                    sections.append(f"\n**✅ Solution:**\n{result['solution']}")
                
                if result.get('workaround'):
                    sections.append(f"\n**Workaround:** {result['workaround']}")
                
                sections.append("")
            
            return {
                "content": [{
                    "type": "text",
                    "text": "\n".join(sections)
                }]
            }
    
    except Exception as e:
        # Fall through to keyword search
        pass
    
    # Keyword fallback - search error codes
    errors = await database.search_error_codes(description, limit=limit)
    
    if errors:
        sections = [
            f"# Error Code Matches: \"{description[:60]}...\"",
            f"\n**Found:** {len(errors)} matching error codes\n"
        ]
        
        for err in errors:
            sections.append(f"- **{err['error_code']}** ({err['category']})")
            sections.append(f"  {err['message']}")
            sections.append("")
        
        sections.append("\n💡 **Get full details with:**")
        sections.append(f"`explain_error('{errors[0]['error_code']}')`")
        
        return {
            "content": [{
                "type": "text",
                "text": "\n".join(sections)
            }]
        }
    
    # No results - provide general guidance
    sections = [
        f"# No Direct Matches Found",
        f"\nFor: \"{description}\"",
        "\n## 🔍 Suggestions",
        "1. **Try different keywords** - Search with specific error codes or API names",
        "2. **Check error codes** - Use `explain_error()` with any error codes you're seeing",
        "3. **Review integration guide** - Use `get_integration_guide()` for your use case",
        "\n## 📚 Common Resources",
        "- Payment flow issues: `get_flow('payment.standard')`",
        "- Webhook problems: `diagnose_webhook()` with your headers/body",
        "- Payload validation: `validate_payload()` with your request",
        "\n## 🆘 Still stuck?",
        "Contact support with:",
        "- Exact error message or code",
        "- API endpoint being called",
        "- Request ID (if available)",
        "- Timestamp of issue"
    ]
    
    return {
        "content": [{
            "type": "text",
            "text": "\n".join(sections)
        }]
    }
