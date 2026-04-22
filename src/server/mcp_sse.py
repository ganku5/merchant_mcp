"""
MCP Server with SSE transport using FastMCP.
"""

import asyncio
import json
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastmcp import FastMCP
from src.utils.database import database

# Create MCP server with SSE support
mcp = FastMCP("merchant-integration-mcp")


def _extract_content(result: dict) -> str:
    """Extract text content from MCP-formatted result."""
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        if "content" in result and isinstance(result["content"], list):
            texts = [item["text"] for item in result["content"] if isinstance(item, dict) and "text" in item]
            return "\n\n".join(texts) if texts else json.dumps(result, indent=2)
        return json.dumps(result, indent=2)
    return str(result)


# ==================== Understanding Tools ====================

@mcp.tool()
async def get_api_spec(endpoint_id: str, version: str = "v1") -> str:
    """Get complete API specification for an endpoint including request/response schemas, fields, examples, and error responses."""
    from src.tools.understanding_tools import get_api_spec as _func
    result = await _func(endpoint_id, version)
    return _extract_content(result)


@mcp.tool()
async def get_integration_guide(use_case: str, language: str = "python") -> str:
    """Get step-by-step integration guide for a use case with prerequisites and ordered steps."""
    from src.tools.understanding_tools import get_integration_guide as _func
    result = await _func(use_case, language)
    return _extract_content(result)


@mcp.tool()
async def get_flow(flow_type: str, scenario: str = None) -> str:
    """Get ordered API call sequence for a flow type with decision points and error handling."""
    from src.tools.understanding_tools import get_flow as _func
    result = await _func(flow_type, scenario)
    return _extract_content(result)


@mcp.tool()
async def search_docs(query: str, limit: int = 5, namespace: str = None) -> str:
    """Search documentation using semantic search across guides, FAQs, and error descriptions."""
    from src.tools.understanding_tools import search_docs as _func
    result = await _func(query, limit, namespace)
    return _extract_content(result)


# ==================== Building Tools ====================

@mcp.tool()
async def generate_payload(endpoint_id: str, params: dict = None, include_optional: bool = False) -> str:
    """Generate a valid JSON payload for an endpoint with example values and field documentation."""
    from src.tools.building_tools import generate_payload as _func
    result = await _func(endpoint_id, params or {}, include_optional)
    return _extract_content(result)


@mcp.tool()
async def get_code_example(endpoint_id: str, language: str) -> str:
    """Get working code example for an endpoint with error handling in multiple languages."""
    from src.tools.building_tools import get_code_example as _func
    result = await _func(endpoint_id, language)
    return _extract_content(result)


@mcp.tool()
async def get_webhook_handler(event_type: str, language: str) -> str:
    """Get webhook handler code with HMAC-SHA256 signature verification."""
    from src.tools.building_tools import get_webhook_handler as _func
    result = await _func(event_type, language)
    return _extract_content(result)


@mcp.tool()
async def validate_payload(endpoint_id: str, payload: dict) -> str:
    """Validate a payload against endpoint schema with detailed error reporting."""
    from src.tools.building_tools import validate_payload as _func
    result = await _func(endpoint_id, payload)
    return _extract_content(result)


# ==================== Testing Tools ====================

@mcp.tool()
async def test_sandbox(endpoint_id: str, payload: dict, api_key: str = None) -> str:
    """Test API call in sandbox with annotated response showing field meanings and next steps."""
    from src.tools.testing_tools import test_sandbox as _func
    result = await _func(endpoint_id, payload, api_key)
    return _extract_content(result)


@mcp.tool()
async def explain_error(error_code: str, context: str = None) -> str:
    """Explain an error code with root cause, resolution steps, and related context."""
    from src.tools.testing_tools import explain_error as _func
    result = await _func(error_code, context)
    return _extract_content(result)


@mcp.tool()
async def get_test_cases(flow_type: str, coverage: str = "essential") -> str:
    """Get test scenarios for a flow type with inputs and expected outputs."""
    from src.tools.testing_tools import get_test_cases as _func
    result = await _func(flow_type, coverage)
    return _extract_content(result)


@mcp.tool()
async def check_integration(checklist_type: str = "pre_production") -> str:
    """Check integration readiness against checklist."""
    from src.tools.testing_tools import check_integration as _func
    result = await _func(checklist_type)
    return _extract_content(result)


# ==================== Debugging Tools ====================

@mcp.tool()
async def diagnose_webhook(headers: dict, body: str = "", 
                          expected_signature: str = None, webhook_secret: str = None) -> str:
    """Diagnose webhook issues with delivery debugging, signature verification, and retry logic."""
    from src.tools.debugging_tools import diagnose_webhook as _func
    result = await _func(headers, body, expected_signature, webhook_secret)
    return _extract_content(result)


@mcp.tool()
async def lookup_error_map(error_code: str, source: str = None) -> str:
    """Look up error code in map with category, severity, HTTP mapping, and resolution."""
    from src.tools.debugging_tools import lookup_error_map as _func
    result = await _func(error_code, source)
    return _extract_content(result)


@mcp.tool()
async def search_known_issues(query: str, affected_versions: str = None) -> str:
    """Search known issues with workarounds and related internal tickets."""
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
    """Run the MCP server with SSE transport."""
    loop = asyncio.get_event_loop()
    loop.run_until_complete(database.connect())
    print("✅ Database connected", file=sys.stderr)
    
    try:
        # Run with SSE transport on port 8000
        mcp.run(transport="sse", port=8000, host="0.0.0.0")
    finally:
        loop.run_until_complete(database.close())
        print("✅ Database disconnected", file=sys.stderr)


if __name__ == "__main__":
    main()
