"""Rule-driven integration agent that orchestrates MCP tools via litellm tool-calling."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List

import litellm

from ..utils.config import Config


logger = logging.getLogger(__name__)


AGENT_RULES = [
    "Classify the client question before calling tools.",
    "Use MCP tools for retrieval, specs, flows, validation, testing, and debugging.",
    "Never answer integration details from model memory when MCP context is available.",
    "Prefer latest API specs and business-use-case search for product/API mapping.",
    "Use search_docs with namespace npci_circulars for NPCI circular questions.",
    "If retrieved circular content is metadata-only or insufficient, say so explicitly.",
    "Ask for missing merchant/environment details only when they block a safe answer.",
    "Answer in a natural solutions-engineer style without rigid sections.",
]


SOLUTIONS_ENGINEER_PROMPT = """You are a senior payments solutions engineer.

You have access to Merchant MCP tools for product, API, document, circular, integration, testing, and debugging context. Call tools when you need specifics; do not ask the caller to run tools. Answer the client directly in a natural chat style. Do not include evidence, source, trace, or tool sections. Use markdown tables for API specs, headers, request fields, response fields, error mappings, or comparisons when useful. Keep sample request and response bodies in fenced `json` code blocks.
"""


ToolCallable = Callable[..., Awaitable[Dict[str, Any]]]

_MAX_TOOL_ITERATIONS = 8


@dataclass
class AgentStep:
    stage: str
    title: str
    status: str = "done"
    detail: str = ""
    tool: str | None = None
    arguments: Dict[str, Any] | None = None
    response_preview: str | None = None
    latency_ms: int | None = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "title": self.title,
            "status": self.status,
            "detail": self.detail,
            "tool": self.tool,
            "arguments": self.arguments or {},
            "response_preview": self.response_preview,
            "latency_ms": self.latency_ms,
        }


def _mcp_schemas_to_litellm_tools(
    tool_schemas: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Convert MCP tool schemas to litellm/OpenAI function-calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": schema.get("description", ""),
                "parameters": schema.get("inputSchema", {"type": "object", "properties": {}}),
            },
        }
        for name, schema in sorted(tool_schemas.items())
    ]


def _extract_tool_text(result: Dict[str, Any]) -> str:
    """Flatten an MCP tool result dict into a single text string for the LLM."""
    content = result.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return json.dumps(result, default=str, ensure_ascii=False)


class IntegrationAgent:
    """In-process agent: litellm tool-calling loop over the MCP tool registry."""

    def __init__(
        self,
        tool_schemas: Dict[str, Dict] | None = None,
        tool_registry: Dict[str, ToolCallable] | None = None,
    ):
        self.tool_schemas = tool_schemas or {}
        self.tool_registry = tool_registry or {}

    async def answer(self, question: str) -> Dict[str, Any]:
        question = (question or "").strip()
        if not question:
            return {
                "answer": "Please enter an integration question.",
                "intent": "empty",
                "rules": AGENT_RULES,
                "available_tools": self._available_tools(),
                "steps": [AgentStep("input", "No question supplied", "error").as_dict()],
                "tool_results": [],
            }

        steps: List[AgentStep] = []
        intent = self._classify(question)
        steps.append(AgentStep(
            "classify",
            "Classified request",
            detail=f"Intent: {intent}.",
        ))

        answer = await self._run_tool_calling_loop(question, intent, steps)

        steps.append(AgentStep(
            "answer",
            "Generated response",
            detail="Final response produced by the LLM after tool orchestration.",
        ))

        return {
            "answer": answer,
            "intent": intent,
            "rules": AGENT_RULES,
            "available_tools": self._available_tools(),
            "steps": [step.as_dict() for step in steps],
            "tool_results": [],
        }

    def _classify(self, question: str) -> str:
        q = question.lower()
        if "npci" in q or "circular" in q or "upi lite" in q or "rupay" in q:
            return "circular_or_scheme_context"
        if any(term in q for term in ("payload", "request body", "sample request", "generate json")):
            return "payload_build"
        if any(term in q for term in ("code", "sdk", "python", "java", "node", "go", "php", "example")):
            return "code_generation"
        if any(term in q for term in ("webhook", "callback", "signature", "hmac")):
            return "webhook_debug"
        if re.search(r"\b[A-Z0-9_]{3,}[_-][A-Z0-9_]{2,}\b", question) or "endpoint" in q or "api" in q:
            return "api_spec"
        if any(term in q for term in ("error", "declined", "failed", "failure", "code")):
            return "debugging"
        if any(term in q for term in ("diagram", "mermaid", "visual", "chart")):
            return "flow_diagram"
        if any(term in q for term in ("concept", "explain", "what is", "how does")):
            return "concept_explanation"
        if any(term in q for term in ("flow", "sequence", "steps", "integrate", "integration")):
            return "integration_flow"
        if any(term in q for term in ("test", "sandbox", "uat", "checklist")):
            return "testing"
        return "general_documentation"

    async def _run_tool_calling_loop(
        self,
        question: str,
        intent: str,
        steps: List[AgentStep],
    ) -> str:
        tools = _mcp_schemas_to_litellm_tools(self.tool_schemas)
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SOLUTIONS_ENGINEER_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Client question: {question}\n"
                    f"Classified intent: {intent}\n\n"
                    "Use the available MCP tools when needed, then answer the client directly."
                ),
            },
        ]

        model = Config.LLM_MODEL
        if "/" not in model and Config.LITELLM_LLM_API_BASE:
            model = f"openai/{model}"

        for iteration in range(_MAX_TOOL_ITERATIONS):
            started = time.time()
            try:
                response = await litellm.acompletion(
                    model=model,
                    messages=messages,
                    tools=tools or None,
                    temperature=0.3,
                    api_base=Config.LITELLM_LLM_API_BASE or None,
                    api_key=Config.LITELLM_LLM_API_KEY or None,
                )
            except Exception as exc:
                latency_ms = int((time.time() - started) * 1000)
                steps.append(AgentStep(
                    "llm",
                    f"LLM call failed (iteration {iteration + 1})",
                    status="error",
                    detail=str(exc),
                    latency_ms=latency_ms,
                ))
                return f"I could not complete the chat because the LLM call failed: {exc}"

            latency_ms = int((time.time() - started) * 1000)
            choice = response.choices[0]
            message = choice.message

            tool_calls = getattr(message, "tool_calls", None) or []

            if not tool_calls:
                answer = (message.content or "").strip()
                steps.append(AgentStep(
                    "llm",
                    f"LLM produced final answer (iteration {iteration + 1})",
                    detail=f"Returned {len(answer)} characters.",
                    response_preview=answer[:1200],
                    latency_ms=latency_ms,
                ))
                return answer or "The LLM returned an empty response. Please retry the question."

            messages.append(message.model_dump(exclude_none=True))

            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                raw_args = tool_call.function.arguments or "{}"
                try:
                    arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    arguments = {}

                tool_started = time.time()
                step = AgentStep(
                    "tool",
                    f"Called {tool_name}",
                    tool=tool_name,
                    arguments=arguments,
                )

                handler = self.tool_registry.get(tool_name)
                if handler is None:
                    tool_result_text = f"Tool '{tool_name}' not found."
                    step.status = "error"
                    step.detail = tool_result_text
                else:
                    try:
                        result = await handler(**arguments)
                        tool_result_text = _extract_tool_text(result)
                        step.detail = f"Returned {len(tool_result_text)} characters."
                        step.response_preview = tool_result_text[:1200]
                    except Exception as exc:
                        tool_result_text = f"Tool '{tool_name}' raised: {exc}"
                        step.status = "error"
                        step.detail = tool_result_text

                step.latency_ms = int((time.time() - tool_started) * 1000)
                steps.append(step)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": tool_result_text,
                })

        steps.append(AgentStep(
            "llm",
            f"Reached max tool iterations ({_MAX_TOOL_ITERATIONS})",
            status="error",
            detail="The agent exceeded the tool-call iteration cap without producing a final answer.",
        ))
        return (
            "I reached the maximum number of tool lookups without producing a final answer. "
            "Please rephrase the question or break it into smaller parts."
        )

    def _available_tools(self) -> List[Dict[str, str]]:
        return [
            {
                "name": schema.get("name", name),
                "description": schema.get("description", ""),
            }
            for name, schema in sorted(self.tool_schemas.items())
        ]
