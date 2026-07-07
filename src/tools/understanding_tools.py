"""Understanding phase MCP tools."""

import json
from typing import Optional

from ..utils.database import database
from ..utils.llm import llm_client


def _md_cell(value) -> str:
    """Escape a value for use inside a markdown table cell."""
    text = "" if value is None else str(value)
    return text.replace("|", "&#124;").replace("\n", "<br>").strip()


async def get_api_spec(endpoint_id: str, version: Optional[str] = None, include_samples: bool = True) -> dict:
    """Get complete API specification for an endpoint.

    Args:
        endpoint_id: Unique endpoint identifier (e.g., 'ibmb.merchant.transaction.init')
        version: Optional API version. When omitted, the latest available version is used.
        include_samples: Whether to include request/response samples (v2 APIs only)

    Returns:
        Complete endpoint specification with fields, schemas, headers, and examples
    """
    # Ensure database is connected
    if database._pool is None:
        await database.connect()

    conn = database.pool

    # First try v2 API specs (richer format with headers, samples, conditions)
    try:
        async with conn.acquire() as db_conn:
            if version:
                spec_row = await db_conn.fetchrow("""
                    SELECT * FROM api_specs_v2
                    WHERE endpoint_id = $1 AND api_version = $2
                """, endpoint_id, version)
            else:
                spec_row = None

            if not spec_row:
                spec_row = await db_conn.fetchrow("""
                    SELECT * FROM api_specs_v2
                    WHERE endpoint_id = $1
                    ORDER BY api_version DESC
                    LIMIT 1
                """, endpoint_id)

            if spec_row:
                return await _get_api_spec_v2(db_conn, spec_row, include_samples)
    except Exception:
        # V2 tables might not exist, fall back to legacy
        pass

    # Fall back to legacy endpoint_specs table
    spec = await database.get_endpoint_spec(endpoint_id)

    if not spec:
        # Try to list available endpoints from both tables
        available = await database.list_endpoints()
        available_list = "\n".join([f"  • {e['endpoint_id']} - {e['description']}" for e in available[:10]])

        # Also check v2 APIs
        try:
            async with conn.acquire() as db_conn:
                v2_specs = await db_conn.fetch("SELECT endpoint_id FROM api_specs_v2 LIMIT 10")
                if v2_specs:
                    v2_list = "\n".join([f"  • {s['endpoint_id']}" for s in v2_specs])
                    available_list = v2_list + "\n" + available_list
        except:
            pass

        return {
            "content": [{
                "type": "text",
                "text": f"❌ Endpoint '{endpoint_id}' not found.\n\nAvailable endpoints:\n{available_list}\n\nUse search_docs to find the correct endpoint_id."
            }],
            "isError": True
        }

    # Return legacy format response
    return await _get_api_spec_legacy(spec, endpoint_id, version or spec.get("version", "latest"))


