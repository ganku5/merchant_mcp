"""Rule-driven integration agent that orchestrates MCP tools."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
import shlex
import sys
from dataclasses import dataclass
from typing import Any, Dict, List

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

Use the Merchant MCP tools configured inside OpenCode whenever product, API, document, circular, integration, testing, or debugging context is needed. Do not ask the caller to run tools and do not return tool-call JSON. The application will not execute tools for you; OpenCode must use its own configured MCP integration.

Answer the client directly in a natural chat style. Do not include evidence, source, trace, or tool sections. Use markdown tables for API specs, headers, request fields, response fields, error mappings, or comparisons when useful. Keep sample request and response bodies in fenced `json` code blocks.
"""


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


class IntegrationAgent:
    """OpenCode-driven chat agent; OpenCode owns MCP tool use internally."""

    def __init__(self, tool_schemas: Dict[str, Dict] | None = None):
        self.tool_schemas = tool_schemas or {}

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
            detail=f"Intent: {intent}. OpenCode will answer using its configured MCP servers when needed.",
        ))

        answer = await self._run_opencode_chat(question, intent, steps)

        steps.append(AgentStep(
            "answer",
            "Received OpenCode response",
            detail="The final response was produced by OpenCode.",
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

    async def _run_opencode_chat(
        self,
        question: str,
        intent: str,
        steps: List[AgentStep],
    ) -> str:
        messages = [
            {"role": "system", "content": SOLUTIONS_ENGINEER_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Client question: {question}\n"
                    f"Classified intent: {intent}\n\n"
                    "Use the configured Merchant MCP inside OpenCode if needed, then answer the client directly."
                ),
            },
        ]

        started = time.time()
        try:
            raw = await self._chat_for_agent(messages)
            answer = self._clean_opencode_output(raw)
            steps.append(AgentStep(
                "opencode",
                "OpenCode completed chat response",
                detail=f"Returned {len(answer)} characters.",
                response_preview=answer[:1200],
                latency_ms=int((time.time() - started) * 1000),
            ))
            return answer or "OpenCode returned an empty response. Please retry the question."
        except Exception as exc:
            steps.append(AgentStep(
                "opencode",
                "OpenCode failed",
                status="error",
                detail=str(exc),
                latency_ms=int((time.time() - started) * 1000),
            ))
            return f"I could not complete the chat because OpenCode failed: {exc}"

    async def _chat_for_agent(self, messages: List[Dict[str, str]]) -> str:
        backend = (Config.AGENT_RESPONSE_BACKEND or "litellm").strip().lower()
        if backend != "opencode":
            raise RuntimeError("AGENT_RESPONSE_BACKEND must be 'opencode' for the integration agent")
        return await self._chat_with_opencode_cli(messages)

    async def _chat_with_opencode_cli(self, messages: List[Dict[str, str]]) -> str:
        command = Config.OPENCODE_CLI_COMMAND.strip()
        if not command:
            raise RuntimeError("OPENCODE_CLI_COMMAND is empty")

        prompt = self._messages_to_cli_prompt(messages)
        prompt_bytes = len(prompt.encode("utf-8"))
        parts = self._opencode_command_with_trace_flags(shlex.split(command))
        if not parts:
            raise RuntimeError("OPENCODE_CLI_COMMAND did not parse into a command")

        workdir = Config.OPENCODE_WORKDIR or "/tmp/merchant_mcp_opencode"
        os.makedirs(workdir, exist_ok=True)

        use_stdin = True
        args = []
        for part in parts:
            if "{prompt}" in part:
                args.append(part.replace("{prompt}", prompt))
                use_stdin = False
            else:
                args.append(part)

        timeout_seconds = max(600, int(Config.OPENCODE_CLI_TIMEOUT_SECONDS))
        logger.info(
            "opencode.start command=%s prompt_bytes=%s timeout_seconds=%s cwd=%s",
            self._redacted_command_preview(args),
            prompt_bytes,
            timeout_seconds,
            workdir,
        )
        self._print_opencode_log(
            "start",
            (
                f"command={self._redacted_command_preview(args)} "
                f"prompt_bytes={prompt_bytes} timeout_seconds={timeout_seconds} cwd={workdir}"
            ),
        )
        started = time.time()
        stdin_config = asyncio.subprocess.PIPE if use_stdin else asyncio.subprocess.DEVNULL
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=stdin_config,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workdir,
            env=self._opencode_env(),
        )

        stdout_chunks: List[bytes] = []
        stderr_chunks: List[bytes] = []
        tasks = [
            asyncio.create_task(self._write_opencode_stdin(
                proc,
                prompt.encode("utf-8") if use_stdin else None,
            )),
            asyncio.create_task(self._read_opencode_stream("stdout", proc.stdout, stdout_chunks)),
            asyncio.create_task(self._read_opencode_stream("stderr", proc.stderr, stderr_chunks)),
            asyncio.create_task(proc.wait()),
        ]
        try:
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            for task in tasks:
                task.cancel()
            elapsed_ms = int((time.time() - started) * 1000)
            logger.error(
                "opencode.timeout elapsed_ms=%s prompt_bytes=%s command=%s",
                elapsed_ms,
                prompt_bytes,
                self._redacted_command_preview(args),
            )
            raise RuntimeError(
                f"OpenCode CLI timed out after {timeout_seconds}s "
                f"(prompt_bytes={prompt_bytes}, cwd={workdir})"
            )

        stdout = b"".join(stdout_chunks)
        stderr = b"".join(stderr_chunks)
        out = stdout.decode("utf-8", errors="replace").strip()
        err = stderr.decode("utf-8", errors="replace").strip()
        elapsed_ms = int((time.time() - started) * 1000)
        logger.info(
            "opencode.finish returncode=%s elapsed_ms=%s stdout_bytes=%s stderr_bytes=%s",
            proc.returncode,
            elapsed_ms,
            len(stdout),
            len(stderr),
        )
        self._print_opencode_log(
            "finish",
            (
                f"returncode={proc.returncode} elapsed_ms={elapsed_ms} "
                f"stdout_bytes={len(stdout)} stderr_bytes={len(stderr)}"
            ),
        )
        if proc.returncode != 0:
            detail = err or out or f"exit code {proc.returncode}"
            raise RuntimeError(f"OpenCode CLI failed: {detail[:1200]}")
        if not out:
            raise RuntimeError(f"OpenCode CLI returned no stdout. stderr: {err[:1200]}")
        return out

    @staticmethod
    def _opencode_command_with_trace_flags(parts: List[str]) -> List[str]:
        """Enable OpenCode runtime traces unless the operator already configured them."""
        additions: List[str] = []
        if not any(part == "--print-logs" for part in parts):
            additions.append("--print-logs")
        if not any(part == "--thinking" for part in parts):
            additions.append("--thinking")
        if not any(part == "--log-level" or part.startswith("--log-level=") for part in parts):
            additions.extend(["--log-level", "DEBUG"])

        if not additions:
            return parts

        prompt_index = next(
            (index for index, part in enumerate(parts) if "{prompt}" in part),
            len(parts),
        )
        return [*parts[:prompt_index], *additions, *parts[prompt_index:]]

    @classmethod
    async def _write_opencode_stdin(cls, proc: asyncio.subprocess.Process,
                                    payload: bytes | None) -> None:
        if proc.stdin is None:
            return
        try:
            if payload:
                proc.stdin.write(payload)
                await proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            cls._print_opencode_log("stdin", "OpenCode closed stdin before the prompt was fully written")
        finally:
            proc.stdin.close()
            try:
                await proc.stdin.wait_closed()
            except (BrokenPipeError, ConnectionResetError):
                pass

    @classmethod
    async def _read_opencode_stream(cls, label: str,
                                    stream: asyncio.StreamReader | None,
                                    chunks: List[bytes]) -> None:
        if stream is None:
            return
        while True:
            line = await stream.readline()
            if not line:
                break
            chunks.append(line)
            text = line.decode("utf-8", errors="replace").rstrip()
            cls._print_opencode_log(label, text)

    @classmethod
    def _print_opencode_log(cls, label: str, line: str) -> None:
        safe_line = cls._redact_sensitive_text(line)
        print(f"opencode.{label}: {safe_line}", file=sys.stderr, flush=True)

    @staticmethod
    def _redact_sensitive_text(text: str) -> str:
        redacted = re.sub(r"sk-[A-Za-z0-9_\-]{8,}", "sk-<redacted>", text or "")
        redacted = re.sub(
            r"(?i)(api[_-]?key|token|password|authorization)(['\"]?\s*[:=]\s*['\"]?)[^'\"\s,}]+",
            r"\1\2<redacted>",
            redacted,
        )
        return redacted

    @staticmethod
    def _redacted_command_preview(args: List[str]) -> str:
        preview = []
        for arg in args:
            if len(arg) > 180:
                preview.append(f"{arg[:180]}...[{len(arg)} chars]")
            else:
                preview.append(arg)
        return " ".join(shlex.quote(part) for part in preview)

    @staticmethod
    def _opencode_env() -> Dict[str, str]:
        env = os.environ.copy()
        opencode_bin_dir = (Config.OPENCODE_BIN_DIR or "").strip()
        if opencode_bin_dir:
            env["PATH"] = f"{opencode_bin_dir}:{env.get('PATH', '')}"

        if Config.LITELLM_LLM_API_KEY:
            env.setdefault("LITELLM_LLM_API_KEY", Config.LITELLM_LLM_API_KEY)
            env.setdefault("OPENAI_API_KEY", Config.LITELLM_LLM_API_KEY)
            env.setdefault("JUSPAY_API_KEY", Config.LITELLM_LLM_API_KEY)
        if Config.LITELLM_LLM_API_BASE:
            env.setdefault("LITELLM_LLM_API_BASE", Config.LITELLM_LLM_API_BASE)
            env.setdefault("OPENAI_BASE_URL", Config.LITELLM_LLM_API_BASE)
        if Config.LLM_MODEL:
            env.setdefault("LLM_MODEL", Config.LLM_MODEL)
        return env

    @staticmethod
    def _messages_to_cli_prompt(messages: List[Dict[str, str]]) -> str:
        rendered = []
        for message in messages:
            role = message.get("role", "user").upper()
            content = message.get("content", "")
            rendered.append(f"{role}:\n{content}")
        return "\n\n".join(rendered)

    @staticmethod
    def _clean_opencode_output(raw: str) -> str:
        text = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", raw or "").strip()
        lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("> ") and "·" in stripped:
                continue
            lines.append(line)

        if any(line.strip().startswith("Thinking:") for line in lines):
            answer_start = 0
            for index, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith("Thinking:") or stripped.startswith("Let me "):
                    answer_start = index + 1
            while answer_start < len(lines) and not lines[answer_start].strip():
                answer_start += 1
            lines = lines[answer_start:]

        lines = [
            line for line in lines
            if not line.strip().startswith("Thinking:")
        ]
        return "\n".join(lines).strip()

    def _available_tools(self) -> List[Dict[str, str]]:
        return [
            {
                "name": schema.get("name", name),
                "description": schema.get("description", ""),
            }
            for name, schema in sorted(self.tool_schemas.items())
        ]
