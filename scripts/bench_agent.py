"""Benchmark: OpenCode subprocess vs litellm in-process tool-calling.

Runs the same question through both backends and measures:
- Cold start (first call)
- Per-call latency
- Total wall time

Requires:
- JUSPAY_API_KEY or LITELLM_LLM_API_KEY env var
- LITELLM_LLM_API_BASE env var
- PostgreSQL running on localhost:5432
- opencode binary on PATH (for the old approach)
"""

import asyncio
import json
import os
import statistics
import sys
import time

# Shared env
API_KEY = os.environ.get("JUSPAY_API_KEY") or os.environ.get("LITELLM_LLM_API_KEY", "")
API_BASE = os.environ.get("LITELLM_LLM_API_BASE", "https://grid.ai.juspay.net/")
MODEL = os.environ.get("LLM_MODEL", "openai/kimi-latest")
DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres@localhost:5432/mcp_product_context"
)

QUESTIONS = [
    "What is the API spec for creating an order?",
    "How do UPI collect payments work?",
    "Explain webhook signature verification",
]


def _set_env():
    os.environ["LITELLM_LLM_API_KEY"] = API_KEY
    os.environ["LITELLM_LLM_API_BASE"] = API_BASE
    os.environ["LLM_MODEL"] = MODEL
    os.environ["DATABASE_URL"] = DB_URL


async def benchmark_litellm():
    """Benchmark the new in-process litellm tool-calling loop."""
    _set_env()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")
    from src.agent.integration_agent import IntegrationAgent
    from src.server.tool_registry import TOOL_REGISTRY, TOOL_SCHEMAS
    from src.utils.database import database

    await database.connect()

    agent = IntegrationAgent(tool_schemas=TOOL_SCHEMAS, tool_registry=TOOL_REGISTRY)
    results = []

    for i, question in enumerate(QUESTIONS):
        start = time.perf_counter()
        result = await agent.answer(question)
        elapsed = time.perf_counter() - start

        tool_calls = [s for s in result["steps"] if s["stage"] == "tool"]
        llm_calls = [s for s in result["steps"] if s["stage"] == "llm"]
        results.append(
            {
                "question": question,
                "total_s": round(elapsed, 2),
                "tool_calls": len(tool_calls),
                "llm_calls": len(llm_calls),
                "answer_chars": len(result.get("answer", "")),
                "steps": len(result["steps"]),
            }
        )

    await database.close()
    return results


async def benchmark_opencode():
    """Benchmark the old OpenCode subprocess approach."""
    _set_env()
    # Force the old config values that the old code expects
    os.environ["AGENT_RESPONSE_BACKEND"] = "opencode"
    os.environ["OPENCODE_BIN_DIR"] = os.path.expanduser("~/.opencode/bin")
    os.environ["OPENCODE_CLI_COMMAND"] = (
        f"opencode run --dir /tmp/merchant_mcp_bench "
        f"--model litellm/kimi-latest --no-replay {{prompt}}"
    )
    os.environ["OPENCODE_CLI_TIMEOUT_SECONDS"] = "600"
    os.environ["OPENCODE_WORKDIR"] = "/tmp/merchant_mcp_bench"
    os.makedirs("/tmp/merchant_mcp_bench", exist_ok=True)

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")
    # Import from the OLD worktree instead
    # We can't import the old code directly from here, so we'll measure
    # the subprocess overhead directly
    from src.utils.config import Config

    Config.OPENCODE_BIN_DIR = os.environ["OPENCODE_BIN_DIR"]
    Config.OPENCODE_CLI_COMMAND = os.environ["OPENCODE_CLI_COMMAND"]
    Config.OPENCODE_CLI_TIMEOUT_SECONDS = 600
    Config.OPENCODE_WORKDIR = "/tmp/merchant_mcp_bench"
    Config.AGENT_RESPONSE_BACKEND = "opencode"

    # Import the OLD IntegrationAgent from the uv-nix-setup worktree
    import importlib
    import importlib.util

    old_path = "/home/nikhil.singh/work/merchant_mcp/uv-nix-setup/src/agent/integration_agent.py"
    spec = importlib.util.spec_from_file_location("old_integration_agent", old_path)
    old_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old_module)

    from src.server.tool_registry import TOOL_SCHEMAS
    from src.utils.database import database

    await database.connect()

    agent = old_module.IntegrationAgent(tool_schemas=TOOL_SCHEMAS)
    results = []

    for i, question in enumerate(QUESTIONS):
        start = time.perf_counter()
        try:
            result = await agent.answer(question)
            elapsed = time.perf_counter() - start
            answer = result.get("answer", "")
            error = None
        except Exception as exc:
            elapsed = time.perf_counter() - start
            answer = ""
            error = str(exc)[:200]

        results.append(
            {
                "question": question,
                "total_s": round(elapsed, 2),
                "answer_chars": len(answer),
                "error": error,
            }
        )

    await database.close()
    return results


