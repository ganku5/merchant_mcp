"""Production MCP Server implementation."""

import asyncio
import json
import time
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, List, Optional

from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from ..utils.database import database
from ..utils.llm import llm_client

# Import all tools
from ..tools.understanding_tools import (
    get_api_spec, get_integration_guide, get_flow, search_docs
)
from ..tools.building_tools import (
    generate_payload, get_code_example, get_webhook_handler, validate_payload
)
from ..tools.testing_tools import (
    test_sandbox, explain_error, get_test_cases, check_integration
)
from ..tools.debugging_tools import (
    diagnose_webhook, lookup_error_map, search_known_issues
)


# Tool registry - maps tool names to functions
TOOL_REGISTRY: Dict[str, Callable] = {
    # Understanding tools
    "get_api_spec": get_api_spec,
    "get_integration_guide": get_integration_guide,
    "get_flow": get_flow,
    "search_docs": search_docs,
    # Building tools
    "generate_payload": generate_payload,
    "get_code_example": get_code_example,
    "get_webhook_handler": get_webhook_handler,
    "validate_payload": validate_payload,
    # Testing tools
    "test_sandbox": test_sandbox,
    "explain_error": explain_error,
    "get_test_cases": get_test_cases,
    "check_integration": check_integration,
    # Debugging tools
    "diagnose_webhook": diagnose_webhook,
    "lookup_error_map": lookup_error_map,
    "search_known_issues": search_known_issues,
}

