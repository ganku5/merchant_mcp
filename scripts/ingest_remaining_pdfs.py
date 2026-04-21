#!/usr/bin/env python3
"""Ingest remaining PDFs with robust extraction methods."""

import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, '/home/ganesh/merchant_mcp')

from src.utils.database import database
from src.utils.llm import llm_client


PDF_DIR = "/home/ganesh/Downloads/ibmb"


async def extract_with_pdfplumber(pdf_path: str) -> str:
    """Extract using pdfplumber - handles complex layouts."""
    import pdfplumber
    
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text and text.strip():
                text_parts.append(f"\n--- Page {i+1} ---\n{text.strip()}")
    
    return "\n".join(text_parts)


async def extract_with_pikepdf_pdfminer(pdf_path: str) -> str:
    """Extract using pikepdf + pdfminer for better text extraction."""
    from pdfminer.high_level import extract_text
    from pdfminer.layout import LAParams
    
    # Extract with layout analysis
    laparams = LAParams(
        line_margin=0.5,
        word_margin=0.1,
        char_margin=2.0
    )
    
    text = extract_text(pdf_path, laparams=laparams)
    return text


async def extract_with_pdftotext(pdf_path: str) -> str:
    """Extract using pdftotext command line tool."""
    result = subprocess.run(
        ['pdftotext', '-layout', pdf_path, '-'],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    if result.returncode == 0:
        return result.stdout
    raise RuntimeError(f"pdftotext failed: {result.stderr}")


async def extract_pdf_robust(pdf_path: str, doc_id: str) -> str:
    """Try multiple extraction methods."""
    methods = [
        ("pdfplumber", extract_with_pdfplumber),
        ("pikepdf+pdfminer", extract_with_pikepdf_pdfminer),
        ("pdftotext", extract_with_pdftotext),
    ]
    
    for name, method in methods:
        try:
            print(f"  Trying {name}...")
            text = await method(pdf_path)
            if text and len(text.strip()) > 500:
                print(f"  ✓ {name} succeeded ({len(text)} chars)")
                return text
        except Exception as e:
            print(f"  ✗ {name} failed: {e}")
            continue
    
    raise ValueError(f"All extraction methods failed for {pdf_path}")


def clean_text(text: str) -> str:
    """Clean extracted text."""
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Normalize whitespace
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
        
        # Try to break at sentence boundary
        if end < text_len:
            search_start = max(start, end - 150)
            boundary = text.rfind('. ', search_start, end)
            if boundary > search_start:
                end = boundary + 1
        
        chunk = text[start:end].strip()
        if chunk and len(chunk) > 50:
            chunks.append(chunk[:1500])  # Limit chunk size
        
        start = end - overlap
        if start >= end:
            break
    
    return chunks


async def ingest_pdf_file(pdf_path: str, doc_id: str):
    """Ingest a single PDF file."""
    print(f"\n{'='*70}")
    print(f"Processing: {os.path.basename(pdf_path)}")
    print(f"Doc ID: {doc_id}")
    print('='*70)
    
    # Step 1: Extract text
    print("\n1. Extracting text...")
    extracted_text = await extract_pdf_robust(pdf_path, doc_id)
    cleaned_text = clean_text(extracted_text)
    print(f"   Extracted {len(cleaned_text):,} characters")
    
    # Step 2: Store document
    print("\n2. Storing document...")
    await database.connect()
    
    async with database.pool.acquire() as conn:
        # Delete old document and chunks
        await conn.execute("DELETE FROM text_chunks WHERE doc_id = $1", doc_id)
        await conn.execute("DELETE FROM documents WHERE doc_id = $1", doc_id)
        
        # Insert document
        await conn.execute("""
            INSERT INTO documents (doc_id, filename, content, num_pages, total_chars, source_type)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, doc_id, os.path.basename(pdf_path), cleaned_text[:100000], 
             max(1, len(cleaned_text) // 2500), len(cleaned_text), 'pdf')
    
    print(f"   Document stored")
    
    # Step 3: Create chunks
    print("\n3. Creating chunks...")
    chunks = create_chunks(cleaned_text)
    print(f"   Created {len(chunks)} chunks")
    
    # Step 4: Store chunks with embeddings
    print("\n4. Generating embeddings and storing chunks...")
    
    async with database.pool.acquire() as conn:
        success_count = 0
        
        for i in range(0, len(chunks), 5):  # Batch size 5
            batch = chunks[i:i+5]
            
            try:
                # Generate embeddings
                embeddings = await llm_client.embed(batch)
                
                # Store with embeddings
                for j, (chunk_text, embedding) in enumerate(zip(batch, embeddings)):
                    await conn.execute("""
                        INSERT INTO text_chunks (doc_id, chunk_index, chunk_text, embedding, namespace)
                        VALUES ($1, $2, $3, $4::jsonb, $5)
                    """, doc_id, i + j, chunk_text, json.dumps(embedding), f"pdf_{doc_id}")
                
                success_count += len(batch)
                print(f"   Batch {i//5 + 1}: {len(batch)} chunks embedded ✓")
                
            except Exception as e:
                print(f"   Batch {i//5 + 1} failed: {e}")
                # Store without embeddings
                for j, chunk_text in enumerate(batch):
                    await conn.execute("""
                        INSERT INTO text_chunks (doc_id, chunk_index, chunk_text, embedding, namespace)
                        VALUES ($1, $2, $3, $4, $5)
                    """, doc_id, i + j, chunk_text, None, f"pdf_{doc_id}")
                success_count += len(batch)
            
            await asyncio.sleep(0.2)
    
    await database.close()
    
    return {
        "doc_id": doc_id,
        "filename": os.path.basename(pdf_path),
        "chars": len(text),
        "chunks": len(chunks),
        "status": "success"
    }


async def main():
    """Main entry point."""
    print("="*70)
    print("INGESTING REMAINING IBMB PDFs")
    print("="*70)
    
    pdfs = [
        (os.path.join(PDF_DIR, "IBMB Acquiring - Merchant Integration.pdf"), "ibmb_acquiring_guide"),
        (os.path.join(PDF_DIR, "IBMB BO_User Manual_PA Portal_v1.0 (2)-1.pdf"), "ibmb_pa_portal_manual"),
    ]
    
    results = []
    
    for pdf_path, doc_id in pdfs:
        if not os.path.exists(pdf_path):
            print(f"\n⚠️ File not found: {pdf_path}")
            continue
        
        try:
            result = await ingest_pdf_file(pdf_path, doc_id)
            results.append((doc_id, True, result))
        except Exception as e:
            print(f"\n❌ FAILED: {e}")
            import traceback
            traceback.print_exc()
            results.append((doc_id, False, str(e)))
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    for doc_id, success, result in results:
        if success:
            print(f"✅ {doc_id}: {result['chunks']} chunks from {result['chars']:,} chars")
        else:
            print(f"❌ {doc_id}: {result}")
    
    # Show all embedded files
    await database.connect()
    async with database.pool.acquire() as conn:
        docs = await conn.fetch("""
            SELECT d.doc_id, d.filename,
                   COUNT(tc.chunk_id) as total_chunks,
                   COUNT(tc.chunk_id) FILTER (WHERE tc.embedding IS NOT NULL) as embedded
            FROM documents d
            LEFT JOIN text_chunks tc ON d.doc_id = tc.doc_id
            GROUP BY d.doc_id, d.filename
            ORDER BY d.doc_id
        """)
        
        print(f"\nAll Documents ({len(docs)}):")
        for d in docs:
            status = "✅" if d['embedded'] == d['total_chunks'] and d['total_chunks'] > 0 else "⚠️"
            print(f"  {status} {d['doc_id']}: {d['total_chunks']} chunks, {d['embedded']} embedded")
    
    await database.close()
    print("\n✅ Done!")


if __name__ == "__main__":
    asyncio.run(main())
