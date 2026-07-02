"""Shared MCP tool registry used by hosted server entrypoints."""

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List


ToolCallable = Callable[..., Awaitable[Dict[str, Any]]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: ToolCallable

    def as_mcp_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


def _schema(properties: Dict[str, Any], required: List[str] | None = None) -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
    }


def _string(description: str, default: Any = None, enum: List[str] | None = None) -> Dict[str, Any]:
    value: Dict[str, Any] = {"type": "string", "description": description}
    if default is not None:
        value["default"] = default
    if enum:
        value["enum"] = enum
    return value


def _integer(description: str, default: int | None = None) -> Dict[str, Any]:
    value: Dict[str, Any] = {"type": "integer", "description": description}
    if default is not None:
        value["default"] = default
    return value


def _boolean(description: str, default: bool | None = None) -> Dict[str, Any]:
    value: Dict[str, Any] = {"type": "boolean", "description": description}
    if default is not None:
        value["default"] = default
    return value


def _object(description: str) -> Dict[str, Any]:
    return {"type": "object", "description": description}


async def _get_api_spec(endpoint_id: str, include_samples: bool = True):
    from ..tools.understanding_tools import get_api_spec

    return await get_api_spec(endpoint_id, None, include_samples)


async def _get_integration_guide(use_case: str, language: str = "python"):
    from ..tools.understanding_tools import get_integration_guide

    return await get_integration_guide(use_case, language)


async def _get_flow(flow_type: str, scenario: str | None = None):
    from ..tools.understanding_tools import get_flow

    return await get_flow(flow_type, scenario)


async def _search_docs(query: str, limit: int = 5, namespace: str | None = None):
    from ..tools.understanding_tools import search_docs

    return await search_docs(query, limit, namespace)


async def _search_documents(query: str, doc_id: str | None = None, top_k: int = 5):
    from ..tools.improved_search import search_with_qa_format

    return {"content": [{"type": "text", "text": await search_with_qa_format(query, doc_id, top_k)}]}


async def _generate_payload(
    endpoint_id: str,
    include_optional: bool = False,
    include_conditional: bool = False,
    output_format: str = "json",
):
    from ..tools.enhanced_building_tools import generate_enhanced_payload

    return await generate_enhanced_payload(endpoint_id, include_optional, include_conditional, output_format)


async def _get_code_example(
    endpoint_id: str,
    language: str,
    include_comments: bool = True,
    include_error_handling: bool = True,
    include_tests: bool = False,
):
    from ..tools.enhanced_code_generator import get_enhanced_code_example

    return await get_enhanced_code_example(
        endpoint_id,
        language,
        include_comments,
        include_error_handling,
        include_tests,
    )


async def _get_webhook_handler(
    event_type: str,
    language: str = "python",
    signature_algo: str = "hmac-sha256",
    include_docker: bool = False,
    include_tests: bool = False,
):
    from ..tools.enhanced_webhook_handler import get_enhanced_webhook_handler

    return await get_enhanced_webhook_handler(
        event_type,
        language,
        signature_algo,
        include_docker,
        include_tests,
    )


async def _validate_payload(endpoint_id: str, payload: Dict[str, Any], strict: bool = False):
    from ..tools.enhanced_validator import validate_enhanced_payload

    return await validate_enhanced_payload(endpoint_id, payload, strict)


async def _test_sandbox(endpoint_id: str, payload: Dict[str, Any], api_key: str | None = None, mode: str = "mock"):
    from ..tools.sandbox_client import test_in_sandbox

    return await test_in_sandbox(endpoint_id, payload, api_key, mode)


async def _explain_error(error_code: str):
    from ..tools.testing_tools import explain_error

    return await explain_error(error_code, None)


async def _get_test_cases(flow_type: str, coverage: str = "essential", format: str = "detailed"):
    from ..tools.enhanced_testing_tools import get_comprehensive_test_scenarios

    return await get_comprehensive_test_scenarios(flow_type, coverage, format)


async def _run_integration_check(
    merchant_id: str,
    api_key: str | None = None,
    webhook_url: str | None = None,
    base_url: str | None = None,
    checklist_type: str = "full",
):
    from ..tools.integration_checker import run_integration_check

    return await run_integration_check(merchant_id, api_key, webhook_url, base_url, checklist_type)


async def _diagnose_webhook(
    headers: Dict[str, Any],
    body: str,
    expected_signature: str | None = None,
    webhook_secret: str | None = None,
):
    from ..tools.debugging_tools import diagnose_webhook

    return await diagnose_webhook(headers, body, expected_signature, webhook_secret)


async def _lookup_error_map(error_code: str, bank: str | None = None, include_related: bool = True):
    from ..tools.debugging_tools import lookup_error_map

    return await lookup_error_map(error_code, bank, include_related)


async def _search_known_issues(description: str, category: str | None = None, limit: int = 5):
    from ..tools.debugging_tools import search_known_issues

    return await search_known_issues(description, category, limit)


