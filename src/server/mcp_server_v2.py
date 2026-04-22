"""
Production MCP Server with Full JSON-RPC 2.0 Support.

Implements MCP protocol over SSE for OpenCode compatibility.
"""

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field

from fastapi import FastAPI, Request, Response, Body
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

# Tool registry
TOOL_REGISTRY: Dict[str, Callable] = {
    "get_api_spec": get_api_spec,
    "get_integration_guide": get_integration_guide,
    "get_flow": get_flow,
    "search_docs": search_docs,
    "generate_payload": generate_payload,
    "get_code_example": get_code_example,
    "get_webhook_handler": get_webhook_handler,
    "validate_payload": validate_payload,
    "test_sandbox": test_sandbox,
    "explain_error": explain_error,
    "get_test_cases": get_test_cases,
    "check_integration": check_integration,
    "diagnose_webhook": diagnose_webhook,
    "lookup_error_map": lookup_error_map,
    "search_known_issues": search_known_issues,
}

# MCP Protocol Schemas
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
        "description": "Explain an error code with root cause, resolution steps, and related context",
        "inputSchema": {
            "type": "object",
            "properties": {
                "error_code": {"type": "string", "description": "Error code or error message"},
                "context": {"type": "string", "description": "Additional context about when error occurred", "default": None}
            },
            "required": ["error_code"]
        }
    },
    "get_test_cases": {
        "name": "get_test_cases",
        "description": "Get test cases for an endpoint with inputs, expected outputs, and validation rules",
        "inputSchema": {
            "type": "object",
            "properties": {
                "endpoint_id": {"type": "string", "description": "Target endpoint identifier"},
                "scenario": {"type": "string", "description": "Test scenario (success, failure, edge)", "default": "all"}
            },
            "required": ["endpoint_id"]
        }
    },
    "check_integration": {
        "name": "check_integration",
        "description": "Check integration setup with prerequisites, common mistakes, and quick fixes",
        "inputSchema": {
            "type": "object",
            "properties": {
                "step": {"type": "string", "description": "Current integration step", "default": "all"},
                "environment": {"type": "string", "enum": ["sandbox", "production"], "description": "Environment being tested", "default": "sandbox"}
            },
            "default": {}
        }
    },
    "diagnose_webhook": {
        "name": "diagnose_webhook",
        "description": "Diagnose webhook issues with delivery debugging, signature verification, and retry logic",
        "inputSchema": {
            "type": "object",
            "properties": {
                "event_type": {"type": "string", "description": "Webhook event type"},
                "symptom": {"type": "string", "description": "Symptom description", "default": None}
            },
            "required": ["event_type"]
        }
    },
    "lookup_error_map": {
        "name": "lookup_error_map",
        "description": "Look up error code in map with category, severity, HTTP mapping, and resolution",
        "inputSchema": {
            "type": "object",
            "properties": {
                "error_code": {"type": "string", "description": "Error code to look up"},
                "source": {"type": "string", "description": "Error source (gateway, network, validation)", "default": None}
            },
            "required": ["error_code"]
        }
    },
    "search_known_issues": {
        "name": "search_known_issues",
        "description": "Search known issues with workarounds and related internal tickets",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Issue description or keywords"},
                "affected_versions": {"type": "string", "description": "Version range affected", "default": None}
            },
            "required": ["query"]
        }
    },
}


@dataclass
class Session:
    """MCP session state."""
    session_id: str
    client_info: Optional[Dict] = None
    initialized: bool = False
    message_queue: asyncio.Queue = field(default_factory=asyncio.Queue)


