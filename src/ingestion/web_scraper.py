"""Scrape web docs, convert to structured markdown, feed to the ingestion pipeline."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
import litellm

from ..utils.config import Config


logger = logging.getLogger(__name__)


CONVERSION_PROMPT = """You are a technical documentation converter. You convert arbitrary web documentation into structured API specification markdown.

## Your task

Read the raw markdown scraped from a web page. Identify what API endpoint(s) or callback(s) it documents. For each one, output a single markdown file in the EXACT format shown below. If the page documents multiple endpoints, output multiple files separated by a delimiter. If the page is not API documentation at all, output SKIP.

## Output format for an API endpoint

```markdown
# {Title} API Integration Guide

Source endpoint: `{METHOD} {PATH}`

## Overview

{Description of what the API does}

## Business Use Case

{Bullet points or prose describing when and why to use this API}

## Integration Flow

1. {Numbered steps describing the integration sequence}

## Endpoint

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `Authorization` | `{auth description}` |

## Request

### Required Minimum

```json
{{
  "field1": "value1"
}}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `field1` | string | Yes | No default. | Description. |
| `field2` | string | No | Omitted. | Description. |

## Response

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API processing status. |
| `payload` | object | Response payload. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `field1` | string | Description. |

### Response Examples

```json
{{
  "status": "SUCCESS",
  "payload": {{
    "field1": "value1"
  }}
}}
```

## Error Handling

```json
{{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Description"
}}
```
```

## Output format for a callback/webhook

```markdown
# {Title} Callback Guide

Source callback type: `{callback_type}`

## Overview

{Description}

## Business Use Case

{Context}

## When Newton Sends It

{Trigger conditions}

## Delivery

| Property | Value |
|---|---|
| Category | {category} |
| Status | {status} |
| Payload type | JSON |

## Request Body

{Description}

```json
{{
  "event": "{callback_type}",
  "data": {{}}
}}
```

## Field Reference

| Field | Type | Required | Description |
|---|---|---|---|
| `event` | string | Yes | Event type. |

## Merchant Response

{What the merchant should return}
```

## Rules

1. Extract the HTTP method and path from wherever they appear on the page (URL, code blocks, prose, headings).
2. Map field tables wherever you find them (HTML tables, markdown tables, prose descriptions, JSON examples) into the markdown table format above.
3. If the page has JSON examples, include them in fenced ```json blocks.
4. If the page documents multiple endpoints, output one file per endpoint.
5. If the page is not API/callback documentation (e.g., a landing page, a blog post, a changelog), output only the word: SKIP
6. Do NOT invent fields or endpoints that are not on the page. Only extract what's there.
7. Preserve technical accuracy - field names, types, required status, descriptions must match the source.
8. Use `Yes` or `No` in the Required column. Use `conditional` if the field is conditionally required.

## Output convention

For each file, start with a line:
`---FILE: {filename}.md---`

Then the markdown content.

Then a blank line.

If multiple files, repeat the `---FILE:---` delimiter.

If skipping, output exactly: `SKIP`

## Real example (from the target format)

# CBS Transaction Status API Integration Guide

Source endpoint: `POST /api/{apiVersion}/cbs/transactions/status`

## Overview

CBS Transaction Status is a server-to-server API used by an onboarded CBS or bank-side integration to fetch the latest Newton status for a CBS-backed UPI transaction.

## Business Use Case

CBS Transaction Status helps partners:

- Poll a CBS-backed payout, refund, debit, or credit leg after Newton has initiated processing.
- Reconcile gateway status and CBS status using the same `upiRequestId`.

## Integration Flow

1. Newton creates or updates a CBS transaction during the configured CBS-backed UPI flow.
2. The partner stores the Newton `upiRequestId` and the CBS transaction `type`.
3. The partner calls `cbs/transactions/status` with those values.

## Endpoint

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. |

## Request

### Required Minimum

