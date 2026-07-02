"""Production MCP Server implementation."""

import asyncio
import json
import time
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse

from ..utils.database import database
from .tool_registry import TOOL_REGISTRY, TOOL_SCHEMAS


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

    async def _call_tool_direct(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return the direct HTTP response shape."""
        if tool_name not in TOOL_REGISTRY:
            return {
                "content": [{"type": "text", "text": f"Tool '{tool_name}' not found"}],
                "isError": True,
            }

        tool_func = TOOL_REGISTRY[tool_name]
        return await tool_func(**(arguments or {}))

    @staticmethod
    def _json_rpc_error(code: int, message: str, msg_id: Any = None) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "error": {"code": code, "message": message},
            "id": msg_id,
        }

    async def _handle_json_rpc_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle one MCP JSON-RPC message."""
        if not isinstance(message, dict):
            return self._json_rpc_error(-32600, "Invalid Request")

        msg_id = message.get("id")
        method = message.get("method")
        params = message.get("params") or {}
        is_notification = msg_id is None

        if message.get("jsonrpc") != "2.0":
            return self._json_rpc_error(-32600, "Invalid Request", msg_id)

        try:
            if method == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "result": {
                        "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                        "capabilities": {"tools": {}},
                        "serverInfo": {
                            "name": "merchant-integration-mcp",
                            "version": "1.0.0",
                        },
                    },
                    "id": msg_id,
                }

            if method == "initialized":
                return None

            if method == "ping":
                return {"jsonrpc": "2.0", "result": {}, "id": msg_id}

            if method == "tools/list":
                return {
                    "jsonrpc": "2.0",
                    "result": {"tools": list(TOOL_SCHEMAS.values())},
                    "id": msg_id,
                }

            if method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments") or {}
                if not tool_name:
                    return self._json_rpc_error(-32602, "Missing tool name", msg_id)
                result = await self._call_tool_direct(tool_name, arguments)
                return {"jsonrpc": "2.0", "result": result, "id": msg_id}

            if method in {"resources/list", "prompts/list"}:
                key = "resources" if method == "resources/list" else "prompts"
                return {"jsonrpc": "2.0", "result": {key: []}, "id": msg_id}

            if is_notification:
                return None
            return self._json_rpc_error(-32601, f"Method not found: {method}", msg_id)

        except Exception as exc:
            if is_notification:
                return None
            return self._json_rpc_error(-32603, f"Internal error: {exc}", msg_id)

    async def _handle_post_body(self, body: Any) -> JSONResponse:
        """Accept direct tool calls and MCP JSON-RPC POST bodies."""
        if isinstance(body, list):
            responses = []
            for item in body:
                response = await self._handle_json_rpc_message(item)
                if response is not None:
                    responses.append(response)
            return JSONResponse(responses)

        if isinstance(body, dict) and body.get("jsonrpc") == "2.0":
            response = await self._handle_json_rpc_message(body)
            return JSONResponse(response or {})

        if isinstance(body, dict) and "name" in body:
            try:
                result = await self._call_tool_direct(
                    body.get("name"),
                    body.get("arguments") or {},
                )
                status_code = 404 if result.get("isError") and "not found" in str(result).lower() else 200
                return JSONResponse(result, status_code=status_code)
            except Exception as exc:
                return JSONResponse(
                    status_code=500,
                    content={
                        "content": [{"type": "text", "text": f"Error executing tool: {exc}"}],
                        "isError": True,
                    },
                )

        return JSONResponse(
            status_code=400,
            content={
                "content": [{
                    "type": "text",
                    "text": "Invalid POST body. Use MCP JSON-RPC or {'name': tool, 'arguments': {...}}.",
                }],
                "isError": True,
            },
        )

    def _sse_response(self, post_endpoint: str) -> StreamingResponse:
        """Create an SSE response that announces the POST endpoint."""
        async def event_generator():
            yield f"event: endpoint\ndata: {post_endpoint}\n\n"
            tools_data = json.dumps({"tools": list(TOOL_SCHEMAS.values())})
            yield f"event: tools\ndata: {tools_data}\n\n"

            while True:
                yield "event: ping\ndata: {}\n\n"
                await asyncio.sleep(30)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
    
    def _setup_middleware(self):
        """Setup request middleware."""
        
        @self.app.middleware("http")
        async def log_requests(request: Request, call_next):
            start_time = time.time()
            response = await call_next(request)
            duration = (time.time() - start_time) * 1000
            
            # Log to database if not health check
            if request.url.path not in ['/health', '/sse', '/newton-hs'] and database._pool:
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
        async def call_tool(request: Request):
            """Execute a direct tool call or MCP JSON-RPC message."""
            return await self._handle_post_body(await request.json())
        
        @self.app.get("/sse")
        async def sse_endpoint():
            """SSE endpoint for MCP communication."""
            return self._sse_response("/tools/call")

        @self.app.post("/sse")
        async def sse_post_endpoint(request: Request):
            """Compatibility POST endpoint for clients that post to the SSE URL."""
            return await self._handle_post_body(await request.json())

        @self.app.get("/mcp")
        async def mcp_sse_endpoint():
            """Compatibility SSE endpoint for clients configured to /mcp."""
            return self._sse_response("/mcp")

        @self.app.post("/mcp")
        async def mcp_post_endpoint(request: Request):
            """Compatibility POST endpoint for streamable HTTP-style MCP clients."""
            return await self._handle_post_body(await request.json())

        @self.app.get("/newton-hs")
        async def newton_hs_sse_endpoint():
            """Compatibility SSE endpoint for clients configured to /newton-hs."""
            return self._sse_response("/newton-hs")

        @self.app.post("/newton-hs")
        async def newton_hs_post_endpoint(request: Request):
            """Compatibility POST endpoint for MCP JSON-RPC clients."""
            return await self._handle_post_body(await request.json())


# Create global server instance
server = MCPServer()
app = server.app


# For running directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
