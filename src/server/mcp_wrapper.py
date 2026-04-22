"""
MCP Server wrapper that returns plain text for FastMCP compatibility.

Each tool wraps the original tool and extracts the text content.
"""

import asyncio
import json
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastmcp import FastMCP
from src.utils.database import database

mcp = FastMCP("merchant-integration-mcp")


def _extract_content(result: dict) -> str:
    """Extract text content from MCP-formatted result."""
    if isinstance(result, str):
        return result
    
    if isinstance(result, dict):
        # Check if it's already an MCP content structure
        if "content" in result and isinstance(result["content"], list):
            texts = []
            for item in result["content"]:
                if isinstance(item, dict) and "text" in item:
                    texts.append(item["text"])
            return "\n\n".join(texts) if texts else json.dumps(result)
        
        # Otherwise, return pretty-printed JSON
        return json.dumps(result, indent=2)
    
    return str(result)


# ==================== Understanding Tools ====================

@mcp.tool()
async def get_api_spec(endpoint_id: str, version: str = "v1") -> str:
    """Get complete API specification for an endpoint including request/response schemas, fields, examples, and error responses.
    
    Args:
        endpoint_id: Endpoint identifier (e.g., 'orders.create', 'order.status')
        version: API version
    """
    from src.tools.understanding_tools import get_api_spec as _func
    result = await _func(endpoint_id, version)
    return _extract_content(result)


@mcp.tool()
async def get_integration_guide(use_case: str, language: str = "python") -> str:
    """Get step-by-step integration guide for a use case with prerequisites and ordered steps.
    
    Args:
        use_case: Integration use case (payment, collect, mandate, refund, subscription)
        language: Preferred programming language (python, nodejs, java, go, php)
    """
    from src.tools.understanding_tools import get_integration_guide as _func
    result = await _func(use_case, language)
    return _extract_content(result)


@mcp.tool()
async def get_flow(flow_type: str, scenario: str = None) -> str:
    """Get ordered API call sequence for a flow type with decision points and error handling.
    
    Args:
        flow_type: Flow identifier (e.g., 'payment.standard', 'refund.standard')
        scenario: Specific scenario variant
    """
    from src.tools.understanding_tools import get_flow as _func
    result = await _func(flow_type, scenario)
    return _extract_content(result)


@mcp.tool()
async def search_docs(query: str, limit: int = 5, namespace: str = None) -> str:
    """Search documentation using semantic search across guides, FAQs, and error descriptions.
    
    Args:
        query: Natural language search query
        limit: Maximum results
        namespace: Search namespace (guides, faqs, error_descriptions, known_issues)
    """
    from src.tools.understanding_tools import search_docs as _func
    result = await _func(query, limit, namespace)
    return _extract_content(result)


# ==================== Building Tools ====================

@mcp.tool()
async def generate_payload(endpoint_id: str, params: dict = None, include_optional: bool = False) -> str:
    """Generate a valid JSON payload for an endpoint with example values and field documentation.
    
    Args:
        endpoint_id: Target endpoint identifier
        params: Override values for specific fields
        include_optional: Include optional fields
    """
    from src.tools.building_tools import generate_payload as _func
    result = await _func(endpoint_id, params or {}, include_optional)
    return _extract_content(result)


@mcp.tool()
async def get_code_example(endpoint_id: str, language: str) -> str:
    """Get working code example for an endpoint with error handling in multiple languages.
    
    Args:
        endpoint_id: Target endpoint identifier
        language: Programming language (python, nodejs, java, go, php)
    """
    from src.tools.building_tools import get_code_example as _func
    result = await _func(endpoint_id, language)
    return _extract_content(result)


@mcp.tool()
async def get_webhook_handler(event_type: str, language: str) -> str:
    """Get webhook handler code with HMAC-SHA256 signature verification.
    
    Args:
        event_type: Webhook event type (e.g., 'order.charged')
        language: Programming language (python, nodejs, go)
    """
    from src.tools.building_tools import get_webhook_handler as _func
    result = await _func(event_type, language)
    return _extract_content(result)


