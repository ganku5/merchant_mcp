"""Unit tests for WebDocIngester with mocked httpx + litellm.

Run: PYTHONPATH=. uv run pytest tests/test_web_scraper.py -v
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ingestion.web_scraper import WebDocIngester, FILE_DELIMITER


SAMPLE_HTML = """
<html><head><title>Collect Payment API</title></head>
<body>
<h1>Collect Payment API</h1>
<p>POST /api/v1/merchants/transactions/collect</p>
<h2>Overview</h2>
<p>Initiates a UPI collect payment request to a customer's VPA.</p>
<h2>Request Fields</h2>
<table>
<tr><th>Field</th><th>Type</th><th>Required</th><th>Description</th></tr>
<tr><td>amount</td><td>string</td><td>Yes</td><td>Amount in paise</td></tr>
<tr><td>payerVpa</td><td>string</td><td>Yes</td><td>Customer VPA</td></tr>
</table>
<h2>Response</h2>
<pre>{"status":"SUCCESS","txnId":"TXN123"}</pre>
</body></html>
"""


SAMPLE_LLM_OUTPUT = """---FILE: post-api-v1-merchants-transactions-collect.md---
# Collect Payment API Integration Guide

Source endpoint: `POST /api/v1/merchants/transactions/collect`

## Overview

Initiates a UPI collect payment request to a customer's VPA.

## Business Use Case

- Send a collect request to a customer's UPI app
- Customer approves with UPI PIN

## Request

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `amount` | string | Yes | No default. | Amount in paise. |
| `payerVpa` | string | Yes | No default. | Customer VPA. |

### Required Minimum

```json
{
  "amount": "10000",
  "payerVpa": "customer@okhdfcbank"
}
```

## Response

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API status. |
| `txnId` | string | Transaction ID. |

