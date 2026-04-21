#!/usr/bin/env python3
"""Full ingestion pipeline with entity extraction and embeddings."""

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


# Extraction schemas for LLM
ENDPOINT_SCHEMA = {
    "api_endpoints": [{
        "endpoint_id": "string - unique identifier like orders.create",
        "method": "GET|POST|PUT|DELETE",
        "path": "string - URL path like /v1/orders/create",
        "description": "string - what this endpoint does",
        "auth_type": "api_key|bearer|basic",
        "request_fields": [{"name": "", "type": "", "required": True, "description": ""}],
        "response_fields": [{"name": "", "type": "", "description": ""}]
    }]
}

ERROR_SCHEMA = {
    "error_codes": [{
        "error_code": "string - error code",
        "http_status": 400,
        "category": "retryable|terminal|merchant_action|system_error",
        "message": "string - human readable message",
        "description": "string - detailed explanation",
        "common_causes": ["list of causes"],
        "fix_suggestions": ["list of fixes"]
    }]
}

FLOW_SCHEMA = {
    "integration_flows": [{
        "flow_id": "string - unique identifier",
        "name": "string - flow name",
        "use_case": "payment|collect|mandate|refund|subscription",
        "description": "string - what this flow accomplishes",
        "steps": [{
            "step_number": 1,
            "name": "string - step name",
            "description": "string - what this step does",
            "endpoint_id": "string - which endpoint to call"
        }]
    }]
}


