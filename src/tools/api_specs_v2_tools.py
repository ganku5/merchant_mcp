"""API Specs V2 tools for comprehensive API documentation."""

import json
from typing import Dict, List, Optional, Any
from ..utils.database import database


async def insert_api_spec_v2(spec: dict) -> dict:
    """Insert complete API spec with headers, fields, conditions, and samples.
    
    Args:
        spec: Complete API specification JSON following v2 schema
        
    Returns:
        Result with inserted spec_id or error
    """
    if database._pool is None:
        await database.connect()
    
    conn = database.pool
    
    try:
        async with conn.acquire() as db_conn:
            async with db_conn.transaction():
                # Insert main spec
                spec_result = await db_conn.fetchrow("""
                    INSERT INTO api_specs_v2 (
                        endpoint_id, method, path, api_version, description, summary,
                        documentation_url, changelog, rate_limit, idempotency,
                        business_use_case, business_use_case_embedding,
                        source_doc_id, source_file, source_hash
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                    ON CONFLICT (endpoint_id) DO UPDATE SET
                        method = EXCLUDED.method,
                        path = EXCLUDED.path,
                        api_version = EXCLUDED.api_version,
                        description = EXCLUDED.description,
                        summary = EXCLUDED.summary,
                        documentation_url = EXCLUDED.documentation_url,
                        changelog = EXCLUDED.changelog,
                        rate_limit = EXCLUDED.rate_limit,
                        idempotency = EXCLUDED.idempotency,
                        business_use_case = EXCLUDED.business_use_case,
                        business_use_case_embedding = EXCLUDED.business_use_case_embedding,
                        source_doc_id = EXCLUDED.source_doc_id,
                        source_file = EXCLUDED.source_file,
                        source_hash = EXCLUDED.source_hash,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING spec_id
                """,
                    spec.get('endpoint_id'),
                    spec.get('method'),
                    spec.get('path'),
                    spec.get('api_version', 'v1'),
                    spec.get('description'),
                    spec.get('summary'),
                    spec.get('documentation_url'),
                    json.dumps(spec.get('changelog', [])),
                    json.dumps(spec.get('rate_limit', {})),
                    json.dumps(spec.get('idempotency', {})),
                    spec.get('business_use_case'),
                    json.dumps(spec.get('business_use_case_embedding')) if spec.get('business_use_case_embedding') else None,
                    spec.get('source_doc_id'),
                    spec.get('source_file'),
                    spec.get('source_hash')
                )
                
                spec_id = spec_result['spec_id']
                endpoint_id = spec.get('endpoint_id')
                
                # Delete existing related data
                await db_conn.execute("DELETE FROM api_headers WHERE spec_id = $1", spec_id)
                await db_conn.execute("DELETE FROM api_fields WHERE spec_id = $1", spec_id)
                await db_conn.execute("DELETE FROM api_conditions WHERE spec_id = $1", spec_id)
                await db_conn.execute("DELETE FROM api_samples WHERE spec_id = $1", spec_id)
                
                # Insert headers
                headers = spec.get('headers', {})
                for header_type in ['request', 'response']:
                    for header in headers.get(header_type, []):
                        await db_conn.execute("""
                            INSERT INTO api_headers (
                                spec_id, header_type, name, value_template, required,
                                description, conditional_when, conditional_expression,
                                pattern, enum_values, min_length, max_length,
                                example_value, default_value
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                        """,
                            spec_id, header_type,
                            header.get('name'),
                            header.get('value_template'),
                            header.get('required', True),
                            header.get('description'),
                            header.get('conditional_when'),
                            header.get('conditional_expression'),
                            header.get('pattern'),
                            json.dumps(header.get('enum_values', [])),
                            header.get('min_length'),
                            header.get('max_length'),
                            header.get('example_value'),
                            header.get('default_value')
                        )
                
                # Insert conditions
                for condition in spec.get('conditions', []):
                    await db_conn.execute("""
                        INSERT INTO api_conditions (
                            spec_id, condition_name, description, expression,
                            trigger_field, trigger_values
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                        spec_id,
                        condition.get('condition_name'),
                        condition.get('description'),
                        condition.get('expression'),
                        condition.get('trigger_field'),
                        json.dumps(condition.get('trigger_values', []))
                    )
                
                # Helper function to insert fields recursively
                async def insert_fields(fields: List[dict], context: str, parent_path: str = '', start_order: int = 0):
                    for i, field in enumerate(fields):
                        field_name = field.get('field_name') or field.get('name')
                        field_type = field.get('field_type') or field.get('type', 'string')
                        effective_parent_path = field.get('parent_path', parent_path)
                        display_order = field.get('display_order', start_order + i)
                        
                        # Skip if field_name is None or empty
                        if not field_name:
                            continue
                            
                        field_id = await db_conn.fetchval("""
                            INSERT INTO api_fields (
                                spec_id, context, parent_path, field_name,
                                field_type, subtype, format,
                                description, placeholder, requirement,
                                condition_description, condition_expression, condition_dependencies,
                                constraints, array_constraints, object_constraints,
                                example_value, default_value,
                                is_sensitive, encoding, display_order
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21)
                            ON CONFLICT (spec_id, context, full_path) DO NOTHING
                            RETURNING field_id
                        """,
                            spec_id, context, effective_parent_path, field_name,
                            field_type,
                            field.get('subtype'),
                            field.get('format'),
                            field.get('description'),
                            field.get('placeholder'),
                            field.get('requirement', 'optional'),
                            field.get('condition_description'),
                            field.get('condition_expression'),
                            json.dumps(field.get('condition_dependencies', [])),
                            json.dumps(field.get('constraints', {})),
                            json.dumps(field.get('array_constraints', {})),
                            json.dumps(field.get('object_constraints', {})),
                            json.dumps(field.get('example_value')) if field.get('example_value') is not None else None,
                            json.dumps(field.get('default_value')) if field.get('default_value') is not None else None,
                            field.get('is_sensitive', False),
                            field.get('encoding'),
                            display_order
                        )
                        
                        # Handle nested fields
                        nested_fields = field.get('fields', [])
                        if nested_fields:
                            new_parent = f"{effective_parent_path}.{field_name}" if effective_parent_path else field_name
                            await insert_fields(nested_fields, context, new_parent, 0)
                        
                        # Handle array item fields
                        if field_type == 'array' and field.get('item_fields'):
                            new_parent = f"{effective_parent_path}.{field_name}[*]" if effective_parent_path else f"{field_name}[*]"
                            await insert_fields(field.get('item_fields'), context, new_parent, 0)
                
                # Insert request fields
                await insert_fields(spec.get('request_fields', []), 'request')
                
                # Insert response fields
                await insert_fields(spec.get('response_fields', []), 'response')
                
                # Insert samples
                for sample in spec.get('samples', []):
                    await db_conn.execute("""
                        INSERT INTO api_samples (
                            spec_id, sample_name, description, scenario,
                            request, response, curl_command, expected_validation_errors
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                        spec_id,
                        sample.get('sample_name'),
                        sample.get('description'),
                        sample.get('scenario'),
                        json.dumps(sample.get('request', {})),
                        json.dumps(sample.get('response', {})),
                        sample.get('curl_command'),
                        json.dumps(sample.get('expected_validation_errors', []))
                    )
                
                return {
                    "content": [{
                        "type": "text",
                        "text": f"✅ API spec inserted successfully\n\n**Endpoint:** {endpoint_id}\n**Spec ID:** {spec_id}\n\nInserted:\n- Headers: {len(headers.get('request', [])) + len(headers.get('response', []))}\n- Request Fields: {len(spec.get('request_fields', []))}\n- Response Fields: {len(spec.get('response_fields', []))}\n- Conditions: {len(spec.get('conditions', []))}\n- Samples: {len(spec.get('samples', []))}"
                    }],
                    "isError": False
                }
                
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ Error inserting API spec: {str(e)}"
            }],
            "isError": True
        }


