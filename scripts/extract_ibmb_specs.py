#!/usr/bin/env python3
"""Extract IBMB API specifications from PDF content with proper parsing."""

import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.database import database


def parse_parameter_table(text):
    """Parse parameter table from PDF text."""
    fields = []

    # Pattern: SNo Parameter Description Data Type Type Length Regex
    # Lines look like: 1 requestId A unique id... Alphanumeric M 1-40 UUID...

    lines = text.split("\n")
    current_field = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check if line starts with a number (SNo column)
        match = re.match(
            r"^(\d+)\s+(\S+)\s+(.+?)\s+(Alphanumeric|Numeric|Boolean|Array|Object|ENUM)\s+(M|O)\s*(.*)$",
            line,
        )

        if match:
            sno, param, desc, dtype, req_type, rest = match.groups()

            # Clean up description
            desc = desc.strip()

            # Map data types
            type_mapping = {
                "Alphanumeric": "string",
                "Numeric": "number",
                "Boolean": "boolean",
                "Array": "array",
                "Object": "object",
                "ENUM": "string",
            }

            field = {
                "field_name": param.strip(),
                "field_type": type_mapping.get(dtype, "string"),
                "required": req_type == "M",
                "description": desc,
                "json_path": f"$..{param.strip()}",
                "constraints": {},
            }

            # Parse length constraint
            length_match = re.search(r"(\d+)(?:-(\d+))?", rest)
            if length_match:
                min_len = int(length_match.group(1))
                max_len = int(length_match.group(2)) if length_match.group(2) else None
                field["constraints"]["min_length"] = min_len
                if max_len:
                    field["constraints"]["max_length"] = max_len

            fields.append(field)

    return fields


def extract_api_section(content, api_marker, end_markers):
    """Extract API section between marker and end."""
    idx = content.find(api_marker)
    if idx < 0:
        return None

    # Find end
    end_idx = len(content)
    for marker in end_markers:
        marker_idx = content.find(marker, idx + len(api_marker))
        if marker_idx > 0 and marker_idx < end_idx:
            end_idx = marker_idx

    return content[idx:end_idx]