class MCPServer:
    """Full MCP Server with JSON-RPC 2.0 support."""
    
    PROTOCOL_VERSION = "2024-11-05"
    
    def __init__(self):
        self.app = FastAPI(
            title="Merchant Integration MCP",
            description="MCP server for Juspay payment integration support",
            version="1.0.0"
        )
        self.sessions: Dict[str, Session] = {}
        self._setup_routes()
    
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
        
        @self.app.get("/sse")
        async def sse_endpoint():
            """SSE endpoint for MCP communication."""
            session_id = str(uuid.uuid4())
            session = Session(session_id=session_id)
            self.sessions[session_id] = session
            
            async def event_generator():
                # Send endpoint event with message URL
                yield f"event: endpoint\ndata: /messages?session_id={session_id}\n\n"
                
                # Process messages from queue
                while True:
                    try:
                        message = await asyncio.wait_for(
                            session.message_queue.get(),
                            timeout=30.0
                        )
                        yield f"event: message\ndata: {json.dumps(message)}\n\n"
                    except asyncio.TimeoutError:
                        # Send keepalive ping
                        yield f"event: ping\ndata: {{}}\n\n"
            
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                }
            )
        
        @self.app.post("/messages")
        async def handle_message(request: Request):
            """Handle JSON-RPC messages from client."""
            session_id = request.query_params.get("session_id")
            if not session_id or session_id not in self.sessions:
                return JSONResponse(
                    status_code=400,
                    content={
                        "jsonrpc": "2.0",
                        "error": {"code": -32600, "message": "Invalid session"},
                        "id": None
                    }
                )
            
            session = self.sessions[session_id]
            
            try:
                body = await request.json()
            except:
                return JSONResponse(
                    status_code=400,
                    content={
                        "jsonrpc": "2.0",
                        "error": {"code": -32700, "message": "Parse error"},
                        "id": None
                    }
                )
            
            # Handle batch requests
            if isinstance(body, list):
                responses = []
                for msg in body:
                    response = await self._handle_single_message(msg, session)
                    if response:
                        responses.append(response)
                return JSONResponse(responses if responses else {})
            
            # Handle single request
            response = await self._handle_single_message(body, session)
            return JSONResponse(response) if response else JSONResponse({})
    
    async def _handle_single_message(self, message: Dict, session: Session) -> Optional[Dict]:
        """Handle a single JSON-RPC message."""
        if not isinstance(message, dict):
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid Request"},
                "id": None
            }
        
        jsonrpc = message.get("jsonrpc")
        method = message.get("method")
        params = message.get("params", {})
        msg_id = message.get("id")
        
        if jsonrpc != "2.0":
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid Request"},
                "id": msg_id
            }
        
        # Notifications don't need responses
        is_notification = msg_id is None
        
        try:
            if method == "initialize":
                return await self._handle_initialize(params, session, msg_id)
            
            elif method == "initialized":
                session.initialized = True
                return None  # Notification, no response
            
            elif method == "tools/list":
                return await self._handle_tools_list(msg_id)
            
            elif method == "tools/call":
                return await self._handle_tools_call(params, msg_id)
            
            elif method == "resources/list":
                return {"jsonrpc": "2.0", "result": {"resources": []}, "id": msg_id}
            
            elif method == "prompts/list":
                return {"jsonrpc": "2.0", "result": {"prompts": []}, "id": msg_id}
            
            else:
                if is_notification:
                    return None
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                    "id": msg_id
                }
        
        except Exception as e:
            if is_notification:
                return None
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
                "id": msg_id
            }
    
    async def _handle_initialize(self, params: Dict, session: Session, msg_id: Any) -> Dict:
        """Handle initialize request."""
        session.client_info = params.get("clientInfo", {})
        
        return {
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": self.PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {}
                },
                "serverInfo": {
                    "name": "merchant-integration-mcp",
                    "version": "1.0.0"
                }
            },
            "id": msg_id
        }
    
    async def _handle_tools_list(self, msg_id: Any) -> Dict:
        """Handle tools/list request."""
        return {
            "jsonrpc": "2.0",
            "result": {
                "tools": list(TOOL_SCHEMAS.values())
            },
            "id": msg_id
        }
    
    async def _handle_tools_call(self, params: Dict, msg_id: Any) -> Dict:
        """Handle tools/call request."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if not tool_name or tool_name not in TOOL_REGISTRY:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32602,
                    "message": f"Unknown tool: {tool_name}"
                },
                "id": msg_id
            }
        
        try:
            tool_func = TOOL_REGISTRY[tool_name]
            result = await tool_func(**arguments)
            
            # Convert result to MCP format
            return {
                "jsonrpc": "2.0",
                "result": result,
                "id": msg_id
            }
        
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Tool execution error: {str(e)}"
                },
                "id": msg_id
            }


# Create global server instance
server = MCPServer()
app = server.app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
