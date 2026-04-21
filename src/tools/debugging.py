"""Debugging phase tools."""

import hmac
import hashlib
import json
from typing import Optional

from ..utils.db import db
from ..utils.llm import llm_client


async def diagnose_webhook(headers: dict, body: str, expected_signature: str = None,
                           webhook_secret: str = None) -> dict:
    """Diagnose webhook issues from request data."""
    issues = []
    
    # Check signature header
    sig_header = headers.get('X-Juspay-Signature') or headers.get('x-juspay-signature')
    if not sig_header:
        issues.append("❌ Missing X-Juspay-Signature header")
    else:
        issues.append(f"✓ Found signature header: {sig_header[:20]}...")
    
    # Check content type
    content_type = headers.get('Content-Type', '')
    if 'application/json' not in content_type:
        issues.append(f"⚠️ Content-Type is '{content_type}', expected 'application/json'")
    
    # Verify signature if secret provided
    if webhook_secret and sig_header:
        expected = hmac.new(
            webhook_secret.encode(),
            body.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if sig_header == expected:
            issues.append("✓ Signature verification passed")
        else:
            issues.append("❌ Signature verification failed")
            issues.append(f"   Computed: {expected[:30]}...")
            issues.append(f"   Received: {sig_header[:30]}...")
    
    # Try to parse body
    try:
        payload = json.loads(body)
        issues.append("✓ Body parses as valid JSON")
        
        # Check for event type
        event_type = payload.get('event')
        if event_type:
            issues.append(f"✓ Event type: {event_type}")
        else:
            issues.append("⚠️ No 'event' field found in payload")
    except json.JSONDecodeError as e:
        issues.append(f"❌ Body is not valid JSON: {e}")
    
    # Generate fix suggestions
    fixes = []
    if "Missing X-Juspay-Signature" in str(issues):
        fixes.append("Add X-Juspay-Signature header from webhook settings")
    if "not valid JSON" in str(issues):
        fixes.append("Ensure raw body is used, not parsed/form-encoded")
    if "Signature verification failed" in str(issues):
        fixes.append("Verify webhook secret is correct")
        fixes.append("Ensure raw body bytes are used for signature computation")
    
    result_text = f"""## Webhook Diagnosis

### Issues Found
{"\n".join(issues)}

### Suggested Fixes
{"\n".join(f"{i+1}. {fix}" for i, fix in enumerate(fixes)) if fixes else "No specific fixes needed - webhook looks good!"}

### Raw Headers
```json
{json.dumps(headers, indent=2)}
```

### Raw Body (first 500 chars)
```
{body[:500]}...
```"""
    
    return {
        "content": [{
            "type": "text",
            "text": result_text
        }]
    }


async def lookup_error_map(error_code: str, bank: str = None, 
                           include_related: bool = True) -> dict:
    """Look up error code with full context."""
    # This is similar to explain_error but with more context
    result = await db.get_endpoint_spec(f"error:{error_code}")
    
    if not result:
        # Generate from LLM
        prompt = f"""Provide detailed information about error code '{error_code}' in payment processing.

Include:
1. Error meaning
2. Which endpoints return this error
3. Affected payment flows
4. Root causes
5. Solutions
6. Related error codes

Format as JSON with these keys: meaning, endpoints, flows, causes, solutions, related"""
        
        try:
            result_text = await llm_client.chat([
                {"role": "user", "content": prompt}
            ])
            
            # Try to parse as JSON or use as-is
            result = {"description": result_text}
        except Exception:
            result = {
                "description": f"Error code {error_code} documentation not found.",
                "suggestions": ["Check API documentation", "Contact support"]
            }
    
    bank_specific = ""
    if bank:
        bank_specific = f"\n\n**Bank-specific context ({bank}):**\nSome banks may have unique handling for this error."
    
    return {
        "content": [{
            "type": "text",
            "text": f"""## Error Map: {error_code}

{result.get('description', 'No description available')}
{bank_specific}

### Quick Reference
- **Retryable**: Check retry_guidance in explain_error tool
- **Endpoints**: Query related endpoints with get_api_spec
- **Flows**: See get_integration_guide for flow context

Use `explain_error` tool for specific fix suggestions."""
        }]
    }


async def search_known_issues(description: str, category: str = None, 
                               limit: int = 5) -> dict:
    """Search known issues from support KB."""
    # Generate embedding for query
    embeddings = await llm_client.embed([description])
    query_embedding = embeddings[0]
    
    # Search embeddings
    results = await db.search_embeddings(
        namespace="known_issues" if category != "pdf" else "pdf_IBMB Acquiring - Merchant Integration",
        query_embedding=query_embedding,
        limit=limit
    )
    
    if not results:
        # Fallback: use LLM to provide general guidance
        prompt = f"""Based on this issue description, provide troubleshooting steps:

"{description}"

Provide:
1. Possible causes
2. Diagnostic steps
3. Recommended solutions"""
        
        guidance = await llm_client.chat([
            {"role": "user", "content": prompt}
        ])
        
        return {
            "content": [{
                "type": "text",
                "text": f"""## No Exact Matches Found in KB

However, here's AI-generated guidance:

{guidance}

**Tip**: Rephrase your query or contact support with error details."""
            }]
        }
    
    # Format results
    result_texts = []
    for i, r in enumerate(results, 1):
        text = f"**Match {i}** (similarity: {r['similarity']:.3f})\n"
        text += f"{r['chunk_text'][:500]}..."
        result_texts.append(text)
    
    return {
        "content": [{
            "type": "text",
            "text": f"## Known Issues Matching: \"{description}\"\n\n" + "\n\n---\n\n".join(result_texts)
        }]
    }
