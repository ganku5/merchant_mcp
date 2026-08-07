## Benchmark: OpenCode subprocess vs litellm in-process tool-calling

Same 3 questions, same model (`kimi-latest`), same LiteLLM proxy, same PostgreSQL database.

### Results

| Question | OpenCode (old) | litellm (new) | Speedup |
|---|---|---|---|
| What is the API spec for creating an order? | 398.50s | 112.66s | **3.5x** |
| How do UPI collect payments work? | 108.90s | 69.14s | **1.6x** |
| Explain webhook signature verification | 68.45s | 74.83s | 0.9x |
| **Average** | **191.95s** | **85.54s** | **2.2x** |

### Tool call counts (litellm)

| Question | Tool calls | LLM iterations |
|---|---|---|
| What is the API spec for creating an order? | 11 | 7 |
| How do UPI collect payments work? | 9 | 6 |
| Explain webhook signature verification | 4 | 3 |

### Key findings

- **litellm is 2.2x faster on average.** Q1 was 3.5x faster - OpenCode took 6.5 minutes due to subprocess boot (~4s), session/title generation, watcher setup, and its own internal LLM loop.
- **Q3 was slightly slower with litellm** (74.8s vs 68.5s) - but for the wrong reason. OpenCode couldn't find the Merchant MCP tools (logged `MCP server "merchant" does not support resources`), so it answered from general knowledge after 1 LLM call. litellm called 4 real tools before answering, producing a more specific answer.
- **OpenCode never used the Merchant MCP tools in any question.** Its logs show it searched for them, failed, and fell back to general knowledge. The litellm approach called real tools every time (11, 9, and 4 tool calls respectively).

### Why the speedup

- **No subprocess boot**: OpenCode spends ~4s starting up (config loading, plugin init, session creation, watcher setup, title generation LLM call)
- **No stdout parsing**: litellm returns structured `tool_calls` objects; OpenCode required ANSI stripping, "Thinking:" prefix removal, TUI noise filtering
- **No round-trip**: litellm calls tools directly in-process; OpenCode had to connect back to the MCP server over HTTP

### Environment

- Model: `openai/kimi-latest` via LiteLLM proxy
- Database: PostgreSQL with pgvector (localhost)
- Branch: `fix/replace-opencode-with-litellm-tool-calling`
- Benchmark script: `scripts/bench_agent.py`
