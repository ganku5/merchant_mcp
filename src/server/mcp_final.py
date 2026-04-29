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


# ===== Building Tools (Enhanced) =====

@mcp.tool()
def generate_payload(
    endpoint_id: str,
    include_optional: bool = False,
    include_conditional: bool = False,
    output_format: str = "json"
) -> str:
    """Generate intelligent payload for an endpoint with smart defaults.
    
    Args:
        endpoint_id: API endpoint identifier (e.g., 'ibmb.merchant.transaction.init')
        include_optional: Include optional fields in payload
        include_conditional: Include conditional fields
        output_format: Output format - 'json', 'python', 'nodejs', 'java'
    
    Returns:
        Generated payload with field explanations and smart defaults
    """
    from src.tools.enhanced_building_tools import generate_enhanced_payload as fn
    return _extract(_run_async(fn(endpoint_id, include_optional, include_conditional, output_format)))


@mcp.tool()
def get_code_example(
    endpoint_id: str,
    language: str,
    include_comments: bool = True,
    include_error_handling: bool = True,
    include_tests: bool = False
) -> str:
    """Generate production-ready SDK code with authentication and error handling.
    
    Args:
        endpoint_id: API endpoint identifier
        language: Programming language - 'python', 'nodejs', 'java', 'go', 'php'
        include_comments: Include inline documentation
        include_error_handling: Include error handling code
        include_tests: Include unit test template
    
    Returns:
        Complete SDK code with installation instructions
    """
    from src.tools.enhanced_code_generator import get_enhanced_code_example as fn
    return _extract(_run_async(fn(endpoint_id, language, include_comments, include_error_handling, include_tests)))


@mcp.tool()
def get_webhook_handler(
    event_type: str,
    language: str = "python",
    signature_algo: str = "hmac-sha256",
    include_docker: bool = False,
    include_tests: bool = False
) -> str:
    """Generate production-ready webhook handler with signature verification.
    
    Args:
        event_type: Webhook event type (e.g., 'order.charged', 'refund.processed')
        language: Programming language - 'python', 'nodejs'
        signature_algo: Signature algorithm - 'hmac-sha256', 'rsa-sha256'
        include_docker: Include Dockerfile
        include_tests: Include test suite
    
    Returns:
        Webhook handler with HMAC/RSA verification, replay protection, idempotency
    """
    from src.tools.enhanced_webhook_handler import get_enhanced_webhook_handler as fn
    return _extract(_run_async(fn(event_type, language, signature_algo, include_docker, include_tests)))


@mcp.tool()
def validate_payload(
    endpoint_id: str,
    payload: dict,
    strict: bool = False
) -> str:
    """Deep payload validation with business rules and actionable suggestions.
    
    Args:
        endpoint_id: API endpoint identifier
        payload: Payload to validate
        strict: If True, warnings become errors
    
    Returns:
        Validation report with errors, warnings, and improvement suggestions
    """
    from src.tools.enhanced_validator import validate_enhanced_payload as fn
    return _extract(_run_async(fn(endpoint_id, payload, strict)))


# ===== Testing Tools (Enhanced Phase 2) =====

@mcp.tool()
def test_sandbox(
    endpoint_id: str,
    payload: dict,
    api_key: str = None,
    mode: str = "mock"
) -> str:
    """Test API calls in sandbox with real or mock responses.
    
    Args:
        endpoint_id: API endpoint to test
        payload: Request payload
        api_key: Optional sandbox API key for real calls
        mode: Operation mode - 'mock' (fast simulated) or 'sandbox' (real API)
    
    Returns:
        Test result with annotations, latency metrics, and next steps
    """
    from src.tools.sandbox_client import test_in_sandbox
    return _extract(_run_async(test_in_sandbox(endpoint_id, payload, api_key, mode)))


