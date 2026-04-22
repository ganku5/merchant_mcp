"""
MCP Server with STDIO transport - sync version to avoid asyncio conflicts.
"""

import json
import os
import sys
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastmcp import FastMCP
from src.utils.database import database

# Create event loop in separate thread
_loop = asyncio.new_event_loop()
_executor = ThreadPoolExecutor(max_workers=1)

def _run_async(coro):
    """Run async coroutine in the event loop thread."""
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result()

def _init_db():
    """Initialize database connection."""
    _run_async(database.connect())

def _close_db():
    """Close database connection."""
    _run_async(database.close())

# Start event loop thread
def _start_loop():
    asyncio.set_event_loop(_loop)
    _loop.run_forever()

_thread = threading.Thread(target=_start_loop, daemon=True)
_thread.start()

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
def get_api_spec(endpoint_id: str) -> str:
    """Get API specification for an endpoint."""
    from src.tools.understanding_tools import get_api_spec as fn
    return _extract(_run_async(fn(endpoint_id)))


@mcp.tool()
def get_integration_guide(use_case: str, language: str) -> str:
    """Get integration guide for a use case."""
    from src.tools.understanding_tools import get_integration_guide as fn
    return _extract(_run_async(fn(use_case, language)))


@mcp.tool()
def get_flow(flow_type: str) -> str:
    """Get API call flow sequence."""
    from src.tools.understanding_tools import get_flow as fn
    return _extract(_run_async(fn(flow_type, None)))


@mcp.tool()
def search_docs(query: str) -> str:
    """Search documentation."""
    from src.tools.understanding_tools import search_docs as fn
    return _extract(_run_async(fn(query, 5, None)))


# ===== Building Tools =====

@mcp.tool()
def generate_payload(endpoint_id: str) -> str:
    """Generate payload for an endpoint."""
    from src.tools.building_tools import generate_payload as fn
    return _extract(_run_async(fn(endpoint_id, {}, False)))


@mcp.tool()
def get_code_example(endpoint_id: str, language: str) -> str:
    """Get code example."""
    from src.tools.building_tools import get_code_example as fn
    return _extract(_run_async(fn(endpoint_id, language)))


@mcp.tool()
def get_webhook_handler(event_type: str, language: str) -> str:
    """Get webhook handler code."""
    from src.tools.building_tools import get_webhook_handler as fn
    return _extract(_run_async(fn(event_type, language)))


@mcp.tool()
def validate_payload(endpoint_id: str, payload: dict) -> str:
    """Validate payload."""
    from src.tools.building_tools import validate_payload as fn
    return _extract(_run_async(fn(endpoint_id, payload)))


# ===== Testing Tools =====

@mcp.tool()
def test_sandbox(endpoint_id: str, payload: dict) -> str:
    """Test in sandbox."""
    from src.tools.testing_tools import test_sandbox as fn
    return _extract(_run_async(fn(endpoint_id, payload, None)))


@mcp.tool()
def explain_error(error_code: str) -> str:
    """Explain error code."""
    from src.tools.testing_tools import explain_error as fn
    return _extract(_run_async(fn(error_code, None)))


@mcp.tool()
def get_test_cases(flow_type: str) -> str:
    """Get test cases."""
    from src.tools.testing_tools import get_test_cases as fn
    return _extract(_run_async(fn(flow_type, "essential")))


@mcp.tool()
def check_integration() -> str:
    """Check integration."""
    from src.tools.testing_tools import check_integration as fn
    return _extract(_run_async(fn("pre_production")))


# ===== Debugging Tools =====

@mcp.tool()
def diagnose_webhook(headers: dict, body: str) -> str:
    """Diagnose webhook."""
    from src.tools.debugging_tools import diagnose_webhook as fn
    return _extract(_run_async(fn(headers, body, None, None)))


@mcp.tool()
def lookup_error_map(error_code: str) -> str:
    """Lookup error code."""
    from src.tools.debugging_tools import lookup_error_map as fn
    return _extract(_run_async(fn(error_code, None)))