async def get_api_spec_v2(endpoint_id: str, include_samples: bool = True) -> dict:
    """Get complete API spec with all details.
    
    Args:
        endpoint_id: The endpoint identifier
        include_samples: Whether to include request/response samples
        
    Returns:
        Complete API specification
    """
    if database._pool is None:
        await database.connect()
    
    conn = database.pool
    
    try:
        async with conn.acquire() as db_conn:
            # Get main spec
            spec_row = await db_conn.fetchrow("""
                SELECT * FROM api_specs_v2 WHERE endpoint_id = $1
            """, endpoint_id)
            
            if not spec_row:
                return {
                    "content": [{
                        "type": "text",
                        "text": f"❌ API spec not found: {endpoint_id}"
                    }],
                    "isError": True
                }
            
            spec_id = spec_row['spec_id']
            
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

            spec_data = dict(spec_row)
            if spec_data.get('business_use_case'):
                sections.append(f"\n## Business Use Case\n{spec_data['business_use_case']}")
            
            # Get headers
            headers = await db_conn.fetch("""
                SELECT * FROM api_headers WHERE spec_id = $1 ORDER BY header_type, name
            """, spec_id)
            
            if headers:
                sections.append("\n## Headers")
                current_type = None
                for h in headers:
                    if h['header_type'] != current_type:
                        current_type = h['header_type']
                        sections.append(f"\n### {current_type.title()} Headers")
                    
                    req_marker = "*" if h['required'] else ""
                    cond_note = f" [Conditional: {h['conditional_when']}]" if h['conditional_when'] else ""
                    sections.append(f"- **{h['name']}**{req_marker}{cond_note}")
                    if h['description']:
                        sections.append(f"  - {h['description']}")
                    if h['example_value']:
                        sections.append(f"  - Example: `{h['example_value']}`")
            
            # Get fields (build tree)
            async def get_fields(context: str) -> List[dict]:
                rows = await db_conn.fetch("""
                    SELECT * FROM api_fields 
                    WHERE spec_id = $1 AND context = $2
                    ORDER BY parent_path, display_order
                """, spec_id, context)
                return [dict(r) for r in rows]
            
            def format_field_tree(fields: List[dict], parent: str = '', indent: int = 0) -> List[str]:
                result = []
                prefix = "  " * indent
                
                for f in fields:
                    field_parent = f.get('parent_path', '')
                    if field_parent == parent:
                        req = f.get('requirement', 'optional')
                        req_marker = {"mandatory": "*", "optional": "", "conditional": "†"}.get(req, "")
                        
                        field_type = f.get('field_type', 'unknown')
                        if f.get('subtype'):
                            field_type += f"<{f['subtype']}>"
                        
                        cond_note = ""
                        if req == 'conditional' and f.get('condition_description'):
                            cond_note = f" [{f['condition_description']}]"
                        
                        line = f"{prefix}- **{f['field_name']}**{req_marker} (`{field_type}`){cond_note}"
                        result.append(line)
                        
                        if f.get('description'):
                            result.append(f"{prefix}  - {f['description']}")
                        
                        # Recurse into children
                        result.extend(format_field_tree(fields, f.get('full_path', f['field_name']), indent + 1))
                
                return result
            
            # Request schema
            request_fields = await get_fields('request')
            if request_fields:
                sections.append("\n## Request Schema")
                sections.append("\nLegend: `*` = Mandatory, `†` = Conditional")
                sections.extend(format_field_tree(request_fields))
            
            # Response schema
            response_fields = await get_fields('response')
            if response_fields:
                sections.append("\n## Response Schema")
                sections.extend(format_field_tree(response_fields))
            
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
            
            # Rate limits - parse from JSONB
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
            
            return {
                "content": [{
                    "type": "text",
                    "text": "\n".join(sections)
                }],
                "isError": False
            }
            
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ Error retrieving API spec: {str(e)}"
            }],
            "isError": True
        }