@mcp.tool()
def explain_error(error_code: str) -> str:
    """Explain error code with root cause analysis and fix suggestions."""
    from src.tools.testing_tools import explain_error as fn
    return _extract(_run_async(fn(error_code, None)))


@mcp.tool()
def get_test_cases(
    flow_type: str,
    coverage: str = "essential",
    format: str = "detailed"
) -> str:
    """Get comprehensive test scenarios with generated test data.
    
    Args:
        flow_type: Flow type (payment, refund, status, collect)
        coverage: Coverage level - 'essential', 'comprehensive', 'edge_cases'
        format: Output format - 'detailed', 'summary', 'executable'
    
    Returns:
        Test scenarios with payloads, assertions, and execution metadata
    """
    from src.tools.enhanced_testing_tools import get_comprehensive_test_scenarios
    return _extract(_run_async(get_comprehensive_test_scenarios(flow_type, coverage, format)))


@mcp.tool()
def generate_test_suite(
    endpoint_id: str,
    coverage_level: str = "essential",
    include_postman: bool = False,
    include_jmeter: bool = False
) -> str:
    """Generate complete test suite with coverage matrix.
    
    Args:
        endpoint_id: API endpoint identifier
        coverage_level: 'essential' or 'comprehensive'
        include_postman: Export as Postman collection
        include_jmeter: Export as JMeter JMX file
    
    Returns:
        Test suite with categories, priorities, and optional exports
    """
    from src.tools.enhanced_testing_tools import generate_test_suite
    return _extract(_run_async(generate_test_suite(endpoint_id, coverage_level, include_postman, include_jmeter)))


@mcp.tool()
def run_transaction_lifecycle_test(
    endpoint_id: str,
    merchant_id: str,
    api_key: str = None,
    polling_interval: int = 5,
    max_polls: int = 12
) -> str:
    """Run complete transaction lifecycle with state tracking.
    
    Args:
        endpoint_id: Starting endpoint (usually transaction.init)
        merchant_id: Merchant ID for testing
        api_key: Optional sandbox API key
        polling_interval: Seconds between status polls
        max_polls: Maximum polling attempts
    
    Returns:
        Complete lifecycle trace with all state transitions and timing
    """
    from src.tools.enhanced_testing_tools import run_transaction_lifecycle_test
    return _extract(_run_async(run_transaction_lifecycle_test(
        endpoint_id, merchant_id, api_key, polling_interval, max_polls
    )))


@mcp.tool()
def export_test_suite(
    endpoint_id: str,
    format: str,
    coverage_level: str = "essential"
) -> str:
    """Export test suite in various formats.
    
    Args:
        endpoint_id: API endpoint to generate tests for
        format: Export format - 'postman', 'jmeter', 'curl', 'pytest'
        coverage_level: Test coverage level
    
    Returns:
        Exported test suite ready for use in external tools
    """
    from src.tools.enhanced_testing_tools import export_test_suite
    return _extract(_run_async(export_test_suite(endpoint_id, format, coverage_level)))


@mcp.tool()
def run_integration_check(
    merchant_id: str,
    api_key: str = None,
    webhook_url: str = None,
    base_url: str = None,
    checklist_type: str = "full"
) -> str:
    """Run automated integration checks and generate compliance report.
    
    Args:
        merchant_id: Your merchant identifier
        api_key: API key for authentication testing
        webhook_url: Your webhook endpoint URL
        base_url: API base URL (default: production)
        checklist_type: 'full', 'connectivity', or 'security'
    
    Returns:
        Complete integration report with pass/fail status and remediation steps
    """
    from src.tools.integration_checker import run_integration_check as fn
    return _extract(_run_async(fn(merchant_id, api_key, webhook_url, base_url, checklist_type)))


