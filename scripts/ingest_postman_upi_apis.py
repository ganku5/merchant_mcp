import asyncio
import json
import re
from pathlib import Path
from typing import Any, Dict, List

from src.utils.database import database

COLLECTION_PATH = Path("api_specs/upi/postman_upi_collection_for_merchant_mcp.json")
SOURCE_DOC_ID = "upi_postman_collection"


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "api"


def extract_url(raw_url: Any) -> str:
    if isinstance(raw_url, str):
        return raw_url

    if isinstance(raw_url, dict):
        if raw_url.get("raw"):
            return raw_url["raw"]

        path = raw_url.get("path") or []
        if isinstance(path, list):
            return "/" + "/".join(str(p) for p in path)

    return ""


def extract_headers(headers: List[Dict[str, Any]]) -> Dict[str, Any]:
    fields = []

    for header in headers or []:
        key = header.get("key")
        if not key:
            continue

        fields.append(
            {
                "field_name": key,
                "field_type": "string",
                "required": not header.get("disabled", False),
                "description": header.get("description") or "",
                "example": header.get("value") or "",
            }
        )

    return {"headers": fields}


def extract_body(body: Dict[str, Any]) -> Dict[str, Any]:
    if not body:
        return {}

    mode = body.get("mode")
    raw = body.get("raw")

    if mode == "raw" and raw:
        try:
            parsed = json.loads(raw)
            return {
                "body_type": "json",
                "sample": parsed,
            }
        except Exception:
            return {
                "body_type": "raw",
                "sample": raw,
            }

    if mode == "formdata":
        fields = []
        for item in body.get("formdata") or []:
            fields.append(
                {
                    "field_name": item.get("key"),
                    "field_type": item.get("type") or "string",
                    "required": not item.get("disabled", False),
                    "example": item.get("value") or "",
                }
            )
        return {"body_type": "formdata", "fields": fields}

    if mode == "urlencoded":
        fields = []
        for item in body.get("urlencoded") or []:
            fields.append(
                {
                    "field_name": item.get("key"),
                    "field_type": "string",
                    "required": not item.get("disabled", False),
                    "example": item.get("value") or "",
                }
            )
        return {"body_type": "urlencoded", "fields": fields}

    return {"body_type": mode or "unknown"}


def flatten_items(items: List[Dict[str, Any]], folders: List[str] = None):
    folders = folders or []

    for item in items or []:
        if "item" in item:
            yield from flatten_items(item["item"], folders + [item.get("name", "")])
            continue

        request = item.get("request")
        if not request:
            continue

        yield folders, item


async def main():
    if not COLLECTION_PATH.exists():
        raise SystemExit(f"Collection not found: {COLLECTION_PATH}")

    data = json.loads(COLLECTION_PATH.read_text())
    collection_name = data.get("info", {}).get("name", "upi_collection")

    await database.connect()

    await database.insert_document(
        doc_id=SOURCE_DOC_ID,
        filename=str(COLLECTION_PATH),
        content=json.dumps(data),
        num_pages=0,
        source_type="postman_collection",
    )

    inserted = 0
    endpoint_id_counts = {}

    async with database.pool.acquire() as conn:
           await conn.execute(
            """
            DELETE FROM endpoint_specs
            WHERE source_doc_id = $1
            """,
            SOURCE_DOC_ID,
        )

    for folders, item in flatten_items(data.get("item", [])):
        request = item["request"]

        method = request.get("method", "GET")
        path = extract_url(request.get("url"))
        name = item.get("name", "api")

        folder_part = ".".join(slugify(folder) for folder in folders if folder)
        endpoint_name = slugify(name)

        if folder_part:
            endpoint_id = f"upi.{folder_part}.{endpoint_name}"
        else:
            endpoint_id = f"upi.{endpoint_name}"

        endpoint_id_counts[endpoint_id] = endpoint_id_counts.get(endpoint_id, 0) + 1
        if endpoint_id_counts[endpoint_id] > 1:
            endpoint_id = f"{endpoint_id}_{endpoint_id_counts[endpoint_id]}"

        headers_schema = extract_headers(request.get("header") or [])
        body_schema = extract_body(request.get("body") or {})

        request_schema = {
            "headers": headers_schema,
            "body": body_schema,
            "postman_name": name,
            "postman_folders": folders,
        }

        response_schema = {}
        responses = item.get("response") or []

        if responses:
            response_schema["examples"] = [
                {
                    "name": response.get("name"),
                    "status": response.get("status"),
                    "code": response.get("code"),
                    "body": response.get("body"),
                }
                for response in responses[:3]
            ]

        description = request.get("description") or f"{method} {path}"

        await database.insert_endpoint_spec(
            endpoint_id=endpoint_id,
            method=method,
            path=path,
            description=description,
            auth_type="postman_collection",
            request_schema=request_schema,
            response_schema=response_schema,
            error_responses=[],
            spec_data={
                "collection": collection_name,
                "folders": folders,
                "postman_name": name,
                "raw_request": request,
            },
            source_doc_id=SOURCE_DOC_ID,
        )

        inserted += 1

    await database.close()
    print("inserted_upi_endpoints:", inserted)


if __name__ == "__main__":
    asyncio.run(main())