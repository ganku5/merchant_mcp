#!/usr/bin/env python3
"""Ingest PDFs without embeddings (add embeddings separately)."""

import asyncio
import os
import re
import sys
sys.path.insert(0, '/home/ganesh/merchant_mcp')

from src.utils.database import database
import pdfplumber

PDF_DIR = "/home/ganesh/Downloads/ibmb"


def clean_text(text: str) -> str:
    """Clean extracted text."""
    text = text.replace('\x00', '')
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n\n\n+', '\n\n', text)
    return text.strip()


def create_chunks(text: str, chunk_size: int = 800, overlap: int = 150) -> list:
    """Split text into chunks."""
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = min(start + chunk_size, text_len)
        
        if end < text_len:
            search_start = max(start, end - 150)
            boundary = text.rfind('. ', search_start, end)
            if boundary > search_start:
                end = boundary + 1
        
        chunk = text[start:end].strip()
        if chunk and len(chunk) > 50:
            chunks.append(chunk[:1500])
        
        start = end - overlap
        if start >= end:
            break
    
    return chunks


async def ingest_simple(pdf_path: str, doc_id: str):
    """Simple ingestion - extract, chunk, store (no embeddings)."""
    print(f"\nProcessing: {os.path.basename(pdf_path)}")
    
    # Extract with pdfplumber
    print("  Extracting...")
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            txt = page.extract_text()
            if txt:
                text_parts.append(f"\n--- Page {i+1} ---\n{txt.strip()}")
    
    text = clean_text("\n".join(text_parts))
    print(f"  ✓ {len(text):,} chars")
    
    # Connect to DB
    await database.connect()
    
    async with database.pool.acquire() as conn:
        # Clear old
        await conn.execute("DELETE FROM text_chunks WHERE doc_id = $1", doc_id)
        await conn.execute("DELETE FROM documents WHERE doc_id = $1", doc_id)
        
        # Store document
        await conn.execute("""
            INSERT INTO documents (doc_id, filename, content, num_pages, total_chars, source_type)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, doc_id, os.path.basename(pdf_path), text[:100000],
             len(text_parts), len(text), 'pdf')
        
        # Create and store chunks (no embeddings)
        chunks = create_chunks(text)
        print(f"  Storing {len(chunks)} chunks...")
        
        for i, chunk_text in enumerate(chunks):
            await conn.execute("""
                INSERT INTO text_chunks (doc_id, chunk_index, chunk_text, embedding, namespace)
                VALUES ($1, $2, $3, $4, $5)
            """, doc_id, i, chunk_text, None, f"pdf_{doc_id}")
    
    await database.close()
    print(f"  ✓ Done: {len(chunks)} chunks")
    return len(chunks)


async def main():
    print("="*70)
    print("SIMPLE PDF INGESTION (No Embeddings)")
    print("="*70)
    
    files = [
        ("IBMB Acquiring - Merchant Integration.pdf", "ibmb_acquiring_guide"),
        ("IBMB BO_User Manual_PA Portal_v1.0 (2)-1.pdf", "ibmb_pa_portal_manual"),
    ]
    
    for fname, doc_id in files:
        path = os.path.join(PDF_DIR, fname)
        if os.path.exists(path):
            try:
                count = await ingest_simple(path, doc_id)
            except Exception as e:
                print(f"  ✗ Failed: {e}")
        else:
            print(f"  ✗ Not found: {fname}")
    
    # Show status
    print("\n" + "="*70)
    await database.connect()
    async with database.pool.acquire() as conn:
        docs = await conn.fetch("""
            SELECT d.doc_id, d.filename, COUNT(tc.chunk_id) as chunks
            FROM documents d
            LEFT JOIN text_chunks tc ON d.doc_id = tc.doc_id
            GROUP BY d.doc_id, d.filename
            ORDER BY d.doc_id
        """)
        print("Documents:")
        for d in docs:
            print(f"  • {d['doc_id']}: {d['chunks']} chunks ({d['filename'][:50]})")
    await database.close()
    print("\n✅ Ingestion complete!")


if __name__ == "__main__":
    asyncio.run(main())
