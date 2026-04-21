#!/usr/bin/env python3
"""Final ingestion - full extraction and chunking."""

import asyncio
import json
import os
import re
import sys
sys.path.insert(0, '/home/ganesh/merchant_mcp')

import pdfplumber
from src.utils.database import database
from src.utils.llm import llm_client

PDF_DIR = "/home/ganesh/Downloads/ibmb"


def clean(text):
    text = text.replace('\x00', '')
    text = re.sub(r' +', ' ', text)
    return text.strip()


def chunk(text, size=800, overlap=150):
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind('. ', max(start, end-150), end)
            if boundary > max(start, end-150):
                end = boundary + 1
        
        piece = text[start:end].strip()
        if len(piece) > 50:
            chunks.append(piece[:1500])
        
        start = end - overlap
        if start >= end:
            break
    return chunks


async def process_one(pdf_path, doc_id):
    """Process one PDF completely."""
    fname = os.path.basename(pdf_path)
    print(f"\n{'='*60}")
    print(f"Processing: {fname}")
    print('='*60)
    
    # Extract
    print("1. Extracting text...")
    parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            t = page.extract_text()
            if t:
                parts.append(f"\n--- Page {i+1} ---\n{t}")
    
    text = clean("\n".join(parts))
    print(f"   ✓ {len(text):,} chars from {len(parts)} pages")
    
    # Connect and store
    await database.connect()
    
    async with database.pool.acquire() as conn:
        # Clear old
        await conn.execute("DELETE FROM text_chunks WHERE doc_id = $1", doc_id)
        await conn.execute("DELETE FROM documents WHERE doc_id = $1", doc_id)
        
        # Store doc
        await conn.execute("""
            INSERT INTO documents (doc_id, filename, content, num_pages, total_chars, source_type)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, doc_id, fname, text[:100000], len(parts), len(text), 'pdf')
        print("2. Document stored")
        
        # Chunk
        chunks = chunk(text)
        print(f"3. Created {len(chunks)} chunks")
        
        # Store chunks with embeddings (small batches)
        print("4. Adding embeddings...")
        success = 0
        
        for i in range(0, len(chunks), 3):
            batch = chunks[i:i+3]
            
            try:
                embeds = await llm_client.embed(batch)
                for j, (ct, emb) in enumerate(zip(batch, embeds)):
                    await conn.execute("""
                        INSERT INTO text_chunks (doc_id, chunk_index, chunk_text, embedding, namespace)
                        VALUES ($1, $2, $3, $4::jsonb, $5)
                    """, doc_id, i+j, ct, json.dumps(emb), f"pdf_{doc_id}")
                success += len(batch)
                print(f"   Batch {i//3+1}: {len(batch)} done")
            except Exception as e:
                print(f"   Batch {i//3+1} failed: {e}")
                for j, ct in enumerate(batch):
                    await conn.execute("""
                        INSERT INTO text_chunks (doc_id, chunk_index, chunk_text, embedding, namespace)
                        VALUES ($1, $2, $3, $4, $5)
                    """, doc_id, i+j, ct, None, f"pdf_{doc_id}")
                success += len(batch)
            
            await asyncio.sleep(0.3)
        
        print(f"   ✓ {success} chunks stored")
    
    await database.close()
    return len(chunks), success


async def main():
    print("="*60)
    print("FINAL IBMB PDF INGESTION")
    print("="*60)
    
    # Process each PDF
    pdfs = [
        ("IBMB Acquiring - Merchant Integration.pdf", "ibmb_acquiring_guide"),
        ("IBMB BO_User Manual_PA Portal_v1.0 (2)-1.pdf", "ibmb_pa_portal_manual"),
    ]
    
    for fname, doc_id in pdfs:
        path = os.path.join(PDF_DIR, fname)
        if os.path.exists(path):
            try:
                chunks, stored = await process_one(path, doc_id)
            except Exception as e:
                print(f"ERROR: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"Not found: {fname}")
    
    # Summary
    print("\n" + "="*60)
    print("FINAL STATUS")
    print("="*60)
    
    await database.connect()
    async with database.pool.acquire() as conn:
        docs = await conn.fetch("""
            SELECT d.doc_id, d.filename,
                   COUNT(tc.chunk_id) as total,
                   COUNT(tc.chunk_id) FILTER (WHERE tc.embedding IS NOT NULL) as embedded
            FROM documents d
            LEFT JOIN text_chunks tc ON d.doc_id = tc.doc_id
            GROUP BY d.doc_id, d.filename
            ORDER BY d.doc_id
        """)
        
        for d in docs:
            status = "✅" if d['embedded'] == d['total'] and d['total'] > 0 else "⚠️"
            print(f"{status} {d['doc_id']}")
            print(f"   File: {d['filename'][:50]}")
            print(f"   Chunks: {d['total']} total, {d['embedded']} embedded")
    
    await database.close()
    print("\n✅ All done!")


if __name__ == "__main__":
    asyncio.run(main())