async def list_api_specs_v2(limit: int = 20) -> dict:
    """List all API specs v2 (latest version only for each endpoint)."""
    if database._pool is None:
        await database.connect()
    
    conn = database.pool
    
    try:
        async with conn.acquire() as db_conn:
            specs = await db_conn.fetch("""
                SELECT DISTINCT ON (endpoint_id) 
                    endpoint_id, method, path, api_version, description
                FROM api_specs_v2
                ORDER BY endpoint_id, api_version DESC
                LIMIT $1
            """, limit)
            
            sections = ["# Available API Specifications (Latest Versions)\n"]
            for s in specs:
                version_info = f" (v{s['api_version']})" if s['api_version'] else ""
                sections.append(f"- **{s['endpoint_id']}**{version_info} - {s['method']} {s['path']}")
                if s['description']:
                    sections.append(f"  - {s['description'][:80]}...")
            
            return {
                "content": [{
                    "type": "text",
                    "text": "\n".join(sections)
                }],
                "isError": False
            }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ Error: {str(e)}"
            }],
            "isError": True
        }


async def list_api_versions(endpoint_id: str) -> dict:
    """List all available versions for a specific API endpoint.
    
    Args:
        endpoint_id: The API endpoint identifier (e.g., 'ibmb.merchant.transaction.init')
        
    Returns:
        List of all versions available for the API with their details
    """
    if database._pool is None:
        await database.connect()
    
    conn = database.pool
    
    try:
        async with conn.acquire() as db_conn:
            # Get all versions for the endpoint
            versions = await db_conn.fetch("""
                SELECT 
                    api_version,
                    method,
                    path,
                    description,
                    summary,
                    created_at,
                    updated_at,
                    (SELECT COUNT(*) FROM api_fields WHERE spec_id = s.spec_id) as field_count,
                    (SELECT COUNT(*) FROM api_headers WHERE spec_id = s.spec_id) as header_count,
                    (SELECT COUNT(*) FROM api_samples WHERE spec_id = s.spec_id) as sample_count
                FROM api_specs_v2 s
                WHERE endpoint_id = $1
                ORDER BY api_version DESC
            """, endpoint_id)
            
            if not versions:
                # Check if endpoint exists at all
                exists = await db_conn.fetchval("""
                    SELECT COUNT(*) FROM api_specs_v2 
                    WHERE endpoint_id ILIKE $1
                """, f"%{endpoint_id}%")
                
                if exists:
                    similar = await db_conn.fetch("""
                        SELECT endpoint_id FROM api_specs_v2 
                        WHERE endpoint_id ILIKE $1
                        LIMIT 5
                    """, f"%{endpoint_id}%")
                    suggestions = "\n".join([f"  - {s['endpoint_id']}" for s in similar])
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"❌ No versions found for '{endpoint_id}'.\n\nDid you mean:\n{suggestions}"
                        }],
                        "isError": True
                    }
                else:
                    all_endpoints = await db_conn.fetch("""
                        SELECT DISTINCT endpoint_id FROM api_specs_v2 
                        ORDER BY endpoint_id 
                        LIMIT 10
                    """)
                    available = "\n".join([f"  - {e['endpoint_id']}" for e in all_endpoints])
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"❌ Endpoint '{endpoint_id}' not found.\n\nAvailable endpoints:\n{available}\n\nUse list_api_specs_v2 to see all available APIs."
                        }],
                        "isError": True
                    }
            
            # Build response
            sections = [
                f"# API Versions: {endpoint_id}",
                f"\n**Total Versions:** {len(versions)}"
            ]
            
            for i, v in enumerate(versions, 1):
                sections.append(f"\n## Version {v['api_version']}")
                
                # Basic info
                info_line = f"**{v['method']}** {v['path']}"
                sections.append(info_line)
                
                if v['summary']:
                    sections.append(f"**Summary:** {v['summary']}")
                
                if v['description']:
                    sections.append(f"**Description:** {v['description'][:100]}...")
                
                # Stats
                sections.append(f"\n**Stats:**")
                sections.append(f"- Fields: {v['field_count']}")
                sections.append(f"- Headers: {v['header_count']}")
                sections.append(f"- Samples: {v['sample_count']}")
                
                # Timestamps
                if v['created_at']:
                    sections.append(f"- Created: {v['created_at'].strftime('%Y-%m-%d')}")
                if v['updated_at']:
                    sections.append(f"- Updated: {v['updated_at'].strftime('%Y-%m-%d')}")
                
                # Latest indicator
                if i == 1:
                    sections.append(f"\n⭐ **This is the LATEST version**")
            
            sections.append(f"\n---")
            sections.append(f"\n**Usage:**")
            sections.append(f"To get details of a specific version:")
            sections.append(f"`get_api_spec(endpoint_id='{endpoint_id}', version='VERSION')`")
            
            return {
                "content": [{
                    "type": "text",
                    "text": "\n".join(sections)
                }],
                "isError": False
            }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ Error: {str(e)}"
            }],
            "isError": True
        }
