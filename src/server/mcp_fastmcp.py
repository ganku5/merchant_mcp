"""
MCP Server using FastMCP for full protocol compliance.

Uses stdio transport for OpenCode compatibility.
"""

import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastmcp import FastMCP

from src.utils.database import database
from src.utils.llm import llm_client


# Initialize FastMCP
mcp = FastMCP("merchant-integration-mcp")


# ==================== Understanding Tools ====================

@mcp.tool()
async def get_api_spec(endpoint_id: str, version: str = "v1") -> str:
    """Get complete API specification for an endpoint including request/response schemas, fields, examples, and error responses."""
    from src.tools.understanding_tools import get_api_spec as _get_api_spec
    result = await _get_api_spec(endpoint_id, version)
    return json.dumps(result)


@mcp.tool()
async def get_integration_guide(use_case: str, language: str = "python") -> str:
    """Get step-by-step integration guide for a use case with prerequisites and ordered steps.
    
    Args:
        use_case: Integration use case (payment, collect, mandate, refund, subscription)
        language: Preferred programming language (python, nodejs, java, go, php)
    """
    from src.tools.understanding_tools import get_integration_guide as _get_guide
    result = await _get_guide(use_case, language)
    return json.dumps(result)


@mcp.tool()
async def get_flow(flow_type: str, scenario: str = None) -> str:
    """Get ordered API call sequence for a flow type with decision points and error handling.
    
    Args:
        flow_type: Flow identifier (e.g., 'payment.standard', 'refund.standard')
        scenario: Specific scenario variant
    """
    from src.tools.understanding_tools import get_flow as _get_flow
    result = await _get_flow(flow_type, scenario)
    return json.dumps(result)


@mcp.tool()
async def search_docs(query: str, limit: int = 5, namespace: str = None) -> str:
    """Search documentation using semantic search across guides, FAQs, and error descriptions."""
    from src.tools.understanding_tools import search_docs as _search
    result = await _search(query, limit, namespace)
    return json.dumps(result)


# ==================== Building Tools ====================

@mcp.tool()
async def generate_payload(endpoint_id: str, params: dict = None, include_optional: bool = False) -> str:
    """Generate a valid JSON payload for an endpoint with example values and field documentation."""
    from src.tools.building_tools import generate_payload as _gen_payload
    result = await _gen_payload(endpoint_id, params or {}, include_optional)
    return json.dumps(result)


@mcp.tool()
async def get_code_example(endpoint_id: str, language: str) -> str:
    """Get working code example for an endpoint with error handling in multiple languages."""
    from src.tools.building_tools import get_code_example as _get_code
    result = await _get_code(endpoint_id, language)
    return json.dumps(result)


@mcp.tool()
async def get_webhook_handler(event_type: str, language: str) -> str:
    """Get webhook handler code with HMAC-SHA256 signature verification."""
    from src.tools.building_tools import get_webhook_handler as _get_handler
    result = await _get_handler(event_type, language)
    return json.dumps(result)


@mcp.tool()
async def validate_payload(endpoint_id: str, payload: dict) -> str:
    """Validate a payload against endpoint schema with detailed error reporting."""
    from src.tools.building_tools import validate_payload as _validate
    result = await _validate(endpoint_id, payload)
    return json.dumps(result)


# ==================== Testing Tools ====================

@mcp.tool()
async def test_sandbox(endpoint_id: str, payload: dict, api_key: str = None) -> str:
    """Test API call in sandbox with annotated response showing field meanings and next steps."""
    from src.tools.testing_tools import test_sandbox as _test
    result = await _test(endpoint_id, payload, api_key)
    return json.dumps(result)


@mcp.tool()
async def explain_error(error_code: str, context: str = None) -> str:
    """Explain an error code with root cause, resolution steps, and related context."""
    from src.tools.testing_tools import explain_error as _explain
    result = await _explain(error_code, context)
    return json.dumps(result)


@mcp.tool()
async def get_test_cases(endpoint_id: str, scenario: str = "all") -> str:
    """Get test cases for an endpoint with inputs, expected outputs, and validation rules."""
    from src.tools.testing_tools import get_test_cases as _get_tests
    result = await _get_tests(endpoint_id, scenario)
    return json.dumps(result)


@mcp.tool()
async def check_integration(step: str = "all", environment: str = "sandbox") -> str:
    """Check integration setup with prerequisites, common mistakes, and quick fixes."""
    from src.tools.testing_tools import check_integration as _check
    result = await _check(step, environment)
    return json.dumps(result)


# ==================== Debugging Tools ====================

@mcp.tool()
async def diagnose_webhook(event_type: str, symptom: str = None) -> str:
    """Diagnose webhook issues with delivery debugging, signature verification, and retry logic."""
    from src.tools.debugging_tools import diagnose_webhook as _diagnose
    result = await _diagnose(event_type, symptom)
    return json.dumps(result)


@mcp.tool()
async def lookup_error_map(error_code: str, source: str = None) -> str:
    """Look up error code in map with category, severity, HTTP mapping, and resolution."""
    from src.tools.debugging_tools import lookup_error_map as _lookup
    result = await _lookup(error_code, source)
    return json.dumps(result)


@mcp.tool()
async def search_known_issues(query: str, affected_versions: str = None) -> str:
    """Search known issues with workarounds and related internal tickets."""
    from src.tools.debugging_tools import search_known_issues as _search_issues
    result = await _search_issues(query, affected_versions)
    return json.dumps(result)


@mcp.tool()
async def health_check() -> str:
    """Check server health and database connection status."""
    try:
        stats = await database.get_stats()
        return json.dumps({
            "status": "healthy",
            "database": "connected",
            "stats": stats
        })
    except Exception as e:
        return json.dumps({
            "status": "unhealthy",
            "error": str(e)
        })


def main():
    """Run the MCP server with stdio transport."""
    # Connect to database before starting
    loop = asyncio.get_event_loop()
    loop.run_until_complete(database.connect())
    print("✅ Database connected", file=sys.stderr)
    
    try:
        # Run with stdio transport
        mcp.run(transport="stdio")
    finally:
        loop.run_until_complete(database.close())
        print("✅ Database disconnected", file=sys.stderr)


if __name__ == "__main__":
    main()