async def _get_api_spec_v2(db_conn, spec_row, include_samples: bool) -> dict:
    """Get API spec from v2 format (richer data)."""
    import json

    spec_data = dict(spec_row)
    spec_id = spec_row['spec_id']
    endpoint_id = spec_row['endpoint_id']

    # Build sections
    sections = [
        f"# API Specification: {endpoint_id}",
        f"\n**Method:** {spec_row['method']}",
        f"**Path:** {spec_row['path']}",
        f"**Version:** {spec_row['api_version']}",
    ]

    if spec_row['summary']:
        sections.append(f"**Summary:** {spec_row['summary']}")

    sections.append(f"\n## Description\n{spec_row['description'] or 'No description'}")

    if spec_data.get('business_use_case'):
        sections.append(f"\n## Business Use Case\n{spec_data['business_use_case']}")

    if spec_data.get('when_newton_sends_it'):
        sections.append(f"\n## When Newton Sends It\n{spec_data['when_newton_sends_it']}")

    # Get headers
    headers = await db_conn.fetch("""
        SELECT * FROM api_headers WHERE spec_id = $1 ORDER BY header_type, name
    """, spec_id)

    if headers:
        sections.append("\n## Headers")
        current_type = None
        header_rows = []

        def flush_header_table():
            nonlocal header_rows
            if not header_rows:
                return
            sections.extend([
                "| Header | Required | Description | Example | Pattern / Condition |",
                "| --- | --- | --- | --- | --- |",
                *header_rows,
            ])
            header_rows = []

        for h in headers:
            if h['header_type'] != current_type:
                flush_header_table()
                current_type = h['header_type']
                sections.append(f"\n### {current_type.title()} Headers")

            condition = h['conditional_when'] or ""
            pattern_condition = "<br>".join(
                item for item in [
                    f"Pattern: `{h['pattern']}`" if h['pattern'] else "",
                    f"Condition: {condition}" if condition else "",
                ] if item
            )
            header_rows.append(
                "| "
                + " | ".join([
                    _md_cell(h['name']),
                    "Yes" if h['required'] else "No",
                    _md_cell(h['description'] or ""),
                    f"`{_md_cell(h['example_value'])}`" if h['example_value'] else "",
                    _md_cell(pattern_condition),
                ])
                + " |"
            )
        flush_header_table()

    # Get fields (build tree)
    async def get_fields(context: str):
        rows = await db_conn.fetch("""
            SELECT * FROM api_fields
            WHERE spec_id = $1 AND context = $2
            ORDER BY parent_path, display_order
        """, spec_id, context)
        return [dict(r) for r in rows]

    def format_field_table(fields):
        result = [
            "| Field | Type | Required | Description | Constraints / Condition | Example |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for f in fields:
            req = f.get('requirement', 'optional')
            required = {"mandatory": "Yes", "optional": "No", "conditional": "Conditional"}.get(req, req)

            field_type = f.get('field_type', 'unknown')
            if f.get('subtype'):
                field_type += f"<{f['subtype']}>"

            constraints = f.get('constraints', {})
            if isinstance(constraints, str):
                try:
                    constraints = json.loads(constraints)
                except:
                    constraints = {}

            cons_list = []
            if req == 'conditional' and f.get('condition_description'):
                cons_list.append(f"Condition: {f['condition_description']}")
            if constraints:
                if constraints.get('pattern'): cons_list.append(f"Pattern: `{constraints['pattern']}`")
                if constraints.get('minLength'): cons_list.append(f"Min: {constraints['minLength']}")
                if constraints.get('maxLength'): cons_list.append(f"Max: {constraints['maxLength']}")
                if constraints.get('enum'): cons_list.append(f"Enum: {constraints['enum']}")

            field_name = f.get('full_path') or f.get('field_name') or ""
            example = f.get('example_value')
            if isinstance(example, (dict, list)):
                example = json.dumps(example)
            elif example is None:
                example = ""

            result.append(
                "| "
                + " | ".join([
                    _md_cell(field_name),
                    _md_cell(field_type),
                    _md_cell(required),
                    _md_cell(f.get('description') or ""),
                    _md_cell("<br>".join(cons_list)),
                    f"`{_md_cell(str(example))}`" if example != "" else "",
                ])
                + " |"
            )

        return result

    # Request schema
    request_fields = await get_fields('request')
    if request_fields:
        sections.append("\n## Request Fields")
        sections.extend(format_field_table(request_fields))

    # Response schema
    response_fields = await get_fields('response')
    if response_fields:
        sections.append("\n## Response Fields")
        sections.extend(format_field_table(response_fields))

    # Get conditions
    conditions = await db_conn.fetch("""
        SELECT * FROM api_conditions WHERE spec_id = $1
    """, spec_id)

    if conditions:
        sections.append("\n## Conditional Logic")
        for c in conditions:
            sections.append(f"\n### {c['condition_name']}")
            sections.append(f"- Expression: `{c['expression']}`")
            if c['description']:
                sections.append(f"- Description: {c['description']}")

    # Rate limits
    rate_limit_raw = spec_row.get('rate_limit', '{}')
    try:
        rate_limit = rate_limit_raw if isinstance(rate_limit_raw, dict) else json.loads(rate_limit_raw)
    except:
        rate_limit = {}
    if rate_limit and isinstance(rate_limit, dict):
        sections.append("\n## Rate Limits")
        for key, value in rate_limit.items():
            sections.append(f"- {key.replace('_', ' ').title()}: {value}")

    # Get samples if requested
    if include_samples:
        samples = await db_conn.fetch("""
            SELECT * FROM api_samples WHERE spec_id = $1
        """, spec_id)

        if samples:
            sections.append("\n## Examples")
            for s in samples:
                sections.append(f"\n### {s['sample_name']}")
                if s['description']:
                    sections.append(f"*{s['description']}*")

                req_raw = s.get('request', '{}')
                try:
                    req = req_raw if isinstance(req_raw, dict) else json.loads(req_raw)
                except:
                    req = {}
                if req and req.get('body'):
                    sections.append(f"\n**Request:**")
                    if req.get('headers'):
                        sections.append("Headers:")
                        for hk, hv in req['headers'].items():
                            sections.append(f"  {hk}: {hv}")
                    sections.append(f"```json\n{json.dumps(req['body'], indent=2)}\n```")

                resp_raw = s.get('response', '{}')
                try:
                    resp = resp_raw if isinstance(resp_raw, dict) else json.loads(resp_raw)
                except:
                    resp = {}
                if resp and resp.get('body'):
                    sections.append(f"\n**Response ({resp.get('status_code', 200)}):**")
                    sections.append(f"```json\n{json.dumps(resp['body'], indent=2)}\n```")

                if s.get('curl_command'):
                    sections.append(f"\n**cURL:**")
                    sections.append(f"```bash\n{s['curl_command']}\n```")

    return {
        "content": [{
            "type": "text",
            "text": "\n".join(sections)
        }],
        "isError": False
    }


async def _get_api_spec_legacy(spec, endpoint_id: str, version: str) -> dict:
    """Get API spec from legacy format."""
    # Build comprehensive response
    sections = [
        f"# API Specification: {endpoint_id}",
        f"\n**Method:** {spec['method']}",
        f"**Path:** {spec['path']}",
        f"**Version:** {version}",
        f"**Auth:** {spec['auth_type']}",
        f"\n## Description\n{spec['description']}",
    ]

    # Request schema
    if spec.get('request_schema'):
        req = spec['request_schema']
        sections.append("\n## Request Schema")

        fields = req.get('fields', [])
        # Normalize field names (support both 'name'/'type' and 'field_name'/'field_type')
        normalized_fields = []
        for f in fields:
            nf = {
                'field_name': f.get('field_name') or f.get('name', 'unknown'),
                'field_type': f.get('field_type') or f.get('type', 'unknown'),
                'required': f.get('required', False),
                'description': f.get('description', ''),
                'example': f.get('example'),
                'default': f.get('default'),
                'valid_values': f.get('valid_values'),
                'constraints': f.get('constraints', {})
            }
            normalized_fields.append(nf)

        required = [f for f in normalized_fields if f['required']]
        optional = [f for f in normalized_fields if not f['required']]

        if required:
            sections.append("\n### Required Fields")
            for f in required:
                field_desc = f"- **{f['field_name']}** (`{f['field_type']}`)"
                if f.get('example'):
                    field_desc += f" - Example: `{f['example']}`"
                if f.get('description'):
                    field_desc += f"\n  - {f['description']}"
                if f.get('valid_values'):
                    field_desc += f"\n  - Valid values: {f['valid_values']}"
                if f.get('constraints'):
                    cons = f['constraints']
                    constraints = []
                    if cons.get('min_length'): constraints.append(f"min: {cons['min_length']}")
                    if cons.get('max_length'): constraints.append(f"max: {cons['max_length']}")
                    if cons.get('pattern'): constraints.append(f"pattern: {cons['pattern']}")
                    if constraints:
                        field_desc += f"\n  - Constraints: {', '.join(constraints)}"
                sections.append(field_desc)

        if optional:
            sections.append("\n### Optional Fields")
            for f in optional:
                field_desc = f"- **{f['field_name']}** (`{f['field_type']}`)"
                if f.get('default') is not None:
                    field_desc += f" - Default: `{f['default']}`"
                if f.get('description'):
                    field_desc += f"\n  - {f['description']}"
                sections.append(field_desc)

    # Response schema
    if spec.get('response_schema'):
        resp = spec['response_schema']
        sections.append("\n## Response Schema")
        for f in resp.get('fields', []):
            field_name = f.get('field_name') or f.get('name', 'unknown')
            field_type = f.get('field_type') or f.get('type', 'unknown')
            desc = f.get('description', 'No description')
            sections.append(f"- **{field_name}** (`{field_type}`) - {desc}")

    # Error responses
    error_responses = spec.get('error_responses') or spec.get('errors', [])
    if error_responses:
        sections.append("\n## Error Responses")
        for err in error_responses:
            if isinstance(err, dict):
                error_code = err.get('error_code') or err.get('code', 'UNKNOWN')
                http_status = err.get('http_status', err.get('status', 'N/A'))
                desc = err.get('description', err.get('message', 'No description'))
                sections.append(f"- **{error_code}** (HTTP {http_status}) - {desc}")

    # Rate limits
    if spec.get('rate_limit'):
        rl = spec['rate_limit']
        sections.append(f"\n## Rate Limits\n- {rl.get('requests_per_minute', 'N/A')} requests/minute")
        sections.append(f"- Burst allowance: {rl.get('burst_allowance', 'N/A')}")

    # Idempotency
    if spec.get('idempotency'):
        idem = spec['idempotency']
        sections.append(f"\n## Idempotency\n- Required: {idem.get('required', False)}")
        if idem.get('header_name'):
            sections.append(f"- Header: `{idem['header_name']}`")
        if idem.get('behavior'):
            sections.append(f"- Behavior: {idem['behavior']}")

    # Related webhooks
    if spec.get('related_webhooks'):
        sections.append(f"\n## Related Webhooks\n" + ", ".join([f"`{w}`" for w in spec['related_webhooks']]))

    # Sandbox notes
    if spec.get('sandbox_notes'):
        sections.append(f"\n## Sandbox Notes\n{spec['sandbox_notes']}")

    return {
        "content": [{
            "type": "text",
            "text": "\n".join(sections)
        }],
        "isError": False
    }


async def get_integration_guide(use_case: str, language: str = "python") -> dict:
    """Get step-by-step integration guide for a use case.

    Args:
        use_case: Use case type (payment, collect, mandate, refund, subscription)
        language: Preferred programming language

    Returns:
        Integration guide with ordered steps
    """
    if database._pool is None:
        await database.connect()

    # Get flows for this use case
    flows = await database.get_flows_by_use_case(use_case)

    if not flows:
        # List available use cases
        all_flows = await database.list_flows()
        use_cases = list(set(f['use_case'] for f in all_flows))

        return {
            "content": [{
                "type": "text",
                "text": f"❌ No integration guide found for '{use_case}'.\n\nAvailable use cases: {', '.join(use_cases)}"
            }],
            "isError": True
        }

    # Use first flow or find exact match
    flow = flows[0]

    sections = [
        f"# Integration Guide: {flow['name']}",
        f"\n**Use Case:** {flow['use_case']}",
        f"**Description:** {flow['description']}",
        f"**Language:** {language}",
    ]

    if flow.get('prerequisites'):
        sections.append("\n## Prerequisites")
        for prereq in flow['prerequisites']:
            sections.append(f"- {prereq}")

    sections.append("\n## Step-by-Step Flow")

    steps = flow.get('steps', [])
    for i, step in enumerate(steps, 1):
        sections.append(f"\n### Step {i}: {step.get('name', f'Step {i}')}")
        sections.append(f"**Description:** {step.get('description', 'No description')}")

        if step.get('endpoint_id'):
            sections.append(f"**API Endpoint:** `{step['endpoint_id']}`")

        if step.get('required_parameters'):
            sections.append(f"**Required Parameters:** {', '.join(step['required_parameters'])}")

        if step.get('expected_response'):
            sections.append(f"**Expected Response:** {step['expected_response']}")

        if step.get('error_handling'):
            sections.append(f"**Error Handling:** {step['error_handling']}")

        if step.get('decision_point'):
            sections.append(f"**Decision Point:** ⚠️ {step['decision_point']}")

        if step.get('next_steps'):
            sections.append(f"**Next:** {' → '.join(step['next_steps'])}")

    if flow.get('estimated_duration_minutes'):
        sections.append(f"\n---\n⏱️ Estimated Time: {flow['estimated_duration_minutes']} minutes")

    return {
        "content": [{
            "type": "text",
            "text": "\n".join(sections)
        }]
    }


async def get_flow(flow_type: str, scenario: Optional[str] = None) -> dict:
    """Get ordered API call sequence for a flow type.

    Args:
        flow_type: Flow identifier (e.g., 'payment.standard', 'refund.standard')
        scenario: Specific scenario variant

    Returns:
        Ordered API sequence with branching logic
    """
    if database._pool is None:
        await database.connect()

    flow = await database.get_flow(flow_type)

    if not flow:
        available = await database.list_flows()
        available_list = "\n".join([f"  • {f['flow_id']} - {f['name']}" for f in available])

        return {
            "content": [{
                "type": "text",
                "text": f"❌ Flow '{flow_type}' not found.\n\nAvailable flows:\n{available_list}"
            }],
            "isError": True
        }

    sections = [
        f"# Flow: {flow['name']}",
        f"\n**ID:** `{flow['flow_id']}`",
        f"**Use Case:** {flow['use_case']}",
        f"**Description:** {flow['description']}",
    ]

    sections.append("\n## API Sequence")

    steps = flow.get('steps', [])
    for i, step in enumerate(steps, 1):
        icon = "➡️"
        if step.get('decision_point'):
            icon = "🔀"
        elif not step.get('endpoint_id'):
            icon = "⏳"

        line = f"\n{i}. {icon} **{step.get('name', f'Step {i}')}**"
        sections.append(line)

        if step.get('endpoint_id'):
            sections.append(f"   API: `{step['endpoint_id']}`")

        if step.get('decision_point'):
            sections.append(f"   Decision: {step['decision_point']}")

    return {
        "content": [{
            "type": "text",
            "text": "\n".join(sections)
        }]
    }


async def search_docs(query: str, limit: int = 5, namespace: Optional[str] = None) -> dict:
    """Search documentation using semantic search.

    Args:
        query: Natural language search query
        limit: Maximum number of results (default: 5)
        namespace: Specific namespace to search (for NPCI circulars use npci_circulars)

    Returns:
        Top matching documentation chunks with similarity scores
    """
    if database._pool is None:
        await database.connect()

    chunk_results = []
    try:
        chunk_results = await database.search_text_chunks_keyword(query, namespace=namespace, limit=limit)
        for result in chunk_results:
            result["match_type"] = "keyword"
    except Exception:
        chunk_results = []

    # Also try semantic search if we have embeddings, then merge with keyword hits.
    try:
        embeddings = await llm_client.embed([query])
        query_embedding = embeddings[0]

        semantic_results = await database.search_similar_chunks(
            query_embedding=query_embedding,
            namespace=namespace,
            limit=limit
        )
        for result in semantic_results:
            result["match_type"] = "semantic"

        seen = set()
        results = []
        for result in [*chunk_results, *semantic_results]:
            key = (result.get("doc_id"), result.get("chunk_index"))
            if key in seen:
                continue
            seen.add(key)
            results.append(result)
            if len(results) >= limit:
                break

        if results:
            sections = [f"# Search Results for: \"{query}\"\n"]

            for i, result in enumerate(results, 1):
                if result.get("match_type") == "keyword":
                    label = f"Keyword score: {result.get('keyword_score', 0)}"
                else:
                    sim_pct = result.get('similarity', 0) * 100
                    label = f"Relevance: {sim_pct:.0f}%"
                sections.append(f"\n## Result {i} ({label})")
                sections.append(f"**Source:** {result.get('namespace', 'unknown')} / {result.get('filename', 'doc')}")
                sections.append(f"**Document ID:** `{result.get('doc_id', 'unknown')}`")
                sections.append(f"**Chunk:** `{result.get('chunk_index', 'unknown')}`")
                sections.append(f"\n```\n{result['chunk_text'][:800]}...\n```")

            return {
                "content": [{
                    "type": "text",
                    "text": "\n".join(sections)
                }]
            }
    except Exception as e:
        # Fall back to keyword search
        pass

    # Keyword fallback: search existing chunks first, then endpoint and error-code tables.
    sections = [f"# Keyword Search Results for: \"{query}\"\n"]

    if chunk_results:
        sections.append("\n## Matching Document Chunks")
        for i, result in enumerate(chunk_results, 1):
            sections.append(f"\n### Result {i}")
            sections.append(f"**Source:** {result.get('namespace', 'unknown')} / {result.get('filename', 'doc')}")
            sections.append(f"**Document ID:** `{result.get('doc_id', 'unknown')}`")
            sections.append(f"**Chunk:** `{result.get('chunk_index', 'unknown')}`")
            sections.append(f"\n```\n{result['chunk_text'][:800]}...\n```")

    endpoints = await database.search_endpoints(query, limit=5)
    if endpoints:
        sections.append("\n## Matching Endpoints")
        for ep in endpoints:
            sections.append(f"- **{ep['endpoint_id']}** - {ep['method']} {ep['path']}")
            sections.append(f"  {ep.get('description', '')}")

    error_codes = await database.search_error_codes(query, limit=5)
    if error_codes:
        sections.append("\n## Matching Error Codes")
        for err in error_codes:
            sections.append(f"- **{err['error_code']}** ({err['category']}) - {err['message']}")

    if not chunk_results and not endpoints and not error_codes:
        sections.append("\nNo matches found. Try different keywords or check spelling.")

    return {
        "content": [{
            "type": "text",
            "text": "\n".join(sections)
        }]
    }