async def _list_api_specs(limit: int = 20):
    from ..tools.api_specs_v2_tools import list_api_specs_v2

    return await list_api_specs_v2(limit)


async def _search_api_use_cases(query: str, limit: int = 10):
    from ..tools.api_use_case_tools import search_api_use_cases

    return await search_api_use_cases(query, limit)


async def _search_contextual_embeddings(query: str, doc_id: str | None = None, top_k: int = 5):
    from ..tools.contextual_embedding_generator import search_contextual_embeddings

    return await search_contextual_embeddings(query, doc_id, top_k)


async def _get_interactive_guide(
    use_case: str,
    role: str = "backend_developer",
    tech_stack: str = "python_fastapi",
    experience_level: str = "intermediate",
    step_number: int | None = None,
):
    from ..tools.enhanced_guides import get_interactive_guide

    return await get_interactive_guide(use_case, role, tech_stack, experience_level, step_number)


async def _generate_flow_diagram(flow_type: str, format: str = "mermaid", include_timings: bool = False):
    from ..tools.enhanced_guides import generate_flow_diagram

    return await generate_flow_diagram(flow_type, format, include_timings)


async def _explain_concept(concept: str, depth: str = "overview"):
    from ..tools.enhanced_guides import explain_concept

    return await explain_concept(concept, depth)


async def _answer_question(question: str, doc_id: str | None = None, limit: int = 6):
    from ..tools.admin_tools import answer_question

    return await answer_question(question, doc_id, limit)


