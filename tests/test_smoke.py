"""Smoke tests against a running MCP server (or Docker container).

Usage:
    # Against a running server
    MCP_URL=http://localhost:8001 uv run pytest tests/test_smoke.py -v

    # Default URL is http://localhost:8000
    uv run pytest tests/test_smoke.py -v
"""

import os

import httpx
import pytest

URL = os.environ.get("MCP_URL", "http://localhost:8000")


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=URL, timeout=10) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


def test_tools_listed(client):
    r = client.get("/tools")
    assert r.status_code == 200
    tools = r.json()["tools"]
    assert len(tools) > 0, "no tools registered"


def test_tool_call_list_api_specs(client):
    r = client.post(
        "/tools/call",
        json={"name": "list_api_specs", "arguments": {}},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["isError"] is False
    assert "content" in data


def test_sse_endpoint(client):
    with client.stream("GET", "/sse") as r:
        assert r.status_code == 200
        first_event = next(r.iter_lines())
        assert "event: endpoint" in first_event