@mcp.tool()
def search_known_issues(query: str) -> str:
    """Search known issues with workarounds and related internal tickets."""
    from src.tools.debugging_tools import search_known_issues as fn
    return _extract(_run_async(fn(query, None)))


# ===== API Specs V2 Tools =====

@mcp.tool()
def insert_api_spec_v2(spec: dict) -> str:
    """Insert complete API spec with headers, conditional fields, nested structures, and samples.
    
    Args:
        spec: Complete API specification including:
          - endpoint_id: Unique identifier
          - method: HTTP method (GET, POST, PUT, DELETE, PATCH)
          - path: API path
          - api_version: Version string (default: v1)
          - description: Human-readable description
          - headers: {request: [...], response: [...]}
          - request_fields: List of field definitions with nesting support
          - response_fields: List of response field definitions
          - conditions: Conditional logic definitions
          - samples: Complete request/response examples
          - rate_limit: Rate limiting configuration
          - idempotency: Idempotency settings
    """
    from src.tools.api_specs_v2_tools import insert_api_spec_v2 as fn
    return _extract(_run_async(fn(spec)))


@mcp.tool()
def get_api_spec_v2(endpoint_id: str, include_samples: bool = True) -> str:
    """Get complete API spec with headers, fields, conditions, and samples.
    
    Args:
        endpoint_id: The endpoint identifier
        include_samples: Whether to include request/response examples
    """
    from src.tools.api_specs_v2_tools import get_api_spec_v2 as fn
    return _extract(_run_async(fn(endpoint_id, include_samples)))


@mcp.tool()
def list_api_specs_v2(limit: int = 20) -> str:
    """List all available API specifications (latest versions only).
    
    Args:
        limit: Maximum number of specs to return (default: 20)
    """
    from src.tools.api_specs_v2_tools import list_api_specs_v2 as fn
    return _extract(_run_async(fn(limit)))


@mcp.tool()
def list_api_versions(endpoint_id: str) -> str:
    """List all available versions for a specific API endpoint.
    
    Args:
        endpoint_id: The API endpoint identifier (e.g., 'ibmb.merchant.transaction.init')
        
    Returns:
        List of all versions with stats (fields, headers, samples) and timestamps.
        Shows which version is the latest.
    """
    from src.tools.api_specs_v2_tools import list_api_versions as fn
    return _extract(_run_async(fn(endpoint_id)))


@mcp.tool()
def generate_contextual_embeddings(doc_id: str) -> str:
    """Generate contextual embeddings (Q&A pairs) for a document.
    
    Processes all text chunks of a document, generates question-answer pairs
    using LLM, and creates enhanced embeddings for better semantic search.
    
    Args:
        doc_id: The document ID to process (e.g., 'ibmb-api-auth-jwe')
    """
    from src.tools.contextual_embedding_generator import generate_contextual_embeddings as fn
    return _extract(_run_async(fn(doc_id)))


@mcp.tool()
def search_contextual_embeddings(query: str, doc_id: str = None, top_k: int = 5) -> str:
    """Search using contextual embeddings (Q&A-based semantic search).
    
    This search uses generated Q&A pairs to find more relevant matches
    compared to traditional keyword search.
    
    Args:
        query: The search query/question
        doc_id: Optional document ID to filter results
        top_k: Number of top results to return (default: 5)
    """
    from src.tools.contextual_embedding_generator import search_contextual_embeddings as fn
    return _extract(_run_async(fn(query, doc_id, top_k)))


@mcp.tool()
def health_check() -> str:
    """Health check."""
    try:
        stats = _run_async(database.get_stats())
        return json.dumps({"status": "healthy", "stats": stats}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


def main():
    _init_db()
    try:
        mcp.run(transport="stdio")
    finally:
        _close_db()
        _loop.call_soon_threadsafe(_loop.stop)


if __name__ == "__main__":
    main()