@mcp.tool()
async def validate_payload(endpoint_id: str, payload: dict) -> str:
    """Validate a payload against endpoint schema with detailed error reporting.
    
    Args:
        endpoint_id: Target endpoint identifier
        payload: JSON payload to validate
    """
    from src.tools.building_tools import validate_payload as _func
    result = await _func(endpoint_id, payload)
    return _extract_content(result)


# ==================== Testing Tools ====================

@mcp.tool()
async def test_sandbox(endpoint_id: str, payload: dict, api_key: str = None) -> str:
    """Test API call in sandbox with annotated response showing field meanings and next steps.
    
    Args:
        endpoint_id: Target endpoint identifier
        payload: Request payload
        api_key: Optional sandbox API key for real calls
    """
    from src.tools.testing_tools import test_sandbox as _func
    result = await _func(endpoint_id, payload, api_key)
    return _extract_content(result)


@mcp.tool()
async def explain_error(error_code: str, context: str = None) -> str:
    """Explain an error code with root cause, resolution steps, and related context.
    
    Args:
        error_code: Error code or error message
        context: Additional context about when error occurred
    """
    from src.tools.testing_tools import explain_error as _func
    result = await _func(error_code, context)
    return _extract_content(result)


@mcp.tool()
async def get_test_cases(endpoint_id: str, scenario: str = "all") -> str:
    """Get test cases for an endpoint with inputs, expected outputs, and validation rules.
    
    Args:
        endpoint_id: Target endpoint identifier
        scenario: Test scenario (success, failure, edge, all)
    """
    from src.tools.testing_tools import get_test_cases as _func
    result = await _func(endpoint_id, scenario)
    return _extract_content(result)


@mcp.tool()
async def check_integration(step: str = "all", environment: str = "sandbox") -> str:
    """Check integration setup with prerequisites, common mistakes, and quick fixes.
    
    Args:
        step: Current integration step
        environment: Environment being tested (sandbox, production)
    """
    from src.tools.testing_tools import check_integration as _func
    result = await _func(step, environment)
    return _extract_content(result)


# ==================== Debugging Tools ====================

@mcp.tool()
async def diagnose_webhook(event_type: str, symptom: str = None) -> str:
    """Diagnose webhook issues with delivery debugging, signature verification, and retry logic.
    
    Args:
        event_type: Webhook event type
        symptom: Symptom description
    """
    from src.tools.debugging_tools import diagnose_webhook as _func
    result = await _func(event_type, symptom)
    return _extract_content(result)


@mcp.tool()
async def lookup_error_map(error_code: str, source: str = None) -> str:
    """Look up error code in map with category, severity, HTTP mapping, and resolution.
    
    Args:
        error_code: Error code to look up
        source: Error source (gateway, network, validation)
    """
    from src.tools.debugging_tools import lookup_error_map as _func
    result = await _func(error_code, source)
    return _extract_content(result)


@mcp.tool()
async def search_known_issues(query: str, affected_versions: str = None) -> str:
    """Search known issues with workarounds and related internal tickets.
    
    Args:
        query: Issue description or keywords
        affected_versions: Version range affected
    """
    from src.tools.debugging_tools import search_known_issues as _func
    result = await _func(query, affected_versions)
    return _extract_content(result)


@mcp.tool()
async def health_check() -> str:
    """Check server health and database connection status."""
    try:
        stats = await database.get_stats()
        return json.dumps({"status": "healthy", "database": "connected", "stats": stats}, indent=2)
    except Exception as e:
        return json.dumps({"status": "unhealthy", "error": str(e)}, indent=2)


def main():
    """Run the MCP server."""
    loop = asyncio.get_event_loop()
    loop.run_until_complete(database.connect())
    print("✅ Database connected", file=sys.stderr)
    
    try:
        mcp.run(transport="stdio")
    finally:
        loop.run_until_complete(database.close())
        print("✅ Database disconnected", file=sys.stderr)


if __name__ == "__main__":
    main()
