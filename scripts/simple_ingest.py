#!/usr/bin/env python3
"""Simple ingestion without pgvector - extracts and stores text content."""

import asyncio
import json
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, '/home/ganesh/merchant_mcp')

import pdfplumber
import asyncpg

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'merchant_mcp',
    'user': 'postgres',
}


def parse_pdf(filepath: Path) -> dict:
    """Parse PDF and extract content."""
    content = {
        'text': '',
        'tables': [],
        'metadata': {},
        'pages': []
    }
    
    with pdfplumber.open(filepath) as pdf:
        content['metadata'] = {
            'num_pages': len(pdf.pages),
            'filename': filepath.name
        }
        
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ''
            content['text'] += f"\n\n--- Page {i + 1} ---\n\n" + page_text
            
            tables = page.extract_tables()
            for table in tables:
                content['tables'].append({
                    'page': i + 1,
                    'data': table
                })
            
            content['pages'].append({
                'page_num': i + 1,
                'text': page_text,
                'tables': tables
            })
    
    return content


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        
        # Try to break at sentence boundary
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


async def init_db(pool):
    """Initialize database schema without pgvector."""
    async with pool.acquire() as conn:
        # Simple documents table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                filename TEXT,
                content TEXT,
                chunks JSONB,
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Simple endpoints table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS endpoints (
                endpoint_id TEXT PRIMARY KEY,
                method TEXT,
                path TEXT,
                description TEXT,
                spec_data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        print("✓ Database schema initialized")


async def ingest_file(pool, filepath: Path) -> dict:
    """Ingest a single PDF file."""
    print(f"\nProcessing: {filepath.name}")
    
    # Parse PDF
    content = parse_pdf(filepath)
    
    # Calculate hash
    doc_hash = hashlib.sha256(content['text'].encode()).hexdigest()
    doc_id = f"{filepath.stem}_{doc_hash[:16]}"
    
    # Check if already exists
    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            "SELECT doc_id FROM documents WHERE doc_id = $1",
            doc_id
        )
        if existing:
            print(f"  ⊘ Already ingested: {doc_id}")
            return {'status': 'skipped', 'doc_id': doc_id}
    
    # Chunk text
    chunks = chunk_text(content['text'])
    print(f"  ✓ Parsed {content['metadata']['num_pages']} pages, {len(chunks)} chunks")
    
    # Store in database
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO documents (doc_id, filename, content, chunks, metadata)
            VALUES ($1, $2, $3, $4, $5)
        """, 
        doc_id,
        filepath.name,
        content['text'][:100000],  # Limit content size
        json.dumps(chunks),
        json.dumps(content['metadata'])
        )
    
    print(f"  ✓ Stored in database: {doc_id}")
    
    return {
        'status': 'success',
        'doc_id': doc_id,
        'pages': content['metadata']['num_pages'],
        'chunks': len(chunks)
    }


async def main():
    """Main ingestion function."""
    print("=" * 60)
    print("IBMB Document Ingestion")
    print("=" * 60)
    
    # Connect to database
    pool = await asyncpg.create_pool(**DB_CONFIG)
    print("✓ Connected to database")
    
    # Initialize schema
    await init_db(pool)
    
    # Find IBMB files
    ibmb_folder = Path("/home/ganesh/Downloads/ibmb")
    pdf_files = list(ibmb_folder.glob("*.pdf"))
    
    print(f"\nFound {len(pdf_files)} PDF files")
    
    # Ingest each file
    results = []
    for filepath in pdf_files:
        try:
            result = await ingest_file(pool, filepath)
            results.append(result)
        except Exception as e:
            print(f"  ✗ Error: {e}")
            results.append({'status': 'error', 'file': str(filepath), 'error': str(e)})
    
    # Summary
    print("\n" + "=" * 60)
    print("Ingestion Summary")
    print("=" * 60)
    
    success = sum(1 for r in results if r.get('status') == 'success')
    skipped = sum(1 for r in results if r.get('status') == 'skipped')
    failed = sum(1 for r in results if r.get('status') == 'error')
    
    print(f"  ✓ Successful: {success}")
    print(f"  ⊘ Skipped: {skipped}")
    print(f"  ✗ Failed: {failed}")
    
    # Show stored documents
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT doc_id, filename FROM documents ORDER BY created_at DESC")
        print(f"\n  Total documents in database: {len(rows)}")
        for row in rows[:5]:
            print(f"    - {row['filename']}")
    
    await pool.close()
    print("\n✓ Ingestion complete!")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