@mcp.tool()
def validate_integration_readiness(
    requirements: list,
    merchant_config: dict
) -> str:
    """Validate specific integration requirements are met.
    
    Args:
        requirements: List of requirements to validate
                      (e.g., ['webhook', 'retry_logic', 'idempotency'])
        merchant_config: Merchant configuration dictionary
    
    Returns:
        Requirement-by-requirement validation results
    """
    from src.tools.integration_checker import validate_integration_readiness
    return _extract(_run_async(validate_integration_readiness(requirements, merchant_config)))


# ===== Debugging Tools (Enhanced Phase 3) =====

@mcp.tool()
def diagnose_webhook(headers: dict, body: str) -> str:
    """Basic webhook diagnosis with signature verification."""
    from src.tools.debugging_tools import diagnose_webhook as fn
    return _extract(_run_async(fn(headers, body, None, None)))


@mcp.tool()
def run_deep_webhook_diagnostics(
    webhook_url: str,
    headers: dict,
    body: str,
    webhook_secret: str = None
) -> str:
    """Run comprehensive webhook diagnostics with network, security, and payload checks.
    
    Args:
        webhook_url: Your webhook endpoint URL
        headers: HTTP headers received from Juspay
        body: Raw request body (as string)
        webhook_secret: Your webhook secret for signature verification
    
    Returns:
        Complete diagnostic report with findings and prioritized recommendations
    """
    from src.tools.enhanced_debugging_tools import run_deep_webhook_diagnostics
    return _extract(_run_async(run_deep_webhook_diagnostics(webhook_url, headers, body, webhook_secret)))


@mcp.tool()
def analyze_issue_with_ai(
    symptoms: str,
    context: dict = None
) -> str:
    """AI-powered root cause analysis for payment integration issues.
    
    Args:
        symptoms: Description of the problem you're experiencing
        context: Additional context like endpoint, error_code, timestamp, merchant_id
    
    Returns:
        Root cause analysis with confidence scores and actionable solutions
    """
    from src.tools.enhanced_debugging_tools import analyze_issue_with_ai
    return _extract(_run_async(analyze_issue_with_ai(symptoms, context)))


@mcp.tool()
def analyze_webhook_logs(
    logs: list
) -> str:
    """Analyze webhook delivery logs for trends and issues.
    
    Args:
        logs: List of log entries with timestamp, status, event, latency_ms
    
    Returns:
        Analysis with success rates, trends, and detected issues
    """
    from src.tools.enhanced_debugging_tools import analyze_webhook_logs
    return _extract(_run_async(analyze_webhook_logs(logs)))


@mcp.tool()
def diagnose_api_error(
    error_message: str,
    endpoint_id: str = None,
    request_payload: dict = None,
    response_body: str = None
) -> str:
    """Diagnose API errors with pattern matching and context analysis.
    
    Args:
        error_message: The error message received
        endpoint_id: API endpoint that returned the error
        request_payload: Request payload sent (optional)
        response_body: Full response body (optional)
    
    Returns:
        Diagnosis with root cause and fix instructions
    """
    from src.tools.enhanced_debugging_tools import diagnose_api_error
    return _extract(_run_async(diagnose_api_error(error_message, endpoint_id, request_payload, response_body)))


@mcp.tool()
def find_similar_incidents(
    issue_description: str,
    merchant_id: str = None,
    time_range_days: int = 30
) -> str:
    """Find similar past incidents and their resolutions.
    
    Args:
        issue_description: Description of current issue
        merchant_id: Optional merchant ID to filter by
        time_range_days: How far back to search
    
    Returns:
        Similar incidents with resolutions and outcomes
    """
    from src.tools.enhanced_debugging_tools import find_similar_incidents
    return _extract(_run_async(find_similar_incidents(issue_description, merchant_id, time_range_days)))


@mcp.tool()
def lookup_error_map(error_code: str) -> str:
    """Lookup error code with full context and affected endpoints."""
    from src.tools.debugging_tools import lookup_error_map as fn
    return _extract(_run_async(fn(error_code, None)))


