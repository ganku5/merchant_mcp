"""Unit tests for the IntegrationAgent litellm tool-calling loop.

Mocks litellm.acompletion so no external LLM proxy or DB is needed.
Run: uv run pytest tests/test_integration_agent.py -v
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.agent.integration_agent import (
    AGENT_RULES,
    IntegrationAgent,
    _mcp_schemas_to_litellm_tools,
)
from src.server.tool_registry import TOOL_SCHEMAS


def _make_tool_call(name, arguments, call_id="call_1"):
    return type(
        "TC",
        (),
        {
            "id": call_id,
            "function": type(
                "F",
                (),
                {"name": name, "arguments": json.dumps(arguments)},
            )(),
        },
    )


def _make_message(content=None, tool_calls=None):
    msg = type(
        "M",
        (),
        {"content": content, "tool_calls": tool_calls},
    )()
    msg.model_dump = lambda exclude_none=False: {
        "role": "assistant",
        "content": content,
        **({"tool_calls": [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in tool_calls]} if tool_calls else {}),
    }
    return msg


def _make_response(message):
    return type("R", (), {"choices": [type("C", (), {"message": message})()]})


async def _fake_tool_handler(endpoint_id, **kwargs):
    """Returns a realistic MCP-shaped tool result."""
    return {
        "content": [
            {
                "type": "text",
                "text": f"API spec for {endpoint_id}: POST /v1/orders/create with fields order_id, amount, currency.",
            }
        ],
        "isError": False,
    }


@pytest.fixture
def agent():
    return IntegrationAgent(
        tool_schemas=TOOL_SCHEMAS,
        tool_registry={"get_api_spec": _fake_tool_handler},
    )


@pytest.mark.asyncio
async def test_empty_question_returns_error(agent):
    result = await agent.answer("")
    assert result["intent"] == "empty"
    assert "enter an integration question" in result["answer"].lower()
    assert result["steps"][0]["status"] == "error"


@pytest.mark.asyncio
async def test_tool_calling_loop_happy_path(agent):
    """LLM calls a tool, then produces a final answer."""
    tool_call = _make_tool_call("get_api_spec", {"endpoint_id": "ibmb.merchant.order.create"})
    responses = [
        _make_response(_make_message(tool_calls=[tool_call])),
        _make_response(_make_message(content="To create an order, POST to /v1/orders/create with order_id, amount, and currency.")),
    ]
    call_count = 0

    async def fake_completion(**kwargs):
        nonlocal call_count
        call_count += 1
        return responses[call_count - 1]

    with patch("src.agent.integration_agent.litellm.acompletion", new=AsyncMock(side_effect=fake_completion)):
        result = await agent.answer("How do I create an order?")

    stages = [s["stage"] for s in result["steps"]]
    assert "classify" in stages
    assert "tool" in stages
    assert "llm" in stages
    assert "answer" in stages

    tool_steps = [s for s in result["steps"] if s["stage"] == "tool"]
    assert len(tool_steps) == 1
    assert tool_steps[0]["tool"] == "get_api_spec"
    assert tool_steps[0]["arguments"]["endpoint_id"] == "ibmb.merchant.order.create"
    assert tool_steps[0]["status"] == "done"
    assert "API spec for" in tool_steps[0]["response_preview"]

    assert "create an order" in result["answer"].lower()
    assert call_count == 2
    assert result["rules"] == AGENT_RULES
    assert "available_tools" in result


@pytest.mark.asyncio
async def test_tool_exception_fed_back_to_llm(agent):
    """When a tool raises, the error is fed back to the LLM as a tool result."""
    async def failing_tool(**kwargs):
        raise RuntimeError("DB connection refused")

    agent.tool_registry = {"get_api_spec": failing_tool}

    tool_call = _make_tool_call("get_api_spec", {"endpoint_id": "test"})
    responses = [
        _make_response(_make_message(tool_calls=[tool_call])),
        _make_response(_make_message(content="The tool failed but I can still help.")),
    ]
    call_count = 0

    async def fake_completion(**kwargs):
        nonlocal call_count
        call_count += 1
        return responses[call_count - 1]

    with patch("src.agent.integration_agent.litellm.acompletion", new=AsyncMock(side_effect=fake_completion)):
        result = await agent.answer("What is the API spec for orders?")

    tool_steps = [s for s in result["steps"] if s["stage"] == "tool"]
    assert len(tool_steps) == 1
    assert tool_steps[0]["status"] == "error"
    assert "DB connection refused" in tool_steps[0]["detail"]
    assert "tool failed" in result["answer"].lower()


@pytest.mark.asyncio
async def test_llm_call_failure_returns_error(agent):
    """When litellm.acompletion itself raises, the agent returns a clear error."""
    async def failing_llm(**kwargs):
        raise RuntimeError("LiteLLM proxy unreachable")

    with patch("src.agent.integration_agent.litellm.acompletion", new=AsyncMock(side_effect=failing_llm)):
        result = await agent.answer("test question")

    assert "LLM call failed" in result["answer"]
    llm_steps = [s for s in result["steps"] if s["stage"] == "llm"]
    assert any(s["status"] == "error" for s in llm_steps)


@pytest.mark.asyncio
async def test_max_iteration_cap(agent):
    """If the LLM always returns tool_calls, the loop hits the cap instead of looping forever."""
    tool_call = _make_tool_call("get_api_spec", {"endpoint_id": "test"})
    response = _make_response(_make_message(tool_calls=[tool_call]))

    async def always_tool(**kwargs):
        return response

    with patch("src.agent.integration_agent.litellm.acompletion", new=AsyncMock(side_effect=always_tool)):
        result = await agent.answer("test")

    error_steps = [s for s in result["steps"] if s["status"] == "error"]
    assert any("max" in s["detail"].lower() or "iteration" in s["detail"].lower() for s in error_steps)
    assert "maximum number of tool" in result["answer"].lower()


@pytest.mark.asyncio
async def test_unknown_tool_returns_error_in_result(agent):
    """If the LLM calls a tool not in the registry, it gets a 'not found' message back."""
    tool_call = _make_tool_call("nonexistent_tool", {})
    responses = [
        _make_response(_make_message(tool_calls=[tool_call])),
        _make_response(_make_message(content="That tool doesn't exist, but here's what I know.")),
    ]
    call_count = 0

    async def fake_completion(**kwargs):
        nonlocal call_count
        call_count += 1
        return responses[call_count - 1]

    with patch("src.agent.integration_agent.litellm.acompletion", new=AsyncMock(side_effect=fake_completion)):
        result = await agent.answer("test")

    tool_steps = [s for s in result["steps"] if s["stage"] == "tool"]
    assert len(tool_steps) == 1
    assert tool_steps[0]["status"] == "error"
    assert "not found" in tool_steps[0]["detail"].lower()


def test_schema_conversion():
    """MCP tool schemas convert to litellm/OpenAI function-calling format correctly."""
    tools = _mcp_schemas_to_litellm_tools(TOOL_SCHEMAS)
    assert len(tools) == len(TOOL_SCHEMAS)
    for tool in tools:
        assert tool["type"] == "function"
        assert "name" in tool["function"]
        assert "description" in tool["function"]
        assert "parameters" in tool["function"]
        assert tool["function"]["parameters"]["type"] == "object"