## Error Handling

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid VPA"
}
```
"""


def _mock_httpx_response(html: str):
    resp = AsyncMock()
    resp.text = html
    resp.raise_for_status = MagicMock(return_value=None)
    return resp


def _mock_litellm_response(content: str):
    message = type("M", (), {"content": content})()
    choice = type("C", (), {"message": message})()
    return type("R", (), {"choices": [choice]})


@pytest.fixture
def ingester(tmp_path):
    return WebDocIngester(output_dir=str(tmp_path / "scraped_docs"))


@pytest.mark.asyncio
async def test_scrape_and_convert_happy_path(ingester):
    """URL is fetched, LLM converts to structured markdown, file is written."""
    mock_resp = _mock_httpx_response(SAMPLE_HTML)
    mock_llm = _mock_litellm_response(SAMPLE_LLM_OUTPUT)

    with patch("src.ingestion.web_scraper.httpx.AsyncClient") as mock_client_cls, \
         patch("src.ingestion.web_scraper.litellm.acompletion", new=AsyncMock(return_value=mock_llm)):

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        results = await ingester.scrape_and_convert(["https://docs.example.com/api/collect"])

    assert len(results) == 1
    assert results[0]["status"] == "ok"
    assert results[0]["source_url"] == "https://docs.example.com/api/collect"
    assert len(results[0]["files_written"]) == 1

    md_files = list(ingester.output_dir.glob("*.md"))
    assert len(md_files) == 1
    content = md_files[0].read_text()
    assert "Source endpoint:" in content
    assert "## Request" in content
    assert "## Response" in content

    log_path = ingester.output_dir / "_conversion_log.json"
    assert log_path.exists()
    log = json.loads(log_path.read_text())
    assert log[0]["status"] == "ok"


@pytest.mark.asyncio
async def test_fetch_error_handled(ingester):
    """Network errors are logged and don't crash the batch."""
    with patch("src.ingestion.web_scraper.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client_cls.return_value = mock_client

        results = await ingester.scrape_and_convert(["https://unreachable.example.com"])

    assert results[0]["status"] == "fetch_error"
    assert "Connection refused" in results[0]["reason"]


@pytest.mark.asyncio
async def test_skip_non_api_page(ingester):
    """LLM returns SKIP for non-API pages."""
    mock_resp = _mock_httpx_response("<html><body><h1>Welcome to our blog about payments</h1><p>This is a blog post about payment trends in the industry. It covers various topics but does not document any API endpoint.</p></body></html>")
    mock_llm = _mock_litellm_response("SKIP")

    with patch("src.ingestion.web_scraper.httpx.AsyncClient") as mock_client_cls, \
         patch("src.ingestion.web_scraper.litellm.acompletion", new=AsyncMock(return_value=mock_llm)):

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        results = await ingester.scrape_and_convert(["https://example.com/blog"])

    assert results[0]["status"] == "skipped"
    assert "not API" in results[0]["reason"]
    md_files = list(ingester.output_dir.glob("*.md"))
    assert len(md_files) == 0


@pytest.mark.asyncio
async def test_multi_endpoint_page(ingester):
    """LLM returns multiple files from one page."""
    multi_output = (
        "---FILE: post-api-v1-collect.md---\n# Collect API\n\nSource endpoint: `POST /api/v1/collect`\n\n## Overview\nCollect.\n"
        "\n---FILE: post-api-v1-refund.md---\n# Refund API\n\nSource endpoint: `POST /api/v1/refund`\n\n## Overview\nRefund.\n"
    )
    mock_resp = _mock_httpx_response(SAMPLE_HTML)
    mock_llm = _mock_litellm_response(multi_output)

    with patch("src.ingestion.web_scraper.httpx.AsyncClient") as mock_client_cls, \
         patch("src.ingestion.web_scraper.litellm.acompletion", new=AsyncMock(return_value=mock_llm)):

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        results = await ingester.scrape_and_convert(["https://docs.example.com/api"])

    assert results[0]["status"] == "ok"
    assert len(results[0]["files_written"]) == 2
    md_files = sorted(ingester.output_dir.glob("*.md"))
    assert len(md_files) == 2
    assert "collect" in md_files[0].name
    assert "refund" in md_files[1].name


@pytest.mark.asyncio
async def test_llm_failure_returns_empty(ingester):
    """LLM call failure doesn't crash, returns empty list."""
    mock_resp = _mock_httpx_response(SAMPLE_HTML)

    with patch("src.ingestion.web_scraper.httpx.AsyncClient") as mock_client_cls, \
         patch("src.ingestion.web_scraper.litellm.acompletion", new=AsyncMock(side_effect=Exception("LLM unreachable"))):

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        results = await ingester.scrape_and_convert(["https://docs.example.com/api"])

    assert results[0]["status"] == "skipped"
    assert "LLM" in results[0]["reason"]


def test_parse_llm_output_single_file():
    files = WebDocIngester._parse_llm_output(SAMPLE_LLM_OUTPUT)
    assert len(files) == 1
    assert "collect" in files[0][0]
    assert "Source endpoint" in files[0][1]


def test_parse_llm_output_skip():
    files = WebDocIngester._parse_llm_output("SKIP")
    assert files == []


def test_parse_llm_output_empty():
    files = WebDocIngester._parse_llm_output("")
    assert files == []


def test_parse_llm_output_no_delimiter():
    files = WebDocIngester._parse_llm_output("# Some markdown\n\nNo delimiter.")
    assert len(files) == 1
    assert files[0][0] == "doc"


def test_safe_filename():
    assert WebDocIngester._safe_filename("post-api-v1-collect") == "post-api-v1-collect"
    assert WebDocIngester._safe_filename("file with spaces!") == "file-with-spaces"
    assert WebDocIngester._safe_filename("") == "doc"
    assert WebDocIngester._safe_filename("../etc/passwd") == "etc-passwd"


def test_zip_output(ingester):
    ingester.output_dir.mkdir(parents=True, exist_ok=True)
    (ingester.output_dir / "test1.md").write_text("# Test 1")
    (ingester.output_dir / "test2.md").write_text("# Test 2")

    zip_path = ingester.zip_output()
    assert Path(zip_path).exists()

    import zipfile
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        assert "server-to-server-apis/test1.md" in names
        assert "server-to-server-apis/test2.md" in names
