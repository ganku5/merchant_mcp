"""Deterministic ingestion for generated server-to-server API markdown docs."""

from __future__ import annotations

import hashlib
import json
import re
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..tools.api_specs_v2_tools import insert_api_spec_v2
from ..utils.database import database


API_DOC_PREFIX = "server-to-server-apis/"
CALLBACK_DOC_PREFIX = "docs/newton-callbacks/"
DEFAULT_SOURCE_NAME = "s2s_api_docs"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _clean_cell(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^`|`$", "", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    return value.strip()


def _strip_heading_name(value: str) -> str:
    return re.sub(r"\s+API Integration Guide$", "", value.strip())


def _section(text: str, heading: str, level: int = 2) -> str:
    marker = "#" * level
    pattern = re.compile(
        rf"^{re.escape(marker)}\s+{re.escape(heading)}\s*$"
        rf"(?P<body>.*?)(?=^{re.escape(marker)}\s+|\Z)",
        re.M | re.S,
    )
    match = pattern.search(text)
    return match.group("body").strip() if match else ""


def _first_heading(text: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", text, re.M)
    return match.group(1).strip() if match else ""


def _source_endpoint(text: str) -> Tuple[str, str]:
    match = re.search(r"Source endpoint:\s*`([A-Z]+)\s+([^`]+)`", text)
    if not match:
        return "POST", "/"
    return match.group(1), match.group(2)


def _source_callback_type(text: str) -> str:
    match = re.search(r"(?:Source callback type|Callback type):\s*`([^`]+)`", text)
    return match.group(1).strip() if match else ""


def _endpoint_id(method: str, path: str) -> str:
    path_part = re.sub(r"^/api/\{apiVersion\}/?", "", path).strip("/")
    segments = [_slug(part) for part in path_part.split("/") if part]
    return ".".join(["newton", "s2s", method.lower(), *segments])


def _callback_endpoint_id(callback_type: str, fallback_path: str) -> str:
    value = callback_type or Path(fallback_path).stem
    return ".".join(["newton", "callbacks", "post", _slug(value)])


def _parse_markdown_table(
    lines: List[str], start: int
) -> Tuple[List[Dict[str, str]], int]:
    table_lines = []
    index = start
    while index < len(lines) and lines[index].lstrip().startswith("|"):
        table_lines.append(lines[index].strip())
        index += 1

    if len(table_lines) < 2:
        return [], index

    headers = [_clean_cell(cell) for cell in table_lines[0].strip("|").split("|")]
    rows = []
    for line in table_lines[2:]:
        values = [_clean_cell(cell) for cell in line.strip("|").split("|")]
        if len(values) < len(headers):
            values.extend([""] * (len(headers) - len(values)))
        rows.append({headers[i]: values[i] for i in range(len(headers))})
    return rows, index


def _tables_with_context(text: str) -> Iterable[Tuple[str, List[Dict[str, str]]]]:
    lines = text.splitlines()
    current_heading = ""
    index = 0
    while index < len(lines):
        heading = re.match(r"^(#{3,5})\s+(.+?)\s*$", lines[index])
        if heading:
            current_heading = _clean_cell(heading.group(2))
        if lines[index].lstrip().startswith("|"):
            rows, next_index = _parse_markdown_table(lines, index)
            if rows:
                yield current_heading, rows
            index = next_index
            continue
        index += 1


def _requirement(value: str) -> str:
    lowered = value.lower()
    if "required when selected" in lowered:
        return "conditional"
    if lowered in {"yes", "required", "true", "always present"} or lowered.startswith(
        "required"
    ):
        return "mandatory"
    if "conditional" in lowered or "yes for" in lowered:
        return "conditional"
    return "optional"


def _is_required(value: str) -> bool:
    return _requirement(value) == "mandatory"


def _field_type(value: str) -> str:
    normalized = value.lower().strip()
    if "array" in normalized:
        return "array"
    if "object" in normalized:
        return "object"
    if "boolean" in normalized:
        return "boolean"
    if "integer" in normalized or "number" in normalized:
        return "number"
    if "enum" in normalized:
        return "string"
    if not normalized:
        return "string"
    return normalized.split()[0].replace("/", "_")[:30]


def _enum_values(row: Dict[str, str]) -> List[str]:
    description = " ".join(row.values())
    values = re.findall(r"`([^`]+)`", description)
    return [value for value in values if value and len(value) <= 80]


def _field_from_row(
    row: Dict[str, str], context: str, order: int, parent_path: str = ""
) -> Optional[Dict[str, Any]]:
    name = row.get("Field") or row.get("Name") or row.get("Header")
    if not name:
        return None

    required_text = (
        row.get("Required") or row.get("Presence") or row.get("Always present") or "No"
    )
    requirement = _requirement(required_text)
    default_value = row.get("Default / omitted behavior") or row.get("Default") or None
    condition = required_text if requirement == "conditional" else None
    constraints: Dict[str, Any] = {}
    enum_values = _enum_values(row)
    if enum_values:
        constraints["enum"] = enum_values

    return {
        "field_name": name,
        "field_type": _field_type(row.get("Type", "")),
        "description": row.get("Description", ""),
        "requirement": requirement,
        "condition_description": condition,
        "constraints": constraints,
        "default_value": default_value,
        "display_order": order,
        "parent_path": parent_path,
        "context": context,
    }


def _parent_from_heading(heading: str) -> str:
    value = heading.strip("`").strip()
    if value.endswith("[]"):
        return f"{value[:-2]}[*]"
    if value in {"Field Reference", "Response Field Reference"}:
        return ""
    if " " in value or not value:
        return ""
    return value


def _json_block_after(text: str, heading: str) -> Optional[Any]:
    marker = re.search(rf"^###\s+{re.escape(heading)}\s*$", text, re.M)
    if not marker:
        return None
    block = re.search(r"```json\s*(.*?)```", text[marker.end() :], re.S)
    if not block:
        return None
    try:
        return json.loads(block.group(1).strip())
    except json.JSONDecodeError:
        return None


def _first_json_block(text: str) -> Optional[Any]:
    block = re.search(r"```json\s*(.*?)```", text, re.S)
    if not block:
        return None
    try:
        return json.loads(block.group(1).strip())
    except json.JSONDecodeError:
        return None


def _http_block_after(text: str, heading: str) -> Optional[str]:
    marker = re.search(rf"^###\s+{re.escape(heading)}\s*$", text, re.M)
    if not marker:
        return None
    block = re.search(r"```http\s*(.*?)```", text[marker.end() :], re.S)
    return block.group(1).strip() if block else None


def _chunk_text(text: str, chunk_size: int = 1200, overlap: int = 180) -> List[str]:
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            split_at = max(text.rfind("\n\n", start, end), text.rfind(". ", start, end))
            if split_at > start + chunk_size // 2:
                end = split_at + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return [chunk for chunk in chunks if chunk]


async def _embed_batch(
    texts: List[str], batch_size: int = 32
) -> List[Optional[List[float]]]:
    from ..utils.llm import llm_client

    total = len(texts)
    print(f"    Vectorizing {total} text chunk(s) via embedding model...")
    embeddings: List[Optional[List[float]]] = []
    for index in range(0, total, batch_size):
        batch = texts[index : index + batch_size]
        batch_num = index // batch_size + 1
        total_batches = (total + batch_size - 1) // batch_size
        t0 = time.time()
        result = await llm_client.embed(batch)
        ms = int((time.time() - t0) * 1000)
        dims = len(result[0]) if result else 0
        print(
            f"      Batch {batch_num}/{total_batches}: {len(batch)} texts -> {dims}d vectors in {ms}ms"
        )
        embeddings.extend(result)
    return embeddings


def parse_api_markdown(relative_path: str, content: str) -> Dict[str, Any]:
    """Parse one generated API markdown file into the v2 API spec shape."""
    method, path = _source_endpoint(content)
    title = _strip_heading_name(_first_heading(content))
    overview = _section(content, "Overview")
    business_use_case = _section(content, "Business Use Case")
    request_section = _section(content, "Request")
    response_section = _section(content, "Response")

    headers = {"request": [], "response": []}
    for _heading, rows in _tables_with_context(_section(content, "Endpoint")):
        if not rows:
            continue
        columns = set(rows[0].keys())
        if "Header" not in columns:
            continue
        for row in rows:
            if "Required" in columns:
                required = _is_required(row.get("Required", "No"))
                description = row.get("Description", "")
            else:
                required = "optional" not in row.get("Value", "").lower()
                description = row.get("Value", "")
            headers["request"].append(
                {
                    "name": row.get("Header"),
                    "required": required,
                    "description": description,
                    "value_template": row.get("Value"),
                    "conditional_when": row.get("Description")
                    if _requirement(row.get("Required", "")) == "conditional"
                    else None,
                }
            )

    request_fields = []
    order = 0
    for heading, rows in _tables_with_context(request_section):
        if not rows:
            continue
        columns = set(rows[0].keys())
        if "Field" not in columns or "Type" not in columns:
            continue
        parent_path = _parent_from_heading(heading)
        for row in rows:
            field = _field_from_row(row, "request", order, parent_path)
            if field:
                request_fields.append(field)
                order += 1

    response_fields = []
    order = 0
    for heading, rows in _tables_with_context(response_section):
        if not rows:
            continue
        columns = set(rows[0].keys())
        if "Field" not in columns or "Type" not in columns:
            continue
        parent_path = _parent_from_heading(heading)
        for row in rows:
            field = _field_from_row(row, "response", order, parent_path)
            if field:
                response_fields.append(field)
                order += 1

    request_body = _json_block_after(request_section, "Required Minimum")
    raw_http = _http_block_after(request_section, "Required Minimum")
    samples = []
    if request_body is not None or raw_http:
        samples.append(
            {
                "sample_name": "Required Minimum",
                "description": "Minimum request shape from the generated guide.",
                "scenario": "required_minimum",
                "request": {
                    "headers": {},
                    "query_params": {},
                    "path_params": {},
                    "body": request_body or {},
                    "raw": raw_http,
                },
                "response": {},
            }
        )

    source_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    doc_id = f"{DEFAULT_SOURCE_NAME}__{_slug(Path(relative_path).stem)}"

    return {
        "endpoint_id": _endpoint_id(method, path),
        "method": method,
        "path": path,
        "api_version": "latest",
        "summary": title,
        "description": overview,
        "business_use_case": business_use_case,
        "documentation_url": relative_path,
        "headers": headers,
        "request_fields": request_fields,
        "response_fields": response_fields,
        "samples": samples,
        "conditions": [],
        "source_doc_id": doc_id,
        "source_file": relative_path,
        "source_hash": source_hash,
        "spec_data": {
            "overview": overview,
            "integration_flow": _section(content, "Integration Flow"),
            "source_file": relative_path,
        },
    }


def parse_callback_markdown(relative_path: str, content: str) -> Dict[str, Any]:
    """Parse one generated callback markdown file into the v2 API spec shape."""
    callback_type = _source_callback_type(content)
    title = _strip_heading_name(_first_heading(content))
    overview = _section(content, "Overview")
    business_use_case = _section(content, "Business Use Case")
    when_sent = _section(content, "When Newton Sends It")
    delivery = _section(content, "Delivery")
    request_body_section = _section(content, "Request Body")
    field_reference = _section(content, "Field Reference")
    response_section = _section(content, "Merchant Response")

    delivery_props = {}
    for _heading, rows in _tables_with_context(delivery):
        for row in rows:
            prop = row.get("Property")
            if prop:
                delivery_props[prop] = row.get("Value", "")

    request_fields = []
    order = 0
    for heading, rows in _tables_with_context(field_reference):
        if not rows:
            continue
        columns = set(rows[0].keys())
        if "Field" not in columns or "Type" not in columns:
            continue
        parent_path = _parent_from_heading(heading)
        for row in rows:
            field = _field_from_row(row, "request", order, parent_path)
            if field:
                request_fields.append(field)
                order += 1

    request_body = _first_json_block(request_body_section)
    headers = {
        "request": [
            {
                "name": "Content-Type",
                "required": True,
                "description": "Callback request content type.",
                "value_template": "application/json",
                "example_value": "application/json",
            },
            {
                "name": "X-Merchant-Payload-Signature",
                "required": False,
                "description": "Signature header when configured for the merchant callback.",
                "value_template": "<signature when configured>",
                "conditional_when": "Present when callback signing is enabled for the merchant.",
            },
        ],
        "response": [],
    }

    callback_path = f"/callbacks/{callback_type or _slug(Path(relative_path).stem)}"
    description = overview
    business_context = "\n\n".join(
        part for part in [business_use_case, response_section] if part
    )
    source_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    doc_id = f"{DEFAULT_SOURCE_NAME}__{_slug(Path(relative_path).stem)}"

    samples = []
    if request_body is not None:
        samples.append(
            {
                "sample_name": "Callback Payload",
                "description": "Decrypted business payload example from the generated callback guide.",
                "scenario": "callback_payload",
                "request": {
                    "headers": {
                        "Content-Type": "application/json",
                        "X-Merchant-Payload-Signature": "<signature when configured>",
                    },
                    "query_params": {},
                    "path_params": {},
                    "body": request_body,
                },
                "response": {
                    "status_code": 200,
                    "headers": {},
                    "body": {},
                },
            }
        )

    return {
        "endpoint_id": _callback_endpoint_id(callback_type, relative_path),
        "method": "POST",
        "path": callback_path,
        "api_version": "latest",
        "summary": title,
        "description": description,
        "business_use_case": business_context or business_use_case,
        "when_newton_sends_it": when_sent,
        "documentation_url": relative_path,
        "headers": headers,
        "request_fields": request_fields,
        "response_fields": [],
        "samples": samples,
        "conditions": [],
        "source_doc_id": doc_id,
        "source_file": relative_path,
        "source_hash": source_hash,
        "spec_data": {
            "doc_type": "callback",
            "callback_type": callback_type,
            "category": delivery_props.get("Category"),
            "status": delivery_props.get("Status"),
            "payload_type": delivery_props.get("Payload type"),
            "source_builder": delivery_props.get("Source builder"),
            "delivery": delivery_props,
            "request_body_notes": request_body_section,
            "merchant_response": response_section,
            "source_file": relative_path,
        },
    }


def read_docs_zip(zip_path: str) -> Tuple[Dict[str, str], str, str]:
    """Read generated markdown files from a documentation zip."""
    docs: Dict[str, str] = {}
    shared_conventions = ""
    doc_family = "api"
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        if any(name.startswith(CALLBACK_DOC_PREFIX) for name in names):
            prefix = CALLBACK_DOC_PREFIX
            doc_family = "callback"
        else:
            prefix = API_DOC_PREFIX

        for name in names:
            if not name.startswith(prefix) or not name.endswith(".md"):
                continue
            content = archive.read(name).decode("utf-8")
            relative = name[len(prefix) :]
            if relative == "_shared-conventions.md":
                shared_conventions = content
            elif relative != "_index.md":
                docs[relative] = content
    return docs, shared_conventions, doc_family


async def ensure_api_specs_v2_ingestion_schema() -> None:
    """Add ingestion metadata columns when an older v2 schema is already present."""
    async with database.pool.acquire() as conn:
        await conn.execute(
            "ALTER TABLE api_specs_v2 ADD COLUMN IF NOT EXISTS business_use_case TEXT"
        )
        await conn.execute(
            "ALTER TABLE api_specs_v2 ADD COLUMN IF NOT EXISTS business_use_case_embedding JSONB"
        )
        await conn.execute(
            "ALTER TABLE api_specs_v2 ADD COLUMN IF NOT EXISTS when_newton_sends_it TEXT"
        )
        await conn.execute(
            "ALTER TABLE api_specs_v2 ADD COLUMN IF NOT EXISTS source_doc_id TEXT"
        )
        await conn.execute(
            "ALTER TABLE api_specs_v2 ADD COLUMN IF NOT EXISTS source_file TEXT"
        )
        await conn.execute(
            "ALTER TABLE api_specs_v2 ADD COLUMN IF NOT EXISTS source_hash TEXT"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_api_specs_source_doc ON api_specs_v2(source_doc_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_api_specs_source_file ON api_specs_v2(source_file)"
        )


async def _replace_chunks(
    doc_id: str,
    chunks: List[str],
    namespace: str,
    embeddings: List[Optional[List[float]]],
) -> None:
    async with database.pool.acquire() as conn:
        await conn.execute("DELETE FROM text_chunks WHERE doc_id = $1", doc_id)
    for index, chunk in enumerate(chunks):
        await database.insert_text_chunk(
            doc_id, index, chunk, embeddings[index], namespace
        )


async def _existing_api_spec_ids(endpoint_ids: List[str]) -> set[str]:
    if not endpoint_ids:
        return set()
    async with database.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT endpoint_id FROM api_specs_v2 WHERE endpoint_id = ANY($1::text[])",
            endpoint_ids,
        )
    return {row["endpoint_id"] for row in rows}


async def _endpoint_spec_exists(endpoint_id: str) -> bool:
    async with database.pool.acquire() as conn:
        return bool(
            await conn.fetchval(
                "SELECT 1 FROM endpoint_specs WHERE endpoint_id = $1",
                endpoint_id,
            )
        )


async def _insert_legacy_endpoint(
    spec: Dict[str, Any], update_existing_only: bool = False
) -> bool:
    if update_existing_only and not await _endpoint_spec_exists(spec["endpoint_id"]):
        return False

    request_schema = {"fields": spec.get("request_fields", [])}
    response_schema = {"fields": spec.get("response_fields", [])}
    spec_data = {
        "method": spec["method"],
        "path": spec["path"],
        "description": spec.get("description"),
        "business_use_case": spec.get("business_use_case"),
        "when_newton_sends_it": spec.get("when_newton_sends_it"),
        **spec.get("spec_data", {}),
    }
    await database.insert_endpoint_spec(
        spec["endpoint_id"],
        spec["method"],
        spec["path"],
        spec.get("description") or spec.get("summary") or "",
        "s2s",
        request_schema,
        response_schema,
        [],
        spec_data,
        is_ground_truth=True,
        source_doc_id=spec.get("source_doc_id"),
    )
    return True


async def ingest_docs_zip(
    zip_path: str,
    source_name: str = DEFAULT_SOURCE_NAME,
    skip_embeddings: bool = False,
    dry_run: bool = False,
) -> dict:
    """Ingest generated API markdown docs into documents, chunks, and API spec tables."""
    print(f"\n  [INGEST] Step 1: Reading zip {zip_path}")
    t_total = time.time()
    docs, shared_conventions, doc_family = read_docs_zip(zip_path)
    print(
        f"    Found {len(docs)} doc(s), family={doc_family}, conventions={'yes' if shared_conventions else 'no'}"
    )

    if doc_family == "callback" and source_name == DEFAULT_SOURCE_NAME:
        source_name = "callback_api_docs"

    print(f"\n  [INGEST] Step 2: Parsing markdown (regex, no LLM)")
    t_parse = time.time()
    parser = parse_callback_markdown if doc_family == "callback" else parse_api_markdown
    parsed_items = [
        (path, content, parser(path, content)) for path, content in sorted(docs.items())
    ]
    parse_ms = int((time.time() - t_parse) * 1000)
    for path, _, spec in parsed_items:
        fields_count = len(spec.get("request_fields", [])) + len(
            spec.get("response_fields", [])
        )
        print(
            f"    Parsed {path}: endpoint={spec.get('endpoint_id', '?')}, method={spec.get('method', '?')}, path={spec.get('path', '?')}, fields={fields_count}"
        )
    print(f"    Parsed {len(parsed_items)} doc(s) in {parse_ms}ms")

    if source_name != DEFAULT_SOURCE_NAME:
        for _, _, spec in parsed_items:
            spec["source_doc_id"] = spec["source_doc_id"].replace(
                DEFAULT_SOURCE_NAME, source_name, 1
            )

    if dry_run:
        specs = [spec for _, _, spec in parsed_items]
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Dry run parsed {len(specs)} API docs from {zip_path}.\n"
                        f"Document family: {doc_family}\n"
                        f"First endpoint: {specs[0]['endpoint_id'] if specs else 'none'}\n"
                        f"Business use cases detected: {sum(1 for spec in specs if spec.get('business_use_case'))}"
                    ),
                }
            ],
            "isError": False,
        }

    print(f"\n  [INGEST] Step 3: Ensuring DB schema exists")
    await ensure_api_specs_v2_ingestion_schema()

    skipped_missing_specs: List[str] = []
    if doc_family == "callback":
        existing_ids = await _existing_api_spec_ids(
            [spec["endpoint_id"] for _, _, spec in parsed_items]
        )
        ingest_items = []
        for path, content, spec in parsed_items:
            if spec["endpoint_id"] in existing_ids:
                ingest_items.append((path, content, spec))
            else:
                skipped_missing_specs.append(spec["endpoint_id"])
    else:
        ingest_items = parsed_items

    total_chunks = 0
    docs_namespace = source_name
    conventions_namespace = (
        "s2s_api_conventions" if doc_family == "api" else f"{source_name}_conventions"
    )

    if shared_conventions:
        print(f"\n  [INGEST] Step 4a: Ingesting shared conventions")
        doc_id = f"{source_name}__shared_conventions"
        await database.insert_document(
            doc_id, "_shared-conventions.md", shared_conventions, source_type="markdown"
        )
        chunks = _chunk_text(shared_conventions)
        print(f"    Chunked into {len(chunks)} piece(s)")
        embeddings = (
            [None] * len(chunks) if skip_embeddings else await _embed_batch(chunks)
        )
        await _replace_chunks(doc_id, chunks, conventions_namespace, embeddings)
        print(f"    Stored {len(chunks)} chunk(s) with embeddings in DB")
        total_chunks += len(chunks)

    print(
        f"\n  [INGEST] Step 4b: Vectorizing business use cases ({len(ingest_items)} doc(s))"
    )
    business_texts = [
        "\n\n".join(
            part
            for part in [
                spec.get("business_use_case"),
                spec.get("when_newton_sends_it"),
                spec.get("description"),
                spec.get("summary"),
            ]
            if part
        )
        for _, _, spec in ingest_items
    ]
    business_embeddings = (
        [None] * len(ingest_items)
        if skip_embeddings
        else await _embed_batch(business_texts)
    )

    print(
        f"\n  [INGEST] Step 5: Inserting into DB (documents, chunks, api_specs, fields, headers)"
    )
    legacy_updates = 0
    legacy_skipped = 0
    for index, (relative_path, content, spec) in enumerate(ingest_items):
        doc_id = spec["source_doc_id"]
        endpoint_id = spec.get("endpoint_id", "?")
        print(f"    [{index + 1}/{len(ingest_items)}] {endpoint_id}")

        spec["business_use_case_embedding"] = business_embeddings[index]

        await database.insert_document(
            doc_id, relative_path, content, source_type="markdown"
        )
        chunks = _chunk_text(content)
        print(f"      Document stored, chunking into {len(chunks)} piece(s)...")
        embeddings = (
            [None] * len(chunks) if skip_embeddings else await _embed_batch(chunks)
        )
        await _replace_chunks(doc_id, chunks, docs_namespace, embeddings)
        total_chunks += len(chunks)
        print(f"      Chunks + embeddings stored in DB")

        await insert_api_spec_v2(spec)
        fields_count = len(spec.get("request_fields", [])) + len(
            spec.get("response_fields", [])
        )
        headers_count = len(spec.get("headers", {}).get("request", [])) + len(
            spec.get("headers", {}).get("response", [])
        )
        print(f"      api_specs_v2: {fields_count} fields, {headers_count} headers")

        if await _insert_legacy_endpoint(
            spec, update_existing_only=(doc_family == "callback")
        ):
            legacy_updates += 1
            print(f"      Legacy endpoint_specs: updated")
        else:
            legacy_skipped += 1
            print(f"      Legacy endpoint_specs: skipped")

    total_ms = int((time.time() - t_total) * 1000)
    print(f"\n  [INGEST] Done in {total_ms}ms")
    print(f"    Total chunks: {total_chunks}")
    print(
        f"    Business embeddings: {'skipped' if skip_embeddings else len(ingest_items)}"
    )
    print(f"    Legacy updates: {legacy_updates}, skipped: {legacy_skipped}")

    return {
        "content": [
            {
                "type": "text",
                "text": (
                    f"Ingested {len(ingest_items)} API docs from {zip_path}.\n"
                    f"Document family: {doc_family}\n"
                    f"Documents/chunks namespace: {docs_namespace}\n"
                    f"Text chunks inserted: {total_chunks}\n"
                    f"Business-use-case embeddings: {'skipped' if skip_embeddings else len(ingest_items)}\n"
                    f"Legacy endpoint records updated: {legacy_updates}\n"
                    f"Legacy endpoint records skipped: {legacy_skipped}\n"
                    f"Callback specs skipped because no existing api_specs_v2 row matched: {len(skipped_missing_specs)}"
                ),
            }
        ],
        "isError": False,
    }
