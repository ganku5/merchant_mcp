"""Understanding phase tools."""

import json

from ..utils.db_full import db_full as db
from ..utils.llm import llm_client


async def get_api_spec(endpoint_id: str, version: str = "v1") -> dict:
    """Get complete API specification for an endpoint."""
    spec = await db.get_endpoint_spec(endpoint_id)
    
    if not spec:
        return {
            "content": [{
                "type": "text",
                "text": f"Endpoint '{endpoint_id}' not found in knowledge store."
            }],
            "isError": True
        }
    
    # Format response
    formatted = json.dumps(spec, indent=2)
    
    return {
        "content": [{
            "type": "text",
            "text": f"## API Specification: {endpoint_id}\n\n```json\n{formatted}\n```"
        }]
    }


async def get_integration_guide(use_case: str, language: str = "python") -> dict:
    """Get step-by-step integration guide for a use case."""
    # Query flows from database
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT flow_data FROM integration_flows WHERE flow_data->>'use_case' = $1",
            use_case
        )
    
    if rows:
        flow = json.loads(rows[0]['flow_data'])
        steps_text = "\n".join([
            f"{i+1}. **{step.get('name', f'Step {i+1}')}**\n   {step.get('description', '')}"
            for i, step in enumerate(flow.get('steps', []))
        ])
        
        return {
            "content": [{
                "type": "text",
                "text": f"## Integration Guide: {use_case}\n\n{steps_text}\n\n_Language preference: {language}_"
            }]
        }
    
    # Fallback: generate guide using LLM
    prompt = f"""Create a step-by-step integration guide for implementing {use_case} with a payment API.
Include: 1) Prerequisites, 2) API calls in order, 3) Error handling, 4) Webhook handling."""
    
    guide = await llm_client.chat([
        {"role": "user", "content": prompt}
    ])
    
    return {
        "content": [{
            "type": "text",
            "text": f"## Integration Guide: {use_case}\n\n{guide}"
        }]
    }


async def get_flow(flow_type: str, scenario: str = None) -> dict:
    """Get ordered API call sequence for a flow type."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT flow_data FROM integration_flows WHERE flow_id = $1",
            flow_type
        )
    
    if row:
        flow = json.loads(row['flow_data'])
        
        steps = []
        for i, step in enumerate(flow.get('steps', []), 1):
            step_info = f"**Step {i}:** {step.get('name', 'Unknown')}\n"
            step_info += f"- Description: {step.get('description', 'N/A')}\n"
            if step.get('endpoint_id'):
                step_info += f"- Endpoint: `{step['endpoint_id']}`\n"
            if step.get('decision_point'):
                step_info += f"- Decision: {step['decision_point']}\n"
            steps.append(step_info)
        
        return {
            "content": [{
                "type": "text",
                "text": f"## Flow: {flow_type}\n\n" + "\n".join(steps)
            }]
        }
    
    return {
        "content": [{
            "type": "text",
            "text": f"Flow '{flow_type}' not found. Available flows can be listed with search_docs."
        }],
        "isError": True
    }


async def search_docs(query: str, limit: int = 5, namespace: str = None) -> dict:
    """Search documentation using semantic search."""
    # Generate embedding for query
    embeddings = await llm_client.embed([query])
    query_embedding = embeddings[0]
    
    # Search in all namespaces or specific one
    namespaces_to_search = [namespace] if namespace else ['guides', 'faqs', 'error_descriptions', 'known_issues', 'pdf_IBMB Acquiring - Merchant Integration', 'pdf_[Axis] IBMB Bank Server API Specifications']
    
    all_results = []
    for ns in namespaces_to_search:
        try:
            results = await db.search_embeddings(ns, query_embedding, limit=limit)
            for r in results:
                r['namespace'] = ns
                all_results.append(r)
        except Exception:
            continue
    
    # Sort by similarity and take top results
    all_results.sort(key=lambda x: x['similarity'], reverse=True)
    all_results = all_results[:limit]
    
    if not all_results:
        return {
            "content": [{
                "type": "text",
                "text": f"No results found for query: '{query}'"
            }]
        }
    
    # Format results
    result_texts = []
    for i, result in enumerate(all_results, 1):
        text = f"**Result {i}** (similarity: {result['similarity']:.3f})\n"
        text += f"Source: {result.get('namespace', 'unknown')}\n"
        text += f"```\n{result['chunk_text'][:500]}...\n```"
        result_texts.append(text)
    
    return {
        "content": [{
            "type": "text",
            "text": f"## Search Results for: '{query}'\n\n" + "\n\n".join(result_texts)
        }]
    }