# Tool schemas for MCP protocol
TOOL_SCHEMAS = {
    "get_api_spec": {
        "name": "get_api_spec",
        "description": "Get complete API specification for an endpoint including request/response schemas, fields, examples, and error responses",
        "inputSchema": {
            "type": "object",
            "properties": {
                "endpoint_id": {"type": "string", "description": "Endpoint identifier (e.g., 'orders.create', 'order.status')"},
                "version": {"type": "string", "description": "API version", "default": "v1"}
            },
            "required": ["endpoint_id"]
        }
    },
    "get_integration_guide": {
        "name": "get_integration_guide",
        "description": "Get step-by-step integration guide for a use case with prerequisites and ordered steps",
        "inputSchema": {
            "type": "object",
            "properties": {
                "use_case": {"type": "string", "enum": ["payment", "collect", "mandate", "refund", "subscription"], "description": "Integration use case"},
                "language": {"type": "string", "enum": ["python", "nodejs", "java", "go", "php"], "description": "Preferred programming language", "default": "python"}
            },
            "required": ["use_case"]
        }
    },
    "get_flow": {
        "name": "get_flow",
        "description": "Get ordered API call sequence for a flow type with decision points and error handling",
        "inputSchema": {
            "type": "object",
            "properties": {
                "flow_type": {"type": "string", "description": "Flow identifier (e.g., 'payment.standard', 'refund.standard')"},
                "scenario": {"type": "string", "description": "Specific scenario variant", "default": None}
            },
            "required": ["flow_type"]
        }
    },
    "search_docs": {
        "name": "search_docs",
        "description": "Search documentation using semantic search across guides, FAQs, and error descriptions",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language search query"},
                "limit": {"type": "integer", "description": "Maximum results", "default": 5},
                "namespace": {"type": "string", "description": "Search namespace (guides, faqs, error_descriptions, known_issues)", "default": None}
            },
            "required": ["query"]
        }
    },
    "generate_payload": {
        "name": "generate_payload",
        "description": "Generate a valid JSON payload for an endpoint with example values and field documentation",
        "inputSchema": {
            "type": "object",
            "properties": {
                "endpoint_id": {"type": "string", "description": "Target endpoint identifier"},
                "params": {"type": "object", "description": "Override values for specific fields", "default": {}},
                "include_optional": {"type": "boolean", "description": "Include optional fields", "default": False}
            },
            "required": ["endpoint_id"]
        }
    },
    "get_code_example": {
        "name": "get_code_example",
        "description": "Get working code example for an endpoint with error handling in multiple languages",
        "inputSchema": {
            "type": "object",
            "properties": {
                "endpoint_id": {"type": "string", "description": "Target endpoint identifier"},
                "language": {"type": "string", "enum": ["python", "nodejs", "java", "go", "php"], "description": "Programming language"}
            },
            "required": ["endpoint_id", "language"]
        }
    },
    "get_webhook_handler": {
        "name": "get_webhook_handler",
        "description": "Get webhook handler code with HMAC-SHA256 signature verification",
        "inputSchema": {
            "type": "object",
            "properties": {
                "event_type": {"type": "string", "description": "Webhook event type (e.g., 'order.charged')"},
                "language": {"type": "string", "enum": ["python", "nodejs", "go"], "description": "Programming language"}
            },
            "required": ["event_type", "language"]
        }
    },
    "validate_payload": {
        "name": "validate_payload",
        "description": "Validate a payload against endpoint schema with detailed error reporting",
        "inputSchema": {
            "type": "object",
            "properties": {
                "endpoint_id": {"type": "string", "description": "Target endpoint identifier"},
                "payload": {"type": "object", "description": "JSON payload to validate"}
            },
            "required": ["endpoint_id", "payload"]
        }
    },
    "test_sandbox": {
        "name": "test_sandbox",
        "description": "Test API call in sandbox with annotated response showing field meanings and next steps",
        "inputSchema": {
            "type": "object",
            "properties": {
                "endpoint_id": {"type": "string", "description": "Target endpoint identifier"},
                "payload": {"type": "object", "description": "Request payload"},
                "api_key": {"type": "string", "description": "Optional sandbox API key for real calls", "default": None}
            },
            "required": ["endpoint_id", "payload"]
        }
    },
    "explain_error": {
        "name": "explain_error",
        "description": "Explain an error code with root cause, fix suggestions, and retry guidance",
        "inputSchema": {
            "type": "object",
            "properties": {
                "error_code": {"type": "string", "description": "Error code to explain"},
                "context": {"type": "object", "description": "Optional request context", "default": None},
                "bank": {"type": "string", "description": "Optional bank code for bank-specific guidance", "default": None}
            },
            "required": ["error_code"]
        }
    },
    "get_test_cases": {
        "name": "get_test_cases",
        "description": "Get test scenarios for a flow type with inputs and expected outputs",
        "inputSchema": {
            "type": "object",
            "properties": {
                "flow_type": {"type": "string", "description": "Flow type (payment, refund, collect, mandate)"},
                "coverage": {"type": "string", "enum": ["essential", "comprehensive"], "description": "Coverage level", "default": "essential"}
            },
            "required": ["flow_type"]
        }
    },
    "check_integration": {
        "name": "check_integration",
        "description": "Check integration readiness against pre-production checklist",
        "inputSchema": {
            "type": "object",
            "properties": {
                "checklist_type": {"type": "string", "enum": ["pre_production", "security", "performance"], "description": "Type of checklist", "default": "pre_production"}
            },
            "required": []
        }
    },
    "diagnose_webhook": {
        "name": "diagnose_webhook",
        "description": "Diagnose webhook issues from request headers and body with signature verification",
        "inputSchema": {
            "type": "object",
            "properties": {
                "headers": {"type": "object", "description": "HTTP headers from webhook request"},
                "body": {"type": "string", "description": "Raw request body (NOT parsed JSON)"},
                "expected_signature": {"type": "string", "description": "Expected signature for comparison", "default": None},
                "webhook_secret": {"type": "string", "description": "Your webhook secret for verification", "default": None}
            },
            "required": ["headers", "body"]
        }
    },
    "lookup_error_map": {
        "name": "lookup_error_map",
        "description": "Look up error code with full context including affected endpoints and related errors",
        "inputSchema": {
            "type": "object",
            "properties": {
                "error_code": {"type": "string", "description": "Error code to look up"},
                "bank": {"type": "string", "description": "Optional bank code", "default": None},
                "include_related": {"type": "boolean", "description": "Include related errors", "default": True}
            },
            "required": ["error_code"]
        }
    },
    "search_known_issues": {
        "name": "search_known_issues",
        "description": "Search known issues from support KB using semantic search",
        "inputSchema": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "Natural language description of the issue"},
                "category": {"type": "string", "description": "Optional category filter", "default": None},
                "limit": {"type": "integer", "description": "Maximum results", "default": 5}
            },
            "required": ["description"]
        }
    }
}


