"""MCP Server implementation."""

import json
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from mcp.server import Server
from mcp.types import TextContent, Tool

from ..utils.db import db
from ..utils.llm import llm_client
from ..tools.understanding import get_api_spec, get_integration_guide, get_flow, search_docs
from ..tools.building import generate_payload, get_code_example, get_webhook_handler, validate_payload
from ..tools.testing import test_sandbox, explain_error, get_test_cases, check_integration
from ..tools.debugging import diagnose_webhook, lookup_error_map, search_known_issues


class MCPServer:
    """MCP Server with all tools."""
    
    def __init__(self):
        self.app = FastAPI(title="Merchant Integration MCP")
        self.mcp_server = Server("merchant-integration")
        self._setup_tools()
        self._setup_routes()
    
    def _setup_tools(self):
        """Register all MCP tools."""
        
        # Understanding tools
        self.mcp_server.add_tool(
            name="get_api_spec",
            description="Get complete API specification for an endpoint",
            input_schema={
                "type": "object",
                "properties": {
                    "endpoint_id": {"type": "string"},
                    "version": {"type": "string", "default": "v1"}
                },
                "required": ["endpoint_id"]
            },
            handler=get_api_spec
        )
        
        self.mcp_server.add_tool(
            name="get_integration_guide",
            description="Get step-by-step integration guide for a use case",
            input_schema={
                "type": "object",
                "properties": {
                    "use_case": {"type": "string", "enum": ["payment", "collect", "mandate", "refund", "subscription"]},
                    "language": {"type": "string", "default": "python"}
                },
                "required": ["use_case"]
            },
            handler=get_integration_guide
        )
        
        self.mcp_server.add_tool(
            name="get_flow",
            description="Get ordered API call sequence for a flow type",
            input_schema={
                "type": "object",
                "properties": {
                    "flow_type": {"type": "string"},
                    "scenario": {"type": "string"}
                },
                "required": ["flow_type"]
            },
            handler=get_flow
        )
        
        self.mcp_server.add_tool(
            name="search_docs",
            description="Search documentation using semantic search",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 5},
                    "namespace": {"type": "string"}
                },
                "required": ["query"]
            },
            handler=search_docs
        )
        
        # Building tools
        self.mcp_server.add_tool(
            name="generate_payload",
            description="Generate a valid JSON payload for an endpoint",
            input_schema={
                "type": "object",
                "properties": {
                    "endpoint_id": {"type": "string"},
                    "params": {"type": "object"},
                    "include_optional": {"type": "boolean", "default": False}
                },
                "required": ["endpoint_id"]
            },
            handler=generate_payload
        )
        
        self.mcp_server.add_tool(
            name="get_code_example",
            description="Get working code example for an endpoint",
            input_schema={
                "type": "object",
                "properties": {
                    "endpoint_id": {"type": "string"},
                    "language": {"type": "string", "enum": ["python", "nodejs", "java", "go", "php"]}
                },
                "required": ["endpoint_id", "language"]
            },
            handler=get_code_example
        )
        
        self.mcp_server.add_tool(
            name="get_webhook_handler",
            description="Get webhook handler code with signature verification",
            input_schema={
                "type": "object",
                "properties": {
                    "event_type": {"type": "string"},
                    "language": {"type": "string", "enum": ["python", "nodejs", "java", "go", "php"]}
                },
                "required": ["event_type", "language"]
            },
            handler=get_webhook_handler
        )
        
        self.mcp_server.add_tool(
            name="validate_payload",
            description="Validate a payload against endpoint schema",
            input_schema={
                "type": "object",
                "properties": {
                    "endpoint_id": {"type": "string"},
                    "payload": {"type": "object"}
                },
                "required": ["endpoint_id", "payload"]
            },
            handler=validate_payload
        )
        
        # Testing tools
        self.mcp_server.add_tool(
            name="test_sandbox",
            description="Test API call in sandbox with response annotation",
            input_schema={
                "type": "object",
                "properties": {
                    "endpoint_id": {"type": "string"},
                    "payload": {"type": "object"},
                    "api_key": {"type": "string"}
                },
                "required": ["endpoint_id", "payload"]
            },
            handler=test_sandbox
        )
        
        self.mcp_server.add_tool(
            name="explain_error",
            description="Explain an error code with root cause and fix suggestions",
            input_schema={
                "type": "object",
                "properties": {
                    "error_code": {"type": "string"},
                    "context": {"type": "object"},
                    "bank": {"type": "string"}
                },
                "required": ["error_code"]
            },
            handler=explain_error
        )
        
        self.mcp_server.add_tool(
            name="get_test_cases",
            description="Get test scenarios for a flow type",
            input_schema={
                "type": "object",
                "properties": {
                    "flow_type": {"type": "string"},
                    "coverage": {"type": "string", "enum": ["essential", "comprehensive"], "default": "essential"}
                },
                "required": ["flow_type"]
            },
            handler=get_test_cases
        )
        
        self.mcp_server.add_tool(
            name="check_integration",
            description="Check integration readiness against checklist",
            input_schema={
                "type": "object",
                "properties": {
                    "checklist_type": {"type": "string"}
                },
                "required": ["checklist_type"]
            },
            handler=check_integration
        )
        
        # Debugging tools
        self.mcp_server.add_tool(
            name="diagnose_webhook",
            description="Diagnose webhook issues from request data",
            input_schema={
                "type": "object",
                "properties": {
                    "headers": {"type": "object"},
                    "body": {"type": "string"},
                    "expected_signature": {"type": "string"},
                    "webhook_secret": {"type": "string"}
                },
                "required": ["headers", "body"]
            },
            handler=diagnose_webhook
        )
        
        self.mcp_server.add_tool(
            name="lookup_error_map",
            description="Look up error code with full context",
            input_schema={
                "type": "object",
                "properties": {
                    "error_code": {"type": "string"},
                    "bank": {"type": "string"},
                    "include_related": {"type": "boolean", "default": True}
                },
                "required": ["error_code"]
            },
            handler=lookup_error_map
        )
        
        self.mcp_server.add_tool(
            name="search_known_issues",
            description="Search known issues from support KB",
            input_schema={
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "category": {"type": "string"},
                    "limit": {"type": "integer", "default": 5}
                },
                "required": ["description"]
            },
            handler=search_known_issues
        )
    
    def _setup_routes(self):
        """Setup FastAPI routes."""
        
        @self.app.on_event("startup")
        async def startup():
            await db.connect()
            await db.init_schema()
        
        @self.app.on_event("shutdown")
        async def shutdown():
            await db.close()
        
        @self.app.get("/health")
        async def health():
            return {"status": "healthy"}
        
        @self.app.get("/sse")
        async def sse_endpoint():
            """SSE endpoint for MCP communication."""
            async def event_generator():
                # Send initial endpoint event
                yield "event: endpoint\ndata: /messages\\n\\n"
                
                # Keep connection alive
                import asyncio
                while True:
                    yield "event: ping\ndata: {}\\n\\n"
                    await asyncio.sleep(30)
            
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream"
            )
    
    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """Run the server."""
        import uvicorn
        uvicorn.run(self.app, host=host, port=port)


# Create server instance
server = MCPServer()
app = server.app