async def extract_all_apis():
    await database.connect()

    async with database.pool.acquire() as conn:
        # Get PDF content
        doc = await conn.fetchrow(
            "SELECT content FROM documents WHERE doc_id = 'ibmb_axis_api_specs'"
        )
        if not doc or not doc["content"]:
            print("No PDF content found")
            return

        content = doc["content"]

        print("=" * 70)
        print("EXTRACTING IBMB API SPECIFICATIONS")
        print("=" * 70)

        # Define API sections to extract
        apis = [
            {
                "name": "SDK Fetch API",
                "endpoint_id": "ibmb.axis.sdk.fetch",
                "method": "POST",
                "path": "/api/sdk/v1/fetch",
                "markers": ["Endpoint URL: {{host}}/api/sdk/v1/fetch", "SDK Auth API"],
                "description": "Fetch decrypted transaction details from NBBL server",
            },
            {
                "name": "SDK Auth API",
                "endpoint_id": "ibmb.axis.sdk.auth",
                "method": "POST",
                "path": "/api/sdk/v1/auth",
                "markers": ["Endpoint URL: {{host}}/api/sdk/v1/auth", "SDK Pay API"],
                "description": "Authenticate and authorize transaction",
            },
            {
                "name": "SDK Pay API",
                "endpoint_id": "ibmb.axis.sdk.pay",
                "method": "POST",
                "path": "/api/sdk/v1/pay",
                "markers": ["Endpoint URL: {{host}}/api/sdk/v1/pay", "SDK Status API"],
                "description": "Process payment transaction",
            },
            {
                "name": "SDK Status API",
                "endpoint_id": "ibmb.axis.sdk.status",
                "method": "POST",
                "path": "/api/sdk/v1/status",
                "markers": [
                    "Endpoint URL: {{host}}/api/sdk/v1/status",
                    "3. Web Redirection",
                ],
                "description": "Check transaction status",
            },
            {
                "name": "Web Fetch API",
                "endpoint_id": "ibmb.axis.web.fetch",
                "method": "POST",
                "path": "/api/web/v1/fetch",
                "markers": ["Endpoint URL: {{host}}/api/web/v1/fetch", "Web Pay API"],
                "description": "Fetch transaction details (Web Flow)",
            },
            {
                "name": "Web Pay API",
                "endpoint_id": "ibmb.axis.web.pay",
                "method": "POST",
                "path": "/api/web/v1/pay",
                "markers": ["Endpoint URL: {{host}}/api/web/v1/pay", "Web Status API"],
                "description": "Process payment (Web Flow)",
            },
            {
                "name": "Web Status API",
                "endpoint_id": "ibmb.axis.web.status",
                "method": "POST",
                "path": "/api/web/v1/status",
                "markers": [
                    "Endpoint URL: {{host}}/api/web/v1/status",
                    "4. API Error Codes",
                ],
                "description": "Check status (Web Flow)",
            },
        ]

        extracted = []

        for api in apis:
            print(f"\n--- Extracting {api['name']} ---")

            section = extract_api_section(
                content, api["markers"][0], api["markers"][1:]
            )

            if not section:
                print(f"  ⚠️ Section not found")
                continue

            # Extract request parameters
            req_start = section.find("Request Parameters")
            resp_start = section.find("Response Parameters")

            req_fields = []
            resp_fields = []

            if req_start > 0 and resp_start > 0:
                req_section = section[req_start:resp_start]
                req_fields = parse_parameter_table(req_section)
                print(f"  ✅ Found {len(req_fields)} request fields")

            if resp_start > 0:
                resp_section = section[resp_start : resp_start + 3000]
                resp_fields = parse_parameter_table(resp_section)
                print(f"  ✅ Found {len(resp_fields)} response fields")

            api_spec = {
                "endpoint_id": api["endpoint_id"],
                "method": api["method"],
                "path": api["path"],
                "description": api["description"],
                "auth_type": "api_key_with_signature",
                "request_schema": {"fields": req_fields},
                "response_schema": {"fields": resp_fields},
                "error_responses": [
                    {
                        "error_code": "ERR001",
                        "http_status": 400,
                        "description": "Invalid request parameters",
                    },
                    {
                        "error_code": "ERR002",
                        "http_status": 401,
                        "description": "Authentication failed",
                    },
                    {
                        "error_code": "ERR003",
                        "http_status": 500,
                        "description": "Internal server error",
                    },
                ],
                "spec_data": {
                    "source": "axis_ibmb_pdf",
                    "flow_type": "sdk" if "sdk" in api["endpoint_id"] else "web",
                },
            }

            extracted.append(api_spec)

            # Store in database
            try:
                await conn.execute(
                    """
                    INSERT INTO endpoint_specs 
                    (endpoint_id, method, path, description, auth_type, 
                     request_schema, response_schema, error_responses, 
                     spec_data, is_ground_truth, source_doc_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (endpoint_id) DO UPDATE SET
                        method = EXCLUDED.method,
                        path = EXCLUDED.path,
                        description = EXCLUDED.description,
                        request_schema = EXCLUDED.request_schema,
                        response_schema = EXCLUDED.response_schema,
                        spec_data = EXCLUDED.spec_data
                """,
                    api_spec["endpoint_id"],
                    api_spec["method"],
                    api_spec["path"],
                    api_spec["description"],
                    api_spec["auth_type"],
                    json.dumps(api_spec["request_schema"]),
                    json.dumps(api_spec["response_schema"]),
                    json.dumps(api_spec["error_responses"]),
                    json.dumps(api_spec["spec_data"]),
                    False,
                    "ibmb_axis_api_specs",
                )
                print(f"  ✅ Stored: {api['endpoint_id']}")
            except Exception as e:
                print(f"  ❌ Failed: {e}")

        print(f"\n=== SUMMARY ===")
        print(f"Extracted {len(extracted)} APIs")

        # Show stored endpoints
        eps = await conn.fetch("""
            SELECT endpoint_id, method, path, 
                   jsonb_array_length(request_schema->'fields') as req_fields,
                   jsonb_array_length(response_schema->'fields') as resp_fields
            FROM endpoint_specs 
            WHERE endpoint_id LIKE 'ibmb%'
            ORDER BY endpoint_id
        """)

        print(f"\nStored Endpoints ({len(eps)}):")
        for e in eps:
            print(f"  • {e['endpoint_id']}: {e['method']} {e['path']}")
            print(
                f"    Request: {e['req_fields']} fields, Response: {e['resp_fields']} fields"
            )

    await database.close()
    print("\n✅ Extraction complete!")


if __name__ == "__main__":
    asyncio.run(extract_all_apis())