async def init_full_schema():
    """Initialize full database schema."""
    pool = await asyncpg.create_pool(**DB_CONFIG)
    async with pool.acquire() as conn:
        # Documents table
        await conn.execute("""
            DROP TABLE IF EXISTS documents CASCADE;
            CREATE TABLE documents (
                doc_id TEXT PRIMARY KEY,
                filename TEXT,
                content TEXT,
                num_pages INTEGER,
                total_chars INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Text chunks table
        await conn.execute("""
            DROP TABLE IF EXISTS text_chunks CASCADE;
            CREATE TABLE text_chunks (
                chunk_id SERIAL PRIMARY KEY,
                doc_id TEXT REFERENCES documents(doc_id) ON DELETE CASCADE,
                chunk_index INTEGER,
                chunk_text TEXT,
                embedding FLOAT[],  -- Array for vector storage (pgvector alternative)
                UNIQUE(doc_id, chunk_index)
            )
        """)
        
        # Endpoint specs
        await conn.execute("""
            DROP TABLE IF EXISTS endpoint_specs CASCADE;
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
                source_doc_id TEXT,
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Error codes
        await conn.execute("""
            DROP TABLE IF EXISTS error_codes CASCADE;
            CREATE TABLE error_codes (
                error_code TEXT PRIMARY KEY,
                http_status INTEGER,
                category TEXT,
                message TEXT,
                description TEXT,
                common_causes JSONB,
                fix_suggestions JSONB,
                error_data JSONB,
                source_doc_id TEXT,
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Integration flows
        await conn.execute("""
            DROP TABLE IF EXISTS integration_flows CASCADE;
            CREATE TABLE integration_flows (
                flow_id TEXT PRIMARY KEY,
                name TEXT,
                use_case TEXT,
                description TEXT,
                steps JSONB,
                version TEXT DEFAULT 'v1',
                flow_data JSONB,
                source_doc_id TEXT,
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Code templates
        await conn.execute("""
            DROP TABLE IF EXISTS code_templates CASCADE;
            CREATE TABLE code_templates (
                template_id TEXT PRIMARY KEY,
                language TEXT,
                endpoint_id TEXT,
                code_text TEXT,
                template_data JSONB,
                source_doc_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Known issues
        await conn.execute("""
            DROP TABLE IF EXISTS known_issues CASCADE;
            CREATE TABLE known_issues (
                issue_id TEXT PRIMARY KEY,
                pattern TEXT,
                resolution TEXT,
                category TEXT,
                affected_endpoints JSONB,
                issue_data JSONB,
                source_doc_id TEXT,
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Source tracking
        await conn.execute("""
            DROP TABLE IF EXISTS source_documents CASCADE;
            CREATE TABLE source_documents (
                doc_id TEXT PRIMARY KEY,
                source_type TEXT,
                raw_content TEXT,
                hash TEXT,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        print("✓ Full database schema initialized")
    await pool.close()


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        
        # Break at sentence boundary if possible
        if end < len(text):
            last_period = chunk.rfind('.')
            last_newline = chunk.rfind('\n')
            break_point = max(last_period, last_newline)
            if break_point > chunk_size // 2:
                chunk = chunk[:break_point + 1]
                end = start + break_point + 1
        
        chunks.append(chunk.strip())
        start = end - overlap
    
    return chunks


async def extract_entities(text: str, schema: Dict[str, Any], entity_type: str) -> List[Dict]:
    """Extract entities using LLM."""
    # Truncate text for LLM
    max_chars = 6000
    truncated = text[:max_chars] if len(text) > max_chars else text
    
    prompt = f"""Extract {entity_type} from this payment API documentation.

DOCUMENTATION:
{truncated}

Extract according to this schema:
{json.dumps(schema, indent=2)}

Return ONLY valid JSON matching the schema exactly. If no entities found, return empty arrays."""

    try:
        response = await llm_client.chat([
            {"role": "system", "content": "You are a precise data extraction assistant. Return only valid JSON."},
            {"role": "user", "content": prompt}
        ], temperature=0.1)
        
        # Extract JSON from response
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0]
        else:
            json_str = response
        
        result = json.loads(json_str.strip())
        
        # Return appropriate array based on entity type
        if entity_type == "API endpoints":
            return result.get("api_endpoints", [])
        elif entity_type == "error codes":
            return result.get("error_codes", [])
        elif entity_type == "integration flows":
            return result.get("integration_flows", [])
        return []
    except Exception as e:
        print(f"   ⚠️ Extraction failed: {e}")
        return []


async def generate_embeddings(chunks: List[str]) -> List[List[float]]:
    """Generate embeddings using LiteLLM."""
    if not chunks:
        return []
    
    print(f"   Generating embeddings for {len(chunks)} chunks...")
    
    # Process in batches of 10
    all_embeddings = []
    batch_size = 10
    
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        try:
            embeddings = await llm_client.embed(batch)
            all_embeddings.extend(embeddings)
            print(f"     Batch {i//batch_size + 1}/{(len(chunks)-1)//batch_size + 1} ✓")
        except Exception as e:
            print(f"     Batch failed: {e}")
            # Fill with zeros as fallback
            all_embeddings.extend([[0.0] * 768] * len(batch))
    
    return all_embeddings


async def ingest_single_pdf(pool, filepath: Path) -> Dict:
    """Ingest a single PDF with full extraction."""
    print(f"\n📄 Processing: {filepath.name}")
    
    # Parse PDF
    text_chunks = []
    num_pages = 0
    
    with pdfplumber.open(filepath) as pdf:
        num_pages = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ''
            text_chunks.append(page_text)
            if i % 10 == 0 and i > 0:
                print(f"   Page {i}/{num_pages}...")
    
    full_text = "\n\n".join(text_chunks)
    total_chars = len(full_text)
    
    print(f"   ✓ Parsed {num_pages} pages, {total_chars:,} characters")
    
    # Generate doc_id
    doc_hash = hashlib.sha256(full_text[:5000].encode()).hexdigest()
    doc_id = f"{filepath.stem[:30]}_{doc_hash[:12]}"
    
    # Check if exists
    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            "SELECT 1 FROM documents WHERE doc_id = $1", doc_id
        )
        if existing:
            print(f"   ⊘ Already ingested: {doc_id}")
            return {'status': 'skipped', 'doc_id': doc_id}
        
        # Insert document
        await conn.execute("""
            INSERT INTO documents (doc_id, filename, content, num_pages, total_chars)
            VALUES ($1, $2, $3, $4, $5)
        """, doc_id, filepath.name, full_text[:100000], num_pages, total_chars)
    
    print(f"   ✓ Stored document: {doc_id}")
    
    # Chunk and generate embeddings
    chunks = chunk_text(full_text)
    print(f"   Created {len(chunks)} text chunks")
    
    embeddings = await generate_embeddings(chunks)
    
    # Store chunks with embeddings
    async with pool.acquire() as conn:
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            await conn.execute("""
                INSERT INTO text_chunks (doc_id, chunk_index, chunk_text, embedding)
                VALUES ($1, $2, $3, $4)
            """, doc_id, i, chunk, embedding)
    
    print(f"   ✓ Stored {len(chunks)} chunks with embeddings")
    
    # Extract entities
    print(f"\n   🔍 Extracting entities...")
    
    # Extract API endpoints
    endpoints = await extract_entities(full_text, ENDPOINT_SCHEMA, "API endpoints")
    print(f"   Found {len(endpoints)} API endpoints")
    
    async with pool.acquire() as conn:
        for ep in endpoints:
            ep_id = ep.get('endpoint_id') or f"ep_{hashlib.md5(ep.get('path', '').encode()).hexdigest()[:8]}"
            await conn.execute("""
                INSERT INTO endpoint_specs (endpoint_id, method, path, description, 
                    auth_type, request_schema, response_schema, error_responses, 
                    spec_data, source_doc_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (endpoint_id) DO UPDATE SET
                    spec_data = EXCLUDED.spec_data,
                    source_doc_id = EXCLUDED.source_doc_id
            """, 
                ep_id,
                ep.get('method', 'POST'),
                ep.get('path', ''),
                ep.get('description', ''),
                ep.get('auth_type', 'api_key'),
                json.dumps(ep.get('request_fields', [])),
                json.dumps(ep.get('response_fields', [])),
                json.dumps(ep.get('error_codes', [])),
                json.dumps(ep),
                doc_id
            )
    
    # Extract error codes
    errors = await extract_entities(full_text, ERROR_SCHEMA, "error codes")
    print(f"   Found {len(errors)} error codes")
    
    async with pool.acquire() as conn:
        for err in errors:
            err_code = err.get('error_code')
            if not err_code:
                continue
            await conn.execute("""
                INSERT INTO error_codes (error_code, http_status, category, message,
                    description, common_causes, fix_suggestions, error_data, source_doc_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (error_code) DO UPDATE SET
                    error_data = EXCLUDED.error_data,
                    source_doc_id = EXCLUDED.source_doc_id
            """,
                err_code,
                err.get('http_status', 400),
                err.get('category', 'system_error'),
                err.get('message', ''),
                err.get('description', ''),
                json.dumps(err.get('common_causes', [])),
                json.dumps(err.get('fix_suggestions', [])),
                json.dumps(err),
                doc_id
            )
    
    # Extract integration flows
    flows = await extract_entities(full_text, FLOW_SCHEMA, "integration flows")
    print(f"   Found {len(flows)} integration flows")
    
    async with pool.acquire() as conn:
        for flow in flows:
            flow_id = flow.get('flow_id') or f"flow_{hashlib.md5(flow.get('name', '').encode()).hexdigest()[:8]}"
            await conn.execute("""
                INSERT INTO integration_flows (flow_id, name, use_case, description,
                    steps, flow_data, source_doc_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (flow_id) DO UPDATE SET
                    flow_data = EXCLUDED.flow_data,
                    source_doc_id = EXCLUDED.source_doc_id
            """,
                flow_id,
                flow.get('name', ''),
                flow.get('use_case', 'payment'),
                flow.get('description', ''),
                json.dumps(flow.get('steps', [])),
                json.dumps(flow),
                doc_id
            )
    
    print(f"   ✓ Entity extraction complete")
    
    return {
        'status': 'success',
        'doc_id': doc_id,
        'pages': num_pages,
        'chars': total_chars,
        'chunks': len(chunks),
        'endpoints': len(endpoints),
        'errors': len(errors),
        'flows': len(flows)
    }


async def main():
    """Main ingestion function."""
    print("=" * 70)
    print("FULL INGESTION PIPELINE")
    print("=" * 70)
    print(f"\nLLM: {Config.LLM_MODEL}")
    print(f"Embedding: {Config.EMBEDDING_MODEL}")
    
    # Initialize schema
    await init_full_schema()
    
    # Connect to database
    pool = await asyncpg.create_pool(**DB_CONFIG)
    
    # Find PDFs
    ibmb_folder = Path("/home/ganesh/Downloads/ibmb")
    pdf_files = sorted(ibmb_folder.glob("*.pdf"))
    
    print(f"\nFound {len(pdf_files)} PDF files")
    
    # Process each file
    results = []
    for pdf_file in pdf_files:
        try:
            result = await ingest_single_pdf(pool, pdf_file)
            results.append(result)
        except Exception as e:
            print(f"   ✗ Error: {e}")
            import traceback
            traceback.print_exc()
            results.append({'status': 'error', 'error': str(e)})
    
    # Summary
    print("\n" + "=" * 70)
    print("INGESTION SUMMARY")
    print("=" * 70)
    
    success = sum(1 for r in results if r.get('status') == 'success')
    skipped = sum(1 for r in results if r.get('status') == 'skipped')
    failed = sum(1 for r in results if r.get('status') == 'error')
    
    total_chunks = sum(r.get('chunks', 0) for r in results if r.get('status') == 'success')
    total_endpoints = sum(r.get('endpoints', 0) for r in results if r.get('status') == 'success')
    total_errors = sum(r.get('errors', 0) for r in results if r.get('status') == 'success')
    total_flows = sum(r.get('flows', 0) for r in results if r.get('status') == 'success')
    
    print(f"\nFiles:")
    print(f"  ✓ Successful: {success}")
    print(f"  ⊘ Skipped: {skipped}")
    print(f"  ✗ Failed: {failed}")
    
    print(f"\nContent:")
    print(f"  • Text chunks: {total_chunks}")
    print(f"  • API endpoints: {total_endpoints}")
    print(f"  • Error codes: {total_errors}")
    print(f"  • Integration flows: {total_flows}")
    
    # Show database stats
    async with pool.acquire() as conn:
        doc_count = await conn.fetchval("SELECT COUNT(*) FROM documents")
        chunk_count = await conn.fetchval("SELECT COUNT(*) FROM text_chunks")
        ep_count = await conn.fetchval("SELECT COUNT(*) FROM endpoint_specs")
        err_count = await conn.fetchval("SELECT COUNT(*) FROM error_codes")
        flow_count = await conn.fetchval("SELECT COUNT(*) FROM integration_flows")
        
        print(f"\nDatabase totals:")
        print(f"  • Documents: {doc_count}")
        print(f"  • Text chunks: {chunk_count}")
        print(f"  • Endpoints: {ep_count}")
        print(f"  • Error codes: {err_count}")
        print(f"  • Flows: {flow_count}")
    
    await pool.close()
    
    print("\n✓ Full ingestion complete!")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
