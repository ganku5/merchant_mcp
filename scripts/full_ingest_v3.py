#!/usr/bin/env python3
"""Ultra-lightweight full ingestion - entities only, no embeddings initially."""

import asyncio
import json
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, '/home/ganesh/merchant_mcp')

import pdfplumber
import asyncpg

from src.utils.llm import llm_client

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'merchant_mcp',
    'user': 'postgres',
}


async def init_schema():
    """Initialize database."""
    pool = await asyncpg.create_pool(**DB_CONFIG)
    async with pool.acquire() as conn:
        for table in ['endpoint_specs', 'error_codes', 'integration_flows', 'documents']:
            await conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        
        await conn.execute("""
            CREATE TABLE documents (
                doc_id TEXT PRIMARY KEY,
                filename TEXT,
                num_pages INTEGER,
                total_chars INTEGER
            )
        """)
        
        await conn.execute("""
            CREATE TABLE endpoint_specs (
                endpoint_id TEXT PRIMARY KEY,
                method TEXT,
                path TEXT,
                description TEXT,
                spec_data JSONB,
                source_doc_id TEXT
            )
        """)
        
        await conn.execute("""
            CREATE TABLE error_codes (
                error_code TEXT PRIMARY KEY,
                category TEXT,
                description TEXT,
                error_data JSONB,
                source_doc_id TEXT
            )
        """)
        
        await conn.execute("""
            CREATE TABLE integration_flows (
                flow_id TEXT PRIMARY KEY,
                name TEXT,
                use_case TEXT,
                description TEXT,
                steps JSONB,
                flow_data JSONB,
                source_doc_id TEXT
            )
        """)
        print("✓ Schema initialized")
    await pool.close()


async def extract_entities(text: str) -> dict:
    """Extract all entity types in one LLM call."""
    # Use first 2000 chars only
    text = text[:2000]
    
    prompt = f"""From this payment API documentation, extract entities as JSON:
{{
  "endpoints": [
    {{
      "endpoint_id": "unique.name",
      "method": "POST|GET|PUT|DELETE",
      "path": "/v1/...",
      "description": "what it does",
      "auth_type": "api_key"
    }}
  ],
  "error_codes": [
    {{
      "error_code": "CODE_NAME",
      "category": "retryable|terminal|merchant_action",
      "message": "Human readable message",
      "description": "Detailed explanation"
    }}
  ],
  "flows": [
    {{
      "flow_id": "unique.id",
      "name": "Flow Name",
      "use_case": "payment|collect|mandate|refund|subscription",
      "description": "What this flow does",
      "steps": ["step 1", "step 2"]
    }}
  ]
}}

Documentation:
{text}

Return ONLY valid JSON."""
    
    try:
        response = await llm_client.chat([
            {"role": "system", "content": "You extract structured data from API docs. Return only valid JSON."},
            {"role": "user", "content": prompt}
        ], temperature=0.1, max_tokens=2000)
        
        # Extract JSON
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0]
        else:
            json_str = response
        
        data = json.loads(json_str.strip())
        return {
            'endpoints': data.get('endpoints', []),
            'error_codes': data.get('error_codes', []),
            'flows': data.get('flows', [])
        }
    except Exception as e:
        print(f"   ⚠️ Extraction error: {e}")
        return {'endpoints': [], 'error_codes': [], 'flows': []}


