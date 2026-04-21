"""Understanding phase MCP tools."""

import json
from typing import Optional

from ..utils.database import database
from ..utils.llm import llm_client


async def get_api_spec(endpoint_id: str, version: str = "v1") -> dict:
    """Get complete API specification for an endpoint.
    
    Args:
        endpoint_id: Unique endpoint identifier (e.g., 'orders.create')
        version: API version (default: v1)
    
    Returns:
        Complete endpoint specification with fields, schemas, examples
    """
    # Ensure database is connected
    if database._pool is None:
        await database.connect()
    
    spec = await database.get_endpoint_spec(endpoint_id)
    
    if not spec:
        available = await database.list_endpoints()
        available_list = "\n".join([f"  • {e['endpoint_id']} - {e['description']}" for e in available[:10]])
        
        return {
            "content": [{
                "type": "text",
                "text": f"❌ Endpoint '{endpoint_id}' not found.\n\nAvailable endpoints:\n{available_list}\n\nUse search_docs to find the correct endpoint_id."
            }],
            "isError": True
        }
    
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
        required = [f for f in fields if f.get('required')]
        optional = [f for f in fields if not f.get('required')]
        
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
            sections.append(f"- **{f['field_name']}** (`{f['field_type']}`) - {f.get('description', 'No description')}")
    
    # Error responses
    if spec.get('error_responses'):
        sections.append("\n## Error Responses")
        for err in spec['error_responses']:
            sections.append(f"- **{err['error_code']}** (HTTP {err['http_status']}) - {err['description']}")
    
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
        }]
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
        namespace: Specific namespace to search (guides, faqs, error_descriptions, known_issues)
    
    Returns:
        Top matching documentation chunks with similarity scores
    """
    if database._pool is None:
        await database.connect()
    
    # First try semantic search if we have embeddings
    try:
        embeddings = await llm_client.embed([query])
        query_embedding = embeddings[0]
        
        results = await database.search_similar_chunks(
            query_embedding=query_embedding,
            namespace=namespace,
            limit=limit
        )
        
        if results:
            sections = [f"# Search Results for: \"{query}\"\n"]
            
            for i, result in enumerate(results, 1):
                sim_pct = result.get('similarity', 0) * 100
                sections.append(f"\n## Result {i} (Relevance: {sim_pct:.0f}%)")
                sections.append(f"**Source:** {result.get('namespace', 'unknown')} / {result.get('filename', 'doc')}")
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
    
    # Keyword fallback: search endpoints and error codes
    sections = [f"# Keyword Search Results for: \"{query}\"\n"]
    
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
    
    if not endpoints and not error_codes:
        sections.append("\nNo matches found. Try different keywords or check spelling.")
    
    return {
        "content": [{
            "type": "text",
            "text": "\n".join(sections)
        }]
    }