def print_comparison(litellm_results, opencode_results):
    print("\n" + "=" * 90)
    print("BENCHMARK: OpenCode subprocess vs litellm in-process tool-calling")
    print("=" * 90)
    print(f"Model: {MODEL}")
    print(f"Proxy: {API_BASE}")
    print(f"Questions: {len(QUESTIONS)}")
    print()

    # Per-question comparison
    print(f"{'Question':<45} {'OpenCode (s)':>13} {'litellm (s)':>13} {'Speedup':>8}")
    print("-" * 90)

    for i, q in enumerate(QUESTIONS):
        q_short = q[:42] + "..." if len(q) > 42 else q
        oc_time = opencode_results[i]["total_s"]
        ll_time = litellm_results[i]["total_s"]
        speedup = f"{oc_time / ll_time:.1f}x" if ll_time > 0 else "N/A"
        oc_err = " (ERR)" if opencode_results[i].get("error") else ""
        print(
            f"  {q_short:<43} {oc_time:>10.2f}{oc_err:>3} {ll_time:>13.2f} {speedup:>8}"
        )

    # Averages
    oc_times = [r["total_s"] for r in opencode_results if not r.get("error")]
    ll_times = [r["total_s"] for r in litellm_results]

    print("-" * 90)
    if oc_times and ll_times:
        oc_avg = statistics.mean(oc_times)
        ll_avg = statistics.mean(ll_times)
        print(
            f"  {'Average':<43} {oc_avg:>13.2f} {ll_avg:>13.2f} {oc_avg / ll_avg:>7.1f}x"
        )

    if oc_times:
        oc_min = min(oc_times)
        oc_max = max(oc_times)
        print(f"  {'Min':<43} {oc_min:>13.2f}")
        print(f"  {'Max':<43} {oc_max:>13.2f}")

    print(f"\n  litellm avg: {statistics.mean(ll_times):.2f}s")
    print(f"  litellm min: {min(ll_times):.2f}s")
    print(f"  litellm max: {max(ll_times):.2f}s")

    # Tool call counts
    print(f"\n  litellm tool calls per question:")
    for r in litellm_results:
        print(
            f"    {r['question'][:40]}: {r['tool_calls']} tool calls, {r['llm_calls']} LLM calls"
        )

    # Errors
    errors = [r for r in opencode_results if r.get("error")]
    if errors:
        print(f"\n  OpenCode errors:")
        for r in errors:
            print(f"    {r['question'][:40]}: {r['error']}")

    print("=" * 90)


async def main():
    if not API_KEY:
        print("ERROR: Set JUSPAY_API_KEY or LITELLM_LLM_API_KEY")
        sys.exit(1)

    print("Benchmarking litellm (new)...")
    ll_results = await benchmark_litellm()

    print("Benchmarking OpenCode (old)...")
    oc_results = await benchmark_opencode()

    print_comparison(ll_results, oc_results)


if __name__ == "__main__":
    asyncio.run(main())