```json
{{
  "type": "DEBIT",
  "upiRequestId": "CBSTXN123456789"
}}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `type` | string | Yes | No default. | CBS transaction leg. Allowed: `DEBIT`, `CREDIT`. |
| `upiRequestId` | string | Yes | No default. | Newton UPI request id, 1-35 alphanumeric chars. |

## Response

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `amount` | string | Amount formatted with two decimals. |
| `gatewayResponseStatus` | string | Gateway status. |
| `cbsResponseStatus` | string | CBS status. |

### Response Examples

```json
{{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "payload": {{
    "amount": "100.00",
    "gatewayResponseStatus": "PENDING",
    "cbsResponseStatus": "PENDING"
  }}
}}
```

## Error Handling

```json
{{
  "status": "FAILURE",
  "responseCode": "REQUEST_NOT_FOUND",
  "responseMessage": "REQUEST_NOT_FOUND"
}}
```
"""


FILE_DELIMITER = re.compile(r"^---FILE:\s*(.+?)\.md\s*---$", re.M)


class WebDocIngester:
    """Scrape URLs, convert to structured markdown, optionally ingest."""

    def __init__(
        self,
        output_dir: Optional[str] = None,
        model: Optional[str] = None,
        max_crawl_depth: Optional[int] = None,
        max_urls: Optional[int] = None,
    ):
        self.output_dir = Path(output_dir or Config.WEB_SCRAPER_OUTPUT_DIR)
        self.model = model or Config.CONVERSION_LLM_MODEL or Config.LLM_MODEL
        self.max_crawl_depth = (
            max_crawl_depth
            if max_crawl_depth is not None
            else Config.WEB_SCRAPER_MAX_CRAWL_DEPTH
        )
        self.max_urls = (
            max_urls if max_urls is not None else Config.WEB_SCRAPER_MAX_URLS
        )
        if "/" not in self.model and Config.LITELLM_LLM_API_BASE:
            self.model = f"openai/{self.model}"

    async def crawl_and_scrape(self, root_url: str) -> List[Dict[str, Any]]:
        """Crawl from root_url, discover doc pages, then scrape all of them."""
        discovered = await self._discover_urls(root_url)
        if not discovered:
            return [
                {
                    "source_url": root_url,
                    "status": "skipped",
                    "reason": "No doc links found during crawl.",
                }
            ]
        print(f"Discovered {len(discovered)} URLs from {root_url}")
        return await self.scrape_and_convert(discovered)

    async def _discover_urls(self, root_url: str) -> List[str]:
        """Discover doc URLs: try llms.txt first, then BFS crawl."""
        llms_urls = await self._try_llms_txt(root_url)
        if llms_urls:
            print(f"Found llms.txt with {len(llms_urls)} URLs")
            return llms_urls

        return await self._crawl_urls(root_url)

    async def _try_llms_txt(self, root_url: str) -> Optional[List[str]]:
        """Check for llms.txt at common paths, follow sub-llms.txt links, extract .md URLs."""
        from urllib.parse import urljoin, urlparse

        parsed = urlparse(root_url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        candidates = [
            urljoin(root_url, "llms.txt"),
            urljoin(root_url.rstrip("/") + "/", "llms.txt"),
            urljoin(base, "/in/docs/llms.txt"),
            urljoin(base, "/docs/llms.txt"),
        ]

        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            headers={"User-Agent": "MerchantMCP-DocScraper/1.0"},
        ) as client:
            root_llms = None
            for candidate in candidates:
                try:
                    resp = await client.get(candidate)
                    if resp.status_code == 200 and resp.text.strip():
                        root_llms = resp.text
                        print(f"Found llms.txt at {candidate}")
                        break
                except Exception:
                    continue

            if not root_llms:
                return None

            md_urls = re.findall(r"https?://[^\s]+\.md", root_llms)
            sub_llms = re.findall(r"https?://[^\s]+llms\.txt", root_llms)

            for sub in sub_llms[:20]:
                try:
                    resp = await client.get(sub)
                    if resp.status_code == 200 and resp.text.strip():
                        sub_md = re.findall(r"https?://[^\s]+\.md", resp.text)
                        md_urls.extend(sub_md)
                except Exception:
                    continue

            if md_urls:
                seen: set[str] = set()
                deduped: List[str] = []
                for u in md_urls:
                    if u not in seen:
                        seen.add(u)
                        deduped.append(u)
                return deduped[: self.max_urls]

            page_urls = re.findall(r"https?://[^\s]+/docs/[^\s]+", root_llms)
            if page_urls:
                return page_urls[: self.max_urls]

        return None

    async def _crawl_urls(self, root_url: str) -> List[str]:
        """BFS crawl: fetch each page, extract doc-like links."""
        from urllib.parse import urljoin, urlparse

        parsed_root = urlparse(root_url)
        root_domain = parsed_root.netloc

        visited: set[str] = set()
        queue: List[tuple[str, int]] = [(root_url, 0)]
        discovered: List[str] = []

        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": "MerchantMCP-DocScraper/1.0"},
        ) as client:
            while queue and len(discovered) < self.max_urls:
                url, depth = queue.pop(0)
                if url in visited or depth > self.max_crawl_depth:
                    continue
                visited.add(url)

                try:
                    resp = await client.get(url)
                    html = resp.text
                except Exception:
                    continue

                links = re.findall(r'href=["\']([^"\']+)["\']', html)
                for link in links:
                    full_url = urljoin(url, link.split("#")[0].rstrip("/"))
                    if not full_url or full_url in visited:
                        continue

                    parsed = urlparse(full_url)
                    if parsed.netloc != root_domain:
                        continue
                    if "/docs/" not in parsed.path and not full_url.endswith(".md"):
                        continue

                    if full_url not in visited:
                        discovered.append(full_url)
                        queue.append((full_url, depth + 1))

                if url not in discovered:
                    discovered.append(url)

        seen: set[str] = set()
        deduped: List[str] = []
        for u in discovered:
            if u not in seen:
                seen.add(u)
                deduped.append(u)
        return deduped

    async def scrape_and_convert(self, urls: List[str]) -> List[Dict[str, Any]]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        results: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "MerchantMCP-DocScraper/1.0"},
        ) as client:
            for url in urls:
                result = await self._process_url(client, url)
                results.append(result)
                await asyncio.sleep(1)

        log_path = self.output_dir / "_conversion_log.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        return results

    async def _process_url(self, client: httpx.AsyncClient, url: str) -> Dict[str, Any]:
        logger.info("scraping %s", url)
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except Exception as exc:
            logger.error("fetch failed for %s: %s", url, exc)
            return {
                "source_url": url,
                "status": "fetch_error",
                "reason": str(exc)[:200],
            }

        content_type = resp.headers.get("content-type", "")
        if url.endswith(".md") or "text/markdown" in content_type:
            markdown = resp.text
        else:
            markdown = self._html_to_markdown(resp.text, url)
            if self._is_js_spa(markdown):
                logger.info(
                    "detected JS-rendered page, falling back to Playwright for %s", url
                )
                rendered = await self._render_with_playwright(url)
                if rendered:
                    markdown = self._html_to_markdown(rendered, url)

        if not markdown or len(markdown.strip()) < 100:
            return {
                "source_url": url,
                "status": "skipped",
                "reason": "Page too short or empty after conversion.",
            }

        files = await self._llm_convert(markdown, url)
        if not files:
            return {
                "source_url": url,
                "status": "skipped",
                "reason": "LLM determined this page is not API/callback documentation.",
            }

        written = []
        for filename, content in files:
            safe_name = self._safe_filename(filename)
            out_path = self.output_dir / f"{safe_name}.md"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)
            written.append(safe_name + ".md")
            logger.info("wrote %s (%d chars)", out_path.name, len(content))

        return {
            "source_url": url,
            "status": "ok",
            "files_written": written,
            "doc_type": "api_or_callback",
        }

    @staticmethod
    def _is_js_spa(markdown: str) -> bool:
        if not markdown:
            return False
        script_indicators = (
            "createElement",
            "document.",
            "window.",
            "addEventListener",
            ".appendChild(",
            "getElementsByTagName",
            "preconnect",
            "dns-prefetch",
        )
        script_hits = sum(1 for ind in script_indicators if ind in markdown)
        return script_hits >= 4

    @staticmethod
    async def _render_with_playwright(url: str) -> Optional[str]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("playwright not installed; cannot render JS pages")
            return None

        import shutil

        executable = shutil.which("chromium") or shutil.which("chromium-browser")

        try:
            async with async_playwright() as p:
                launch_kwargs = {"headless": True}
                if executable:
                    launch_kwargs["executable_path"] = executable
                browser = await p.chromium.launch(**launch_kwargs)
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(3000)
                html = await page.content()
                await browser.close()
                return html
        except Exception as exc:
            logger.error("playwright render failed for %s: %s", url, exc)
            return None

    @staticmethod
    def _html_to_markdown(html: str, url: str) -> str:
        try:
            from markitdown import MarkItDown

            md = MarkItDown()
            result = md.convert(html)
            text = (
                result.text_content if hasattr(result, "text_content") else str(result)
            )
        except Exception:
            text = re.sub(r"<[^>]+>", "", html)

        text = re.sub(r"\n{3,}", "\n\n", text)
        if not text.startswith(f"Source URL: {url}"):
            text = f"Source URL: {url}\n\n{text}"
        return text.strip()

    async def _llm_convert(self, markdown: str, url: str) -> List[Tuple[str, str]]:
        truncated = markdown[:8000]
        messages = [
            {"role": "system", "content": CONVERSION_PROMPT},
            {
                "role": "user",
                "content": f"Source URL: {url}\n\n--- RAW MARKDOWN ---\n{truncated}",
            },
        ]

        try:
            response = await litellm.acompletion(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=4000,
                api_base=Config.LITELLM_LLM_API_BASE or None,
                api_key=Config.LITELLM_LLM_API_KEY or None,
            )
        except Exception as exc:
            logger.error("LLM conversion failed for %s: %s", url, exc)
            return []

        raw_output = response.choices[0].message.content or ""
        return self._parse_llm_output(raw_output)

    @staticmethod
    def _parse_llm_output(raw: str) -> List[Tuple[str, str]]:
        raw = raw.strip()
        if raw.upper() == "SKIP" or not raw:
            return []

        files: List[Tuple[str, str]] = []
        matches = list(FILE_DELIMITER.finditer(raw))
        if not matches:
            return [("doc", raw)]

        for i, match in enumerate(matches):
            filename = match.group(1)
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
            content = raw[start:end].strip()
            if content:
                files.append((filename, content))

        return files

    @staticmethod
    def _safe_filename(name: str) -> str:
        name = re.sub(r"[^a-zA-Z0-9._-]+", "-", name).strip("-.")
        return name or "doc"

    def zip_output(self) -> str:
        zip_path = str(self.output_dir.parent / f"{self.output_dir.name}.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for md_file in self.output_dir.glob("*.md"):
                zf.write(md_file, f"server-to-server-apis/{md_file.name}")
        return zip_path

    async def ingest(self) -> Dict[str, Any]:
        from .docs_zip_ingester import ingest_docs_zip

        zip_path = self.zip_output()
        return await ingest_docs_zip(zip_path)
