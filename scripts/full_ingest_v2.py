#!/usr/bin/env python3
"""Memory-optimized full ingestion pipeline."""

import asyncio
import json
import hashlib
import sys
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, '/home/ganesh/merchant_mcp')

import pdfplumber
import asyncpg

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'merchant_mcp',
    'user': 'postgres',
}

from src.utils.llm import llm_client
from src.utils.config import Config


async def init_schema():
    """Initialize database schema."""
    pool = await asyncpg.create_pool(**DB_CONFIG)
    async with pool.acquire() as conn:
        # Drop and recreate tables
        await conn.execute("DROP TABLE IF EXISTS text_chunks CASCADE")
        await conn.execute("DROP TABLE IF EXISTS endpoint_specs CASCADE")
        await conn.execute("DROP TABLE IF EXISTS error_codes CASCADE")
        await conn.execute("DROP TABLE IF EXISTS integration_flows CASCADE")
        await conn.execute("DROP TABLE IF EXISTS documents CASCADE")
        
        await conn.execute("""
            CREATE TABLE documents (
                doc_id TEXT PRIMARY KEY,
                filename TEXT,
                content TEXT,
                num_pages INTEGER,
                total_chars INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await conn.execute("""
            CREATE TABLE text_chunks (
                chunk_id SERIAL PRIMARY KEY,
                doc_id TEXT REFERENCES documents(doc_id) ON DELETE CASCADE,
                chunk_index INTEGER,
                chunk_text TEXT,
                embedding FLOAT[],
                UNIQUE(doc_id, chunk_index)
            )
        """)
        
        await conn.execute("""
            CREATE TABLE endpoint_specs (
                endpoint_id TEXT PRIMARY KEY,
                method TEXT,
                path TEXT,
                version TEXT DEFAULT 'v1',
                description TEXT,
                auth_type TEXT,
                request_schema JSONB,
                response_schema JSONB,
                error_responses JSONB,
                spec_data JSONB,
                source_doc_id TEXT
            )
        """)
        
        await conn.execute("""
            CREATE TABLE error_codes (
                error_code TEXT PRIMARY KEY,
                http_status INTEGER,
                category TEXT,
                message TEXT,
                description TEXT,
                common_causes JSONB,
                fix_suggestions JSONB,
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
                version TEXT DEFAULT 'v1',
                flow_data JSONB,
                source_doc_id TEXT
            )
        """)
        
        print("✓ Schema initialized")
    await pool.close()


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        
        if end < len(text):
            last_period = chunk.rfind('.')
            last_newline = chunk.rfind('\n')
            break_point = max(last_period, last_newline)
            if break_point > chunk_size // 2:
                chunk = chunk[:break_point + 1]
                end = start + break_point + 1
        
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap
    
    return chunks


async def extract_with_llm(text: str, prompt_suffix: str) -> Dict:
    """Extract data using LLM."""
    max_chars = 4000
    truncated = text[:max_chars] if len(text) > max_chars else text
    
    prompt = f"""Extract structured data from this payment API documentation:

{truncated}

{prompt_suffix}

Return ONLY valid JSON."""

    try:
        response = await llm_client.chat([
            {"role": "system", "content": "You are a precise data extraction assistant. Return only valid JSON."},
            {"role": "user", "content": prompt}
        ], temperature=0.1)
        
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0]
        else:
            json_str = response
        
        return json.loads(json_str.strip())
    except Exception as e:
        print(f"   ⚠️ Extraction error: {e}")
        return {}


async def ingest_pdf(pool, filepath: Path) -> Dict:
    """Ingest a PDF with entity extraction."""
    print(f"\n📄 {filepath.name}")
    
    # Extract text
    text_parts = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            if text.strip():
                text_parts.append(text)
    
    full_text = "\n\n".join(text_parts)
    num_pages = len(text_parts)
    total_chars = len(full_text)
    
    # Generate doc_id
    doc_hash = hashlib.sha256(full_text[:5000].encode()).hexdigest()
    doc_id = f"{filepath.stem[:25]}_{doc_hash[:10]}"
    
    print(f"   {num_pages} pages, {total_chars:,} chars")
    
    # Check exists
    async with pool.acquire() as conn:
        exists = await conn.fetchval("SELECT 1 FROM documents WHERE doc_id = $1", doc_id)
        if exists:
            print("   ⊘ Already ingested")
            return {'status': 'skipped'}
        
        # Insert document
        await conn.execute("""
            INSERT INTO documents (doc_id, filename, content, num_pages, total_chars)
            VALUES ($1, $2, $3, $4, $5)
        """, doc_id, filepath.name, full_text[:50000], num_pages, total_chars)
    
    # Extract entities first 3000 chars only
    sample_text = full_text[:3000]
    
    print("   🔍 Extracting endpoints...")
    endpoints_prompt = """Extract API endpoints as JSON array with format:
[{"endpoint_id": "unique.id", "method": "POST", "path": "/v1/...", "description": "...", "auth_type": "api_key"}]"""
    
    endpoints = await extract_with_llm(sample_text, endpoints_prompt)
    if isinstance(endpoints, list):
        async with pool.acquire() as conn:
            for ep in endpoints:
                ep_id = ep.get('endpoint_id') or f"ep_{hashlib.md5((ep.get('path','')).encode()).hexdigest()[:6]}"
                await conn.execute("""
                    INSERT INTO endpoint_specs (endpoint_id, method, path, description, 
                        auth_type, spec_data, source_doc_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (endpoint_id) DO UPDATE SET spec_data = EXCLUDED.spec_data
                """, ep_id, ep.get('method','POST'), ep.get('path',''), 
                    ep.get('description','')[:200], ep.get('auth_type','api_key'),
                    json.dumps(ep), doc_id)
        print(f"   ✓ {len(endpoints)} endpoints")
    
    print("   🔍 Extracting error codes...")
    errors_prompt = """Extract error codes as JSON array with format:
[{"error_code": "CODE", "category": "retryable|terminal", "message": "...", "description": "..."}]"""
    
    errors = await extract_with_llm(sample_text, errors_prompt)
    if isinstance(errors, list):
        async with pool.acquire() as conn:
            for err in errors:
                code = err.get('error_code')
                if code:
                    await conn.execute("""
                        INSERT INTO error_codes (error_code, http_status, category, 
                            message, description, error_data, source_doc_id)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (error_code) DO UPDATE SET error_data = EXCLUDED.error_data
                    """, code, err.get('http_status',400), err.get('category','system_error'),
                        err.get('message',''), err.get('description',''),
                        json.dumps(err), doc_id)
        print(f"   ✓ {len(errors)} error codes")
    
    print("   🔍 Extracting flows...")
    flows_prompt = """Extract integration flows as JSON array with format:
[{"flow_id": "unique.id", "name": "...", "use_case": "payment|refund", "description": "...", "steps": [{"step_number": 1, "name": "...", "description": "..."}]}]"""
    
    flows = await extract_with_llm(sample_text, flows_prompt)
    if isinstance(flows, list):
        async with pool.acquire() as conn:
            for flow in flows:
                fid = flow.get('flow_id') or f"flow_{hashlib.md5(flow.get('name','').encode()).hexdigest()[:6]}"
                await conn.execute("""
                    INSERT INTO integration_flows (flow_id, name, use_case, 
                        description, steps, flow_data, source_doc_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (flow_id) DO UPDATE SET flow_data = EXCLUDED.flow_data
                """, fid, flow.get('name',''), flow.get('use_case','payment'),
                    flow.get('description',''), json.dumps(flow.get('steps',[])),
                    json.dumps(flow), doc_id)
        print(f"   ✓ {len(flows)} flows")
    
    # Generate embeddings for chunks (small batch)
    print("   🧠 Generating embeddings...")
    chunks = chunk_text(full_text)
    
    # Process max 20 chunks to save memory
    chunks = chunks[:20]
    
    if chunks:
        try:
            embeddings = await llm_client.embed(chunks[:10])  # Batch of 10 max
            async with pool.acquire() as conn:
                for i, (chunk, emb) in enumerate(zip(chunks[:10], embeddings)):
                    await conn.execute("""
                        INSERT INTO text_chunks (doc_id, chunk_index, chunk_text, embedding)
                        VALUES ($1, $2, $3, $4)
                    """, doc_id, i, chunk, emb)
            print(f"   ✓ {len(embeddings)} embeddings")
        except Exception as e:
            print(f"   ⚠️ Embedding failed: {e}")
    
    return {
        'status': 'success',
        'doc_id': doc_id,
        'pages': num_pages,
        'endpoints': len(endpoints) if isinstance(endpoints, list) else 0,
        'errors': len(errors) if isinstance(errors, list) else 0,
        'flows': len(flows) if isinstance(flows, list) else 0
    }


async def main():
    print("=" * 60)
    print("FULL INGESTION PIPELINE v2 (Optimized)")
    print("=" * 60)
    print(f"\nLLM: {Config.LLM_MODEL}")
    print(f"Embedding: {Config.EMBEDDING_MODEL}")
    
    await init_schema()
    
    pool = await asyncpg.create_pool(**DB_CONFIG)
    
    pdfs = list(Path("/home/ganesh/Downloads/ibmb").glob("*.pdf"))
    print(f"\nFound {len(pdfs)} PDFs")
    
    results = []
    for pdf in sorted(pdfs):
        try:
            result = await ingest_pdf(pool, pdf)
            results.append(result)
        except Exception as e:
            print(f"   ✗ Error: {e}")
            results.append({'status': 'error', 'error': str(e)})
    
    # Stats
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    success = sum(1 for r in results if r.get('status') == 'success')
    eps = sum(r.get('endpoints',0) for r in results if r.get('status')=='success')
    errs = sum(r.get('errors',0) for r in results if r.get('status')=='success')
    flows = sum(r.get('flows',0) for r in results if r.get('status')=='success')
    
    print(f"Files: {success} succeeded")
    print(f"Entities: {eps} endpoints, {errs} errors, {flows} flows")
    
    async with pool.acquire() as conn:
        stats = {
            'docs': await conn.fetchval("SELECT COUNT(*) FROM documents"),
            'chunks': await conn.fetchval("SELECT COUNT(*) FROM text_chunks"),
            'endpoints': await conn.fetchval("SELECT COUNT(*) FROM endpoint_specs"),
            'errors': await conn.fetchval("SELECT COUNT(*) FROM error_codes"),
            'flows': await conn.fetchval("SELECT COUNT(*) FROM integration_flows"),
        }
        print(f"\nDatabase: {stats['docs']} docs, {stats['chunks']} chunks, {stats['endpoints']} endpoints, {stats['errors']} errors, {stats['flows']} flows")
    
    await pool.close()
    print("\n✓ Complete!")
    return 0


if __name__ == "__main__":
    asyncio.run(main())