async def process_pdf(pool, filepath: Path) -> dict:
    """Process a single PDF."""
    print(f"\n📄 {filepath.name[:50]}")
    
    # Extract text
    with pdfplumber.open(filepath) as pdf:
        pages_text = [p.extract_text() or '' for p in pdf.pages]
    
    full_text = '\n\n'.join(pages_text)
    num_pages = len(pages_text)
    total_chars = len(full_text)
    
    # Doc ID
    doc_hash = hashlib.sha256(full_text[:3000].encode()).hexdigest()
    doc_id = f"{filepath.stem[:20]}_{doc_hash[:8]}"
    
    print(f"   {num_pages} pages, {total_chars:,} chars")
    
    async with pool.acquire() as conn:
        exists = await conn.fetchval("SELECT 1 FROM documents WHERE doc_id = $1", doc_id)
        if exists:
            print("   ⊘ Exists")
            return {'status': 'skipped'}
        
        await conn.execute("""
            INSERT INTO documents (doc_id, filename, num_pages, total_chars)
            VALUES ($1, $2, $3, $4)
        """, doc_id, filepath.name, num_pages, total_chars)
    
    # Extract entities
    print("   🔍 Extracting...")
    entities = await extract_entities(full_text)
    
    # Store endpoints
    async with pool.acquire() as conn:
        for ep in entities['endpoints']:
            ep_id = ep.get('endpoint_id') or f"ep_{hashlib.md5(ep.get('path','').encode()).hexdigest()[:6]}"
            await conn.execute("""
                INSERT INTO endpoint_specs (endpoint_id, method, path, description, spec_data, source_doc_id)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (endpoint_id) DO NOTHING
            """, ep_id, ep.get('method','POST'), ep.get('path',''),
                ep.get('description','')[:150], json.dumps(ep), doc_id)
        
        for err in entities['error_codes']:
            code = err.get('error_code')
            if code:
                await conn.execute("""
                    INSERT INTO error_codes (error_code, category, description, error_data, source_doc_id)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (error_code) DO NOTHING
                """, code, err.get('category','system_error'),
                    err.get('description',''), json.dumps(err), doc_id)
        
        for flow in entities['flows']:
            fid = flow.get('flow_id') or f"flow_{hashlib.md5(flow.get('name','').encode()).hexdigest()[:6]}"
            await conn.execute("""
                INSERT INTO integration_flows (flow_id, name, use_case, description, steps, flow_data, source_doc_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (flow_id) DO NOTHING
            """, fid, flow.get('name',''), flow.get('use_case','payment'),
                flow.get('description',''), json.dumps(flow.get('steps',[])),
                json.dumps(flow), doc_id)
    
    print(f"   ✓ {len(entities['endpoints'])} EPs, {len(entities['error_codes'])} ERRs, {len(entities['flows'])} FLWs")
    
    return {
        'status': 'success',
        'endpoints': len(entities['endpoints']),
        'errors': len(entities['error_codes']),
        'flows': len(entities['flows'])
    }


async def main():
    print("=" * 60)
    print("FULL INGESTION v3 (Entities Only)")
    print("=" * 60)
    
    await init_schema()
    
    pool = await asyncpg.create_pool(**DB_CONFIG, min_size=1, max_size=2)
    
    pdfs = sorted(Path("/home/ganesh/Downloads/ibmb").glob("*.pdf"))
    print(f"\nFound {len(pdfs)} PDFs\n")
    
    results = []
    for pdf in pdfs:
        try:
            result = await process_pdf(pool, pdf)
            results.append(result)
        except Exception as e:
            print(f"   ✗ Error: {e}")
            results.append({'status': 'error'})
    
    # Summary
    print("\n" + "=" * 60)
    success = sum(1 for r in results if r.get('status') == 'success')
    total_eps = sum(r.get('endpoints', 0) for r in results)
    total_errs = sum(r.get('errors', 0) for r in results)
    total_flows = sum(r.get('flows', 0) for r in results)
    
    print(f"Processed: {success}/{len(pdfs)} files")
    print(f"Extracted: {total_eps} endpoints, {total_errs} error codes, {total_flows} flows")
    
    async with pool.acquire() as conn:
        stats = await conn.fetchrow("""
            SELECT 
                (SELECT COUNT(*) FROM documents) as docs,
                (SELECT COUNT(*) FROM endpoint_specs) as eps,
                (SELECT COUNT(*) FROM error_codes) as errs,
                (SELECT COUNT(*) FROM integration_flows) as flows
        """)
        print(f"\nDatabase: {stats['docs']} docs, {stats['eps']} endpoints, {stats['errs']} errors, {stats['flows']} flows")
    
    await pool.close()
    print("\n✓ Done!")
    return 0


if __name__ == "__main__":
    asyncio.run(main())