class MCPToolRequest(BaseModel):
    """MCP tool request."""
    name: str
    arguments: Dict[str, Any]


class MCPServer:
    """Production MCP Server with all tools."""
    
    def __init__(self):
        self.app = FastAPI(
            title="Merchant Integration MCP",
            description="MCP server for Juspay payment integration support",
            version="1.0.0"
        )
        self._setup_routes()
        self._setup_middleware()
    
    def _setup_middleware(self):
        """Setup request middleware."""
        
        @self.app.middleware("http")
        async def log_requests(request: Request, call_next):
            start_time = time.time()
            response = await call_next(request)
            duration = (time.time() - start_time) * 1000
            
            # Log to database if not health check
            if request.url.path not in ['/health', '/sse'] and database._pool:
                try:
                    await database.log_request(
                        tool_name=request.url.path,
                        request_params={"method": request.method},
                        response_status=str(response.status_code),
                        latency_ms=int(duration)
                    )
                except:
                    pass
            
            return response
    
    def _setup_routes(self):
        """Setup FastAPI routes."""
        
        @self.app.on_event("startup")
        async def startup():
            """Initialize on startup."""
            await database.connect()
            print("✅ Database connected")
        
        @self.app.on_event("shutdown")
        async def shutdown():
            """Cleanup on shutdown."""
            await database.close()
            print("✅ Database disconnected")
        
        @self.app.get("/health")
        async def health():
            """Health check endpoint."""
            try:
                stats = await database.get_stats()
                return {
                    "status": "healthy",
                    "database": "connected",
                    "stats": stats
                }
            except Exception as e:
                return JSONResponse(
                    status_code=503,
                    content={"status": "unhealthy", "error": str(e)}
                )
        
        @self.app.get("/tools")
        async def list_tools():
            """List available tools."""
            return {
                "tools": list(TOOL_SCHEMAS.values())
            }
        
        @self.app.post("/tools/call")
        async def call_tool(request: MCPToolRequest):
            """Execute a tool."""
            tool_name = request.name
            arguments = request.arguments
            
            if tool_name not in TOOL_REGISTRY:
                return JSONResponse(
                    status_code=404,
                    content={
                        "content": [{"type": "text", "text": f"Tool '{tool_name}' not found"}],
                        "isError": True
                    }
                )
            
            try:
                tool_func = TOOL_REGISTRY[tool_name]
                result = await tool_func(**arguments)
                return result
            except Exception as e:
                return JSONResponse(
                    status_code=500,
                    content={
                        "content": [{"type": "text", "text": f"Error executing tool: {str(e)}"}],
                        "isError": True
                    }
                )
        
        @self.app.get("/sse")
        async def sse_endpoint():
            """SSE endpoint for MCP communication."""
            async def event_generator():
                # Send initial endpoint event
                yield "event: endpoint\ndata: /tools/call\n\n"
                
                # Send available tools
                tools_data = json.dumps({"tools": list(TOOL_SCHEMAS.values())})
                yield f"event: tools\ndata: {tools_data}\n\n"
                
                # Keep connection alive
                while True:
                    yield "event: ping\ndata: {}\n\n"
                    await asyncio.sleep(30)
            
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                }
            )


# Create global server instance
server = MCPServer()
app = server.app


# For running directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