TOOL_DEFINITIONS: List[ToolDefinition] = [
    ToolDefinition(
        "get_api_spec",
        "Get a complete endpoint specification from v2 API specs or legacy endpoint_specs.",
        _schema(
            {
                "endpoint_id": _string("Endpoint identifier"),
                "include_samples": _boolean("Include request/response samples", True),
            },
            ["endpoint_id"],
        ),
        _get_api_spec,
    ),
    ToolDefinition(
        "get_integration_guide",
        "Get a step-by-step integration guide for a payment use case.",
        _schema(
            {
                "use_case": _string("Use case", enum=["payment", "collect", "mandate", "refund", "subscription"]),
                "language": _string("Preferred language", "python"),
            },
            ["use_case"],
        ),
        _get_integration_guide,
    ),
    ToolDefinition(
        "get_flow",
        "Get an ordered API call flow with decision points.",
        _schema({"flow_type": _string("Flow identifier"), "scenario": _string("Optional scenario")}, ["flow_type"]),
        _get_flow,
    ),
    ToolDefinition(
        "search_docs",
        "Semantic/keyword search over endpoint docs, error codes, and document chunks.",
        _schema(
            {
                "query": _string("Search query"),
                "limit": _integer("Maximum results", 5),
                "namespace": _string("Optional namespace"),
            },
            ["query"],
        ),
        _search_docs,
    ),
    ToolDefinition(
        "search_documents",
        "Hybrid raw-chunk and contextual Q&A search over ingested documents.",
        _schema(
            {
                "query": _string("Search query"),
                "doc_id": _string("Optional document ID"),
                "top_k": _integer("Number of results", 5),
            },
            ["query"],
        ),
        _search_documents,
    ),
    ToolDefinition(
        "answer_question",
        "Answer a client question using only ingested MCP documentation context.",
        _schema(
            {
                "question": _string("Client question"),
                "doc_id": _string("Optional document ID filter"),
                "limit": _integer("Context results to use", 6),
            },
            ["question"],
        ),
        _answer_question,
    ),
    ToolDefinition(
        "generate_payload",
        "Generate an integration payload for an endpoint with smart defaults.",
        _schema(
            {
                "endpoint_id": _string("Endpoint identifier"),
                "include_optional": _boolean("Include optional fields", False),
                "include_conditional": _boolean("Include conditional fields", False),
                "output_format": _string("Output format", "json"),
            },
            ["endpoint_id"],
        ),
        _generate_payload,
    ),
    ToolDefinition(
        "get_code_example",
        "Generate production-ready SDK/API code for an endpoint.",
        _schema(
            {
                "endpoint_id": _string("Endpoint identifier"),
                "language": _string("Language", enum=["python", "nodejs", "java", "go", "php"]),
                "include_comments": _boolean("Include comments", True),
                "include_error_handling": _boolean("Include error handling", True),
                "include_tests": _boolean("Include tests", False),
            },
            ["endpoint_id", "language"],
        ),
        _get_code_example,
    ),
    ToolDefinition(
        "get_webhook_handler",
        "Generate a webhook handler with signature verification.",
        _schema(
            {
                "event_type": _string("Webhook event type"),
                "language": _string("Language", "python"),
                "signature_algo": _string("Signature algorithm", "hmac-sha256"),
                "include_docker": _boolean("Include Dockerfile", False),
                "include_tests": _boolean("Include tests", False),
            },
            ["event_type"],
        ),
        _get_webhook_handler,
    ),
    ToolDefinition(
        "validate_payload",
        "Validate a payload against endpoint schema and business rules.",
        _schema(
            {
                "endpoint_id": _string("Endpoint identifier"),
                "payload": _object("Payload to validate"),
                "strict": _boolean("Treat warnings as errors", False),
            },
            ["endpoint_id", "payload"],
        ),
        _validate_payload,
    ),
    ToolDefinition(
        "test_sandbox",
        "Run mock or sandbox API testing for an endpoint.",
        _schema(
            {
                "endpoint_id": _string("Endpoint identifier"),
                "payload": _object("Request payload"),
                "api_key": _string("Optional sandbox API key"),
                "mode": _string("mock or sandbox", "mock"),
            },
            ["endpoint_id", "payload"],
        ),
        _test_sandbox,
    ),
    ToolDefinition(
        "explain_error",
        "Explain an error code with causes and fixes.",
        _schema({"error_code": _string("Error code")}, ["error_code"]),
        _explain_error,
    ),
    ToolDefinition(
        "get_test_cases",
        "Get generated test scenarios for a flow.",
        _schema(
            {
                "flow_type": _string("Flow type"),
                "coverage": _string("Coverage level", "essential"),
                "format": _string("Output format", "detailed"),
            },
            ["flow_type"],
        ),
        _get_test_cases,
    ),
    ToolDefinition(
        "run_integration_check",
        "Run integration readiness checks for a merchant.",
        _schema(
            {
                "merchant_id": _string("Merchant identifier"),
                "api_key": _string("Optional API key"),
                "webhook_url": _string("Optional webhook URL"),
                "base_url": _string("Optional API base URL"),
                "checklist_type": _string("Checklist type", "full"),
            },
            ["merchant_id"],
        ),
        _run_integration_check,
    ),
    ToolDefinition(
        "diagnose_webhook",
        "Diagnose webhook headers, raw body, and optional signature.",
        _schema(
            {
                "headers": _object("Webhook HTTP headers"),
                "body": _string("Raw request body"),
                "expected_signature": _string("Optional expected signature"),
                "webhook_secret": _string("Optional webhook secret"),
            },
            ["headers", "body"],
        ),
        _diagnose_webhook,
    ),
    ToolDefinition(
        "lookup_error_map",
        "Look up full error-code context and affected endpoints.",
        _schema(
            {
                "error_code": _string("Error code"),
                "bank": _string("Optional bank code"),
                "include_related": _boolean("Include related errors", True),
            },
            ["error_code"],
        ),
        _lookup_error_map,
    ),
    ToolDefinition(
        "search_known_issues",
        "Search known issues and workarounds.",
        _schema(
            {
                "description": _string("Issue description"),
                "category": _string("Optional category"),
                "limit": _integer("Maximum results", 5),
            },
            ["description"],
        ),
        _search_known_issues,
    ),
    ToolDefinition(
        "list_api_specs",
        "List available latest API specs.",
        _schema({"limit": _integer("Maximum specs", 20)}),
        _list_api_specs,
    ),
    ToolDefinition(
        "search_api_use_cases",
        "Find the right API for a client business scenario using indexed business-use-case embeddings.",
        _schema(
            {
                "query": _string("Client business scenario or integration goal"),
                "limit": _integer("Maximum API matches", 10),
            },
            ["query"],
        ),
        _search_api_use_cases,
    ),
    ToolDefinition(
        "search_contextual_embeddings",
        "Search generated contextual embeddings.",
        _schema(
            {
                "query": _string("Search query"),
                "doc_id": _string("Optional document ID"),
                "top_k": _integer("Number of results", 5),
            },
            ["query"],
        ),
        _search_contextual_embeddings,
    ),
    ToolDefinition(
        "get_interactive_guide",
        "Get a personalized integration guide.",
        _schema(
            {
                "use_case": _string("Use case"),
                "role": _string("User role", "backend_developer"),
                "tech_stack": _string("Technology stack", "python_fastapi"),
                "experience_level": _string("Experience level", "intermediate"),
                "step_number": _integer("Optional step number"),
            },
            ["use_case"],
        ),
        _get_interactive_guide,
    ),
    ToolDefinition(
        "generate_flow_diagram",
        "Generate a Mermaid integration flow diagram.",
        _schema(
            {
                "flow_type": _string("Flow type"),
                "format": _string("Output format", "mermaid"),
                "include_timings": _boolean("Include timings", False),
            },
            ["flow_type"],
        ),
        _generate_flow_diagram,
    ),
    ToolDefinition(
        "explain_concept",
        "Explain a payment integration concept.",
        _schema(
            {
                "concept": _string("Concept name"),
                "depth": _string("Detail level", "overview"),
            },
            ["concept"],
        ),
        _explain_concept,
    ),
]


TOOL_REGISTRY: Dict[str, ToolCallable] = {tool.name: tool.handler for tool in TOOL_DEFINITIONS}
TOOL_SCHEMAS: Dict[str, Dict[str, Any]] = {tool.name: tool.as_mcp_schema() for tool in TOOL_DEFINITIONS}
