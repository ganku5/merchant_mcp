#!/usr/bin/env python3
"""Lightweight ingestion for IBMB files - processes one file at a time."""

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


async def init_db():
    """Initialize database."""
    pool = await asyncpg.create_pool(**DB_CONFIG)
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                filename TEXT,
                num_pages INTEGER,
                total_chars INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    await pool.close()
    print("✓ Database initialized")


async def ingest_single_pdf(filepath: Path) -> dict:
    """Ingest a single PDF."""
    print(f"\n📄 Processing: {filepath.name}")
    
    # Extract text
    text_chunks = []
    num_pages = 0
    
    with pdfplumber.open(filepath) as pdf:
        num_pages = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ''
            text_chunks.append(page_text)
            if i % 10 == 0:
                print(f"   Page {i+1}/{num_pages}...")
    
    full_text = "\n\n".join(text_chunks)
    total_chars = len(full_text)
    
    # Generate doc_id
    doc_hash = hashlib.sha256(full_text[:5000].encode()).hexdigest()
    doc_id = f"{filepath.stem[:30]}_{doc_hash[:12]}"
    
    # Store in DB
    pool = await asyncpg.create_pool(**DB_CONFIG)
    async with pool.acquire() as conn:
        # Check existing
        existing = await conn.fetchval(
            "SELECT 1 FROM documents WHERE doc_id = $1", doc_id
        )
        if existing:
            print(f"   ⊘ Already exists: {doc_id}")
            await pool.close()
            return {'status': 'skipped', 'doc_id': doc_id}
        
        # Insert
        await conn.execute("""
            INSERT INTO documents (doc_id, filename, num_pages, total_chars)
            VALUES ($1, $2, $3, $4)
        """, doc_id, filepath.name, num_pages, total_chars)
    
    await pool.close()
    print(f"   ✓ Stored: {doc_id}")
    print(f"   📊 {num_pages} pages, {total_chars:,} characters")
    
    return {
        'status': 'success',
        'doc_id': doc_id,
        'pages': num_pages,
        'chars': total_chars
    }


async def main():
    """Main ingestion."""
    print("=" * 60)
    print("IBMB Document Ingestion (Lightweight)")
    print("=" * 60)
    
    await init_db()
    
    ibmb_folder = Path("/home/ganesh/Downloads/ibmb")
    pdf_files = sorted(ibmb_folder.glob("*.pdf"))
    
    print(f"\nFound {len(pdf_files)} PDF files")
    
    results = []
    for pdf_file in pdf_files:
        try:
            result = await ingest_single_pdf(pdf_file)
            results.append(result)
        except Exception as e:
            print(f"   ✗ Error: {e}")
            results.append({'status': 'error', 'error': str(e)})
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    success = sum(1 for r in results if r.get('status') == 'success')
    skipped = sum(1 for r in results if r.get('status') == 'skipped')
    failed = sum(1 for r in results if r.get('status') == 'error')
    
    print(f"  ✓ Successful: {success}")
    print(f"  ⊘ Skipped: {skipped}")
    print(f"  ✗ Failed: {failed}")
    
    # Show documents in DB
    pool = await asyncpg.create_pool(**DB_CONFIG)
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT filename, num_pages, total_chars 
            FROM documents 
            ORDER BY created_at DESC
        """)
        print(f"\n  Total documents: {len(rows)}")
        for row in rows:
            print(f"    • {row['filename']}: {row['num_pages']} pages, {row['total_chars']:,} chars")
    await pool.close()
    
    print("\n✓ Ingestion complete!")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