@mcp.tool()
def search_known_issues(query: str) -> str:
    """Search known issues with workarounds using semantic search."""
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


# ===== Guides & Documentation (Phase 4) =====

@mcp.tool()
def get_interactive_guide(
    use_case: str,
    role: str = "backend_developer",
    tech_stack: str = "python_fastapi",
    experience_level: str = "intermediate",
    step_number: int = None
) -> str:
    """Get personalized, step-by-step integration guide.
    
    Args:
        use_case: Integration use case (upi_payment, mandate_setup, refund_processing)
        role: Your role (backend_developer, frontend_developer, fullstack_developer, devops_engineer)
        tech_stack: Your technology stack (nodejs_express, python_fastapi, python_flask, python_django, java_spring, go, php)
        experience_level: Your experience level (beginner, intermediate, advanced)
        step_number: Specific step to view (None for full guide)
    
    Returns:
        Interactive guide with code examples, commands, and FAQs
    """
    from src.tools.enhanced_guides import get_interactive_guide
    return _extract(_run_async(get_interactive_guide(use_case, role, tech_stack, experience_level, step_number)))


@mcp.tool()
def generate_flow_diagram(
    flow_type: str,
    format: str = "mermaid",
    include_timings: bool = False
) -> str:
    """Generate visual API flow diagram.
    
    Args:
        flow_type: Type of flow (payment_standard, payment_collect, mandate_creation, refund_flow, state_machine)
        format: Output format - 'mermaid', 'svg', 'png', 'embed'
        include_timings: Include timing annotations on the diagram
    
    Returns:
        Mermaid diagram code and rendering links
    """
    from src.tools.enhanced_guides import generate_flow_diagram
    return _extract(_run_async(generate_flow_diagram(flow_type, format, include_timings)))


@mcp.tool()
def generate_error_decision_tree(
    flow_type: str = "payment"
) -> str:
    """Generate decision tree for error handling.
    
    Args:
        flow_type: Type of flow ('payment', 'webhook')
    
    Returns:
        Decision tree diagram and error handling guide
    """
    from src.tools.enhanced_guides import generate_error_decision_tree
    return _extract(_run_async(generate_error_decision_tree(flow_type)))


@mcp.tool()
def get_onboarding_wizard(
    merchant_id: str,
    completed_steps: list = None
) -> str:
    """Get personalized onboarding wizard with current step and progress.
    
    Args:
        merchant_id: Your merchant identifier
        completed_steps: List of steps already completed
                       (account_setup, environment_config, first_api_call, webhook_setup, testing, go_live)
    
    Returns:
        Current step details, progress, and recommended next actions
    """
    from src.tools.enhanced_guides import get_onboarding_wizard
    return _extract(_run_async(get_onboarding_wizard(merchant_id, completed_steps or [])))


@mcp.tool()
def get_step_by_step_walkthrough(
    endpoint_id: str,
    action: str = "overview"
) -> str:
    """Get step-by-step walkthrough for a specific API endpoint.
    
    Args:
        endpoint_id: API endpoint (e.g., 'ibmb.merchant.transaction.init')
        action: What you want to do - 'overview', 'generate_payload', 'handle_response', 'troubleshoot'
    
    Returns:
        Detailed walkthrough with examples for the specific action
    """
    from src.tools.enhanced_guides import get_step_by_step_walkthrough
    return _extract(_run_async(get_step_by_step_walkthrough(endpoint_id, action)))


@mcp.tool()
def explain_concept(
    concept: str,
    depth: str = "overview"
) -> str:
    """Explain payment integration concepts in detail.
    
    Args:
        concept: Concept to explain (idempotency, webhooks, upi_intent, signature_verification, etc.)
        depth: Detail level - 'overview', 'technical', 'implementation'
    
    Returns:
        Detailed explanation with examples
    """
    from src.tools.enhanced_guides import explain_concept
    return _extract(_run_async(explain_concept(concept, depth)))


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
