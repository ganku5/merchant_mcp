"""
MCP Server with STDIO transport for OpenCode.

This is the most reliable transport for OpenCode integration.
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastmcp import FastMCP
from src.utils.database import database

mcp = FastMCP("merchant-integration-mcp")


def _extract(result):
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        if "content" in result:
            texts = [item.get("text", "") for item in result["content"] if isinstance(item, dict)]
            return "\n\n".join(texts) if texts else json.dumps(result, indent=2)
        return json.dumps(result, indent=2)
    return str(result)


# ===== Understanding Tools =====

@mcp.tool()
async def get_api_spec(endpoint_id: str) -> str:
    """Get API specification for an endpoint."""
    from src.tools.understanding_tools import get_api_spec as fn
    return _extract(await fn(endpoint_id))


@mcp.tool()
async def get_integration_guide(use_case: str, language: str) -> str:
    """Get integration guide for a use case."""
    from src.tools.understanding_tools import get_integration_guide as fn
    return _extract(await fn(use_case, language))


@mcp.tool()
async def get_flow(flow_type: str) -> str:
    """Get API call flow sequence."""
    from src.tools.understanding_tools import get_flow as fn
    return _extract(await fn(flow_type, None))


@mcp.tool()
async def search_docs(query: str) -> str:
    """Search documentation."""
    from src.tools.understanding_tools import search_docs as fn
    return _extract(await fn(query, 5, None))


# ===== Building Tools =====

@mcp.tool()
async def generate_payload(endpoint_id: str) -> str:
    """Generate payload for an endpoint."""
    from src.tools.building_tools import generate_payload as fn
    return _extract(await fn(endpoint_id, {}, False))


@mcp.tool()
async def get_code_example(endpoint_id: str, language: str) -> str:
    """Get code example."""
    from src.tools.building_tools import get_code_example as fn
    return _extract(await fn(endpoint_id, language))


@mcp.tool()
async def get_webhook_handler(event_type: str, language: str) -> str:
    """Get webhook handler code."""
    from src.tools.building_tools import get_webhook_handler as fn
    return _extract(await fn(event_type, language))


@mcp.tool()
async def validate_payload(endpoint_id: str, payload: dict) -> str:
    """Validate payload."""
    from src.tools.building_tools import validate_payload as fn
    return _extract(await fn(endpoint_id, payload))


# ===== Testing Tools =====

@mcp.tool()
async def test_sandbox(endpoint_id: str, payload: dict) -> str:
    """Test in sandbox."""
    from src.tools.testing_tools import test_sandbox as fn
    return _extract(await fn(endpoint_id, payload, None))


@mcp.tool()
async def explain_error(error_code: str) -> str:
    """Explain error code."""
    from src.tools.testing_tools import explain_error as fn
    return _extract(await fn(error_code, None))


@mcp.tool()
async def get_test_cases(flow_type: str) -> str:
    """Get test cases."""
    from src.tools.testing_tools import get_test_cases as fn
    return _extract(await fn(flow_type, "essential"))


@mcp.tool()
async def check_integration() -> str:
    """Check integration."""
    from src.tools.testing_tools import check_integration as fn
    return _extract(await fn("pre_production"))


# ===== Debugging Tools =====

@mcp.tool()
async def diagnose_webhook(headers: dict, body: str) -> str:
    """Diagnose webhook."""
    from src.tools.debugging_tools import diagnose_webhook as fn
    return _extract(await fn(headers, body, None, None))


@mcp.tool()
async def lookup_error_map(error_code: str) -> str:
    """Lookup error code."""
    from src.tools.debugging_tools import lookup_error_map as fn
    return _extract(await fn(error_code, None))


@mcp.tool()
async def search_known_issues(query: str) -> str:
    """Search known issues."""
    from src.tools.debugging_tools import search_known_issues as fn
    return _extract(await fn(query, None))


@mcp.tool()
async def health_check() -> str:
    """Health check."""
    try:
        stats = await database.get_stats()
        return json.dumps({"status": "healthy", "stats": stats}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


def main():
    # Suppress stdout for MCP protocol (only stderr allowed)
    import sys
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(database.connect())
    
    # Log to stderr only
    sys.stderr.write("Database connected\n")
    sys.stderr.flush()
    
    try:
        # Run with minimal output
        import logging
        logging.getLogger().setLevel(logging.WARNING)
        mcp.run(transport="stdio")
    finally:
        loop.run_until_complete(database.close())
        sys.stderr.write("Database disconnected\n")
        sys.stderr.flush()


if __name__ == "__main__":
    main()
