"""Production MCP Server implementation."""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse

from ..agent.integration_agent import AGENT_RULES, IntegrationAgent
from ..utils.config import Config
from ..utils.database import database
from .tool_registry import TOOL_REGISTRY, TOOL_SCHEMAS


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
        start_time = time.time()
        safe_arguments = self._redact_secrets(arguments or {})
        query_preview = self._extract_query_preview(safe_arguments)
        logger.info(
            "mcp.tool_call.start tool=%s query=%s args=%s",
            tool_name,
            query_preview,
            self._json_preview(safe_arguments, 1200),
        )

        if tool_name not in TOOL_REGISTRY:
            result = {
                "content": [{"type": "text", "text": f"Tool '{tool_name}' not found"}],
                "isError": True,
            }
            self._log_tool_response(tool_name, result, start_time)
            return result

        tool_func = TOOL_REGISTRY[tool_name]
        try:
            result = await tool_func(**(arguments or {}))
            self._log_tool_response(tool_name, result, start_time)
            return result
        except Exception:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.exception("mcp.tool_call.error tool=%s latency_ms=%s", tool_name, latency_ms)
            raise

    @staticmethod
    def _redact_secrets(value: Any) -> Any:
        """Redact obvious secret fields before logging."""
        secret_terms = ("key", "secret", "token", "password", "authorization", "signature")
        if isinstance(value, dict):
            safe = {}
            for key, item in value.items():
                if any(term in str(key).lower() for term in secret_terms):
                    safe[key] = "***REDACTED***"
                else:
                    safe[key] = MCPServer._redact_secrets(item)
            return safe
        if isinstance(value, list):
            return [MCPServer._redact_secrets(item) for item in value]
        return value

    @staticmethod
    def _extract_query_preview(arguments: Dict[str, Any]) -> str:
        for key in ("query", "question", "endpoint_id", "use_case", "flow_type", "error_code"):
            value = arguments.get(key)
            if value:
                return str(value)[:300]
        return MCPServer._json_preview(arguments, 300)

    @staticmethod
    def _json_preview(value: Any, max_chars: int = 1000) -> str:
        try:
            text = json.dumps(value, default=str, ensure_ascii=False)
        except Exception:
            text = str(value)
        return text if len(text) <= max_chars else text[:max_chars] + "...[truncated]"

    def _log_tool_response(self, tool_name: str, result: Dict[str, Any], start_time: float) -> None:
        latency_ms = int((time.time() - start_time) * 1000)
        status = "error" if result.get("isError") else "ok"
        logger.info(
            "mcp.tool_call.response tool=%s status=%s latency_ms=%s response=%s",
            tool_name,
            status,
            latency_ms,
            self._json_preview(result, 2000),
        )

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

        @self.app.get("/agent", response_class=HTMLResponse)
        async def integration_agent_ui():
            """Terminal-style UI for the integration agent."""
            return HTMLResponse(self._agent_html())

        @self.app.post("/agent/query")
        async def integration_agent_query(request: Request):
            """Run the integration agent over MCP tools."""
            body = await request.json()
            question = body.get("question", "")
            agent = IntegrationAgent(
                tool_schemas=TOOL_SCHEMAS,
                tool_registry=TOOL_REGISTRY,
            )
            result = await agent.answer(question)
            return JSONResponse(result)
        
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

    @staticmethod
    def _agent_html() -> str:
        rules = "".join(f"<li>{rule}</li>" for rule in AGENT_RULES)
        tool_pills = "".join(
            f"<span class=\"pill\" title=\"{schema.get('description', '')}\">{name}</span>"
            for name, schema in sorted(TOOL_SCHEMAS.items())
        )
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Integration Agent</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --ink: #17202a;
      --muted: #5e6a75;
      --line: #d8dee6;
      --panel: #ffffff;
      --terminal: #101418;
      --terminal-ink: #d8f3dc;
      --accent: #0f766e;
      --accent-strong: #0b5f59;
      --warn: #b45309;
      --error: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
    }}
    .shell {{
      min-height: 100vh;
      display: block;
      max-width: 980px;
      margin: 0 auto;
    }}
    aside {{
      display: none;
      border-right: 1px solid var(--line);
      background: #fbfcfd;
      padding: 24px;
      overflow: auto;
    }}
    main {{
      padding: 24px;
      display: grid;
      grid-template-rows: minmax(0, 1fr) auto;
      gap: 16px;
      min-width: 0;
      min-height: 100vh;
    }}
    h1 {{
      font-size: 24px;
      margin: 0 0 8px;
      letter-spacing: 0;
    }}
    h2 {{
      font-size: 14px;
      margin: 28px 0 10px;
      text-transform: uppercase;
      letter-spacing: 0;
      color: var(--muted);
    }}
    p, li {{
      line-height: 1.5;
      color: var(--muted);
      font-size: 14px;
    }}
    ul {{
      padding-left: 18px;
      margin: 0;
    }}
    .querybar {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px;
      align-items: end;
    }}
    label {{
      display: block;
      font-size: 13px;
      color: var(--muted);
      margin-bottom: 6px;
    }}
    textarea {{
      width: 100%;
      min-height: 72px;
      max-height: 180px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px 12px;
      font: inherit;
      line-height: 1.4;
      color: var(--ink);
      background: #fff;
    }}
    button {{
      height: 42px;
      border: 0;
      border-radius: 6px;
      padding: 0 18px;
      background: var(--accent);
      color: #fff;
      font-weight: 700;
      cursor: pointer;
      white-space: nowrap;
    }}
    button:hover {{ background: var(--accent-strong); }}
    button:disabled {{
      background: #8ba7a4;
      cursor: wait;
    }}
    .actions {{
      display: grid;
      gap: 10px;
      justify-items: stretch;
    }}
    .toggle {{
      display: flex;
      gap: 8px;
      align-items: center;
      color: var(--muted);
      font-size: 13px;
      white-space: nowrap;
    }}
    .toggle input {{
      width: 16px;
      height: 16px;
      accent-color: var(--accent);
    }}
    .workspace {{
      display: block;
      min-height: 0;
    }}
    .terminal, .answer {{
      min-height: 0;
      overflow: auto;
      border-radius: 8px;
      border: 1px solid var(--line);
    }}
    .terminal {{
      display: none;
      background: var(--terminal);
      color: var(--terminal-ink);
      padding: 16px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
      font-size: 13px;
      line-height: 1.55;
    }}
    .line {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      margin-bottom: 10px;
    }}
    .line .stage {{ color: #7dd3fc; }}
    .line .tool {{ color: #fbbf24; }}
    .line.error {{ color: #fecaca; }}
    .answer {{
      background: var(--panel);
      line-height: 1.55;
      min-height: calc(100vh - 170px);
    }}
    .answer h2 {{
      margin: 0;
      padding: 14px 18px;
      border-bottom: 1px solid var(--line);
      color: var(--ink);
      font-size: 15px;
      text-transform: none;
    }}
    .answer-body {{
      padding: 18px;
      overflow-wrap: anywhere;
      font-size: 15px;
      color: var(--ink);
      display: flex;
      flex-direction: column;
      gap: 14px;
    }}
    .message {{
      max-width: 86%;
      border-radius: 8px;
      padding: 12px 14px;
      border: 1px solid var(--line);
    }}
    .message.user {{
      align-self: flex-end;
      background: #e7f3f1;
      border-color: #b7d9d5;
    }}
    .message.assistant {{
      align-self: flex-start;
      background: #fff;
    }}
    .message.pending {{
      color: var(--muted);
    }}
    .answer-body p {{
      margin: 0 0 12px;
    }}
    .answer-body h3 {{
      margin: 18px 0 8px;
      font-size: 16px;
      letter-spacing: 0;
    }}
    .answer-body ul {{
      margin: 0 0 14px;
      padding-left: 22px;
    }}
    .answer-body table {{
      width: 100%;
      border-collapse: collapse;
      margin: 12px 0 18px;
      font-size: 14px;
    }}
    .answer-body th, .answer-body td {{
      border: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }}
    .answer-body th {{
      background: #f1f5f9;
      font-weight: 700;
    }}
    .answer-body pre {{
      background: #0f1720;
      color: #e7f8ee;
      border-radius: 6px;
      padding: 12px;
      overflow: auto;
      white-space: pre;
      font-size: 13px;
    }}
    .answer-body code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
    }}
    .meta {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 12px;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 10px;
      color: var(--muted);
      font-size: 12px;
      background: #fff;
    }}
    @media (max-width: 900px) {{
      .shell {{ grid-template-columns: 1fr; }}
      aside {{ border-right: 0; border-bottom: 1px solid var(--line); }}
      .workspace {{ grid-template-columns: 1fr; }}
      .querybar {{ grid-template-columns: 1fr; }}
      button {{ width: 100%; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <aside>
      <h1>Integration Agent</h1>
      <p>Solutions-engineer chat backed by litellm tool-calling and Merchant MCP.</p>
      <h2>Rules</h2>
      <ul>{rules}</ul>
      <h2>Tool Surface</h2>
      <div class="meta">
        {tool_pills}
      </div>
    </aside>
    <main>
      <section class="workspace">
        <div class="terminal" id="terminal"></div>
        <div class="answer">
          <h2>Integration Agent</h2>
          <div class="answer-body" id="answer">
            <div class="message assistant">Ask an integration question. I will use OpenCode with the configured Merchant MCP when needed.</div>
          </div>
        </div>
      </section>
      <form class="querybar" id="agent-form">
        <div>
          <label for="question">Message</label>
          <textarea id="question" name="question" placeholder="Ask about an API, payload, circular, error, or integration flow"></textarea>
        </div>
        <div class="actions">
          <button id="run" type="submit">Send</button>
        </div>
      </form>
    </main>
  </div>
  <script>
    const form = document.getElementById('agent-form');
    const question = document.getElementById('question');
    const button = document.getElementById('run');
    const terminal = document.getElementById('terminal');
    const answer = document.getElementById('answer');

    function esc(value) {{
      return String(value ?? '').replace(/[&<>"']/g, ch => ({{
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
      }}[ch]));
    }}

    function line(html, cls = '') {{
      terminal.insertAdjacentHTML('beforeend', `<div class="line ${{cls}}">${{html}}</div>`);
      terminal.scrollTop = terminal.scrollHeight;
    }}

    function appendMessage(role, content, pending = false) {{
      const node = document.createElement('div');
      node.className = `message ${{role}}${{pending ? ' pending' : ''}}`;
      node.innerHTML = role === 'assistant' ? renderMarkdown(content) : inlineMarkdown(content);
      answer.appendChild(node);
      node.scrollIntoView({{ block: 'end' }});
      return node;
    }}

    function renderStep(step, index) {{
      const title = esc(step.title);
      const stage = esc(step.stage);
      const tool = step.tool ? ` <span class="tool">${{esc(step.tool)}}</span>` : '';
      const latency = step.latency_ms != null ? ` ${{step.latency_ms}}ms` : '';
      const status = step.status === 'error' ? 'error' : '';
      line(`<span class="stage">[${{index + 1}}:${{stage}}]</span>${{tool}} ${{title}}${{latency}}`, status);
      if (step.detail) line(`  ${{esc(step.detail)}}`, status);
      if (step.arguments && Object.keys(step.arguments).length) {{
        line(`  args: ${{esc(JSON.stringify(step.arguments))}}`);
      }}
      if (step.response_preview) {{
        line(`  response: ${{esc(step.response_preview.slice(0, 700))}}${{step.response_preview.length > 700 ? '...' : ''}}`, status);
      }}
    }}

    function inlineMarkdown(text) {{
      return esc(text)
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');
    }}

    function renderTable(lines) {{
      const rows = lines
        .filter(line => line.trim())
        .map(line => line.trim().replace(/^\\||\\|$/g, '').split('|').map(cell => inlineMarkdown(cell.trim())));
      if (!rows.length) return '';
      const header = rows[0].map(cell => `<th>${{cell}}</th>`).join('');
      const body = rows.slice(2).map(row => `<tr>${{row.map(cell => `<td>${{cell}}</td>`).join('')}}</tr>`).join('');
      return `<table><thead><tr>${{header}}</tr></thead><tbody>${{body}}</tbody></table>`;
    }}

    function renderMarkdown(text) {{
      const lines = String(text || '').split('\\n');
      const html = [];
      let paragraph = [];
      let list = [];
      let table = [];
      let code = [];
      let inCode = false;

      function flushParagraph() {{
        if (paragraph.length) {{
          html.push(`<p>${{inlineMarkdown(paragraph.join(' '))}}</p>`);
          paragraph = [];
        }}
      }}
      function flushList() {{
        if (list.length) {{
          html.push(`<ul>${{list.map(item => `<li>${{inlineMarkdown(item)}}</li>`).join('')}}</ul>`);
          list = [];
        }}
      }}
      function flushTable() {{
        if (table.length) {{
          html.push(renderTable(table));
          table = [];
        }}
      }}

      for (const line of lines) {{
        if (line.trim().startsWith('```')) {{
          if (inCode) {{
            html.push(`<pre><code>${{esc(code.join('\\n'))}}</code></pre>`);
            code = [];
            inCode = false;
          }} else {{
            flushParagraph();
            flushList();
            flushTable();
            inCode = true;
          }}
          continue;
        }}
        if (inCode) {{
          code.push(line);
          continue;
        }}
        if (/^\\s*\\|.+\\|\\s*$/.test(line)) {{
          flushParagraph();
          flushList();
          table.push(line);
          continue;
        }}
        flushTable();
        const heading = line.match(/^#{1,3}\\s+(.+)$/);
        if (heading) {{
          flushParagraph();
          flushList();
          html.push(`<h3>${{inlineMarkdown(heading[1])}}</h3>`);
          continue;
        }}
        const bullet = line.match(/^\\s*[-*]\\s+(.+)$/);
        if (bullet) {{
          flushParagraph();
          list.push(bullet[1]);
          continue;
        }}
        if (!line.trim()) {{
          flushParagraph();
          flushList();
          continue;
        }}
        paragraph.push(line.trim());
      }}
      flushParagraph();
      flushList();
      flushTable();
      if (inCode) html.push(`<pre><code>${{esc(code.join('\\n'))}}</code></pre>`);
      return html.join('');
    }}

    form.addEventListener('submit', async event => {{
      event.preventDefault();
      const message = question.value.trim();
      if (!message) return;
      appendMessage('user', message);
      const pending = appendMessage('assistant', 'Thinking...', true);
      question.value = '';
      button.disabled = true;
      try {{
        const response = await fetch('/agent/query', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ question: message }})
        }});
        const data = await response.json();
        pending.classList.remove('pending');
        pending.innerHTML = renderMarkdown(data.answer || 'No answer returned.');
      }} catch (err) {{
        pending.classList.remove('pending');
        pending.innerHTML = renderMarkdown(`Agent run failed: ${{err.message}}`);
      }} finally {{
        button.disabled = false;
      }}
    }});
  </script>
</body>
</html>"""


# Create global server instance
server = MCPServer()
app = server.app


# For running directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
