#!/usr/bin/env python3
"""Fix and re-run document ingestion with proper embeddings."""

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, '/home/ganesh/merchant_mcp')

from src.utils.database import database
from src.utils.llm import llm_client


class FixedDocumentIngester:
    """Fixed ingestion pipeline with proper error handling and batching."""
    
    CHUNK_SIZE = 800  # Reduced from 1000
    CHUNK_OVERLAP = 150  # Reduced from 200
    EMBEDDING_BATCH_SIZE = 2  # Small batches to avoid memory issues
    MAX_CHUNK_LENGTH = 1500  # Limit chunk text size
    
    async def ingest_pdf_robust(self, filepath: str, doc_id: Optional[str] = None) -> dict:
        """Robust PDF ingestion with progress tracking."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {filepath}")
        
        if doc_id is None:
            doc_id = path.stem.lower().replace(' ', '_').replace('-', '_').replace('.', '_')
        
        print(f"📄 Processing: {path.name}")
        print(f"   Doc ID: {doc_id}")
        
        # Step 1: Extract text
        print("   Step 1: Extracting text...")
        text = self._extract_pdf_text_safe(str(path))
        
        if not text or len(text.strip()) < 100:
            raise ValueError(f"Could not extract meaningful text from {filepath}")
        
        print(f"   ✓ Extracted {len(text)} characters")
        
        # Step 2: Clean text
        print("   Step 2: Cleaning text...")
        text = self._clean_text(text)
        print(f"   ✓ Cleaned to {len(text)} characters")
        
        # Step 3: Store document (delete old if exists)
        print("   Step 3: Storing document...")
        await self._store_document_safe(doc_id, path.name, text)
        print("   ✓ Document stored")
        
        # Step 4: Delete old chunks if any
        print("   Step 4: Cleaning old chunks...")
        await self._delete_old_chunks(doc_id)
        print("   ✓ Old chunks removed")
        
        # Step 5: Chunk text
        print("   Step 5: Chunking text...")
        chunks = self._chunk_text_smart(text)
        print(f"   ✓ Created {len(chunks)} chunks")
        
        # Step 6: Store chunks with embeddings
        print("   Step 6: Generating embeddings and storing chunks...")
        chunk_count = await self._store_chunks_with_embeddings_safe(doc_id, chunks)
        print(f"   ✓ Stored {chunk_count} chunks with embeddings")
        
        return {
            "doc_id": doc_id,
            "filename": path.name,
            "total_chars": len(text),
            "chunks_created": chunk_count,
            "status": "success"
        }
    
    def _extract_pdf_text_safe(self, filepath: str) -> str:
        """Safely extract text from PDF."""
        text_parts = []
        
        # Try multiple methods in order
        methods = [
            ("PyPDF2", self._try_pypdf2),
            ("pdfplumber", self._try_pdfplumber),
            ("pdftotext", self._try_pdftotext),
        ]
        
        for name, method in methods:
            try:
                print(f"      Trying {name}...")
                result = method(filepath)
                if result and len(result.strip()) > 100:
                    print(f"      ✓ {name} succeeded")
                    return result
            except Exception as e:
                print(f"      ✗ {name} failed: {e}")
                continue
        
        # Final fallback: read as binary and extract printable chars
        print("      Using binary fallback...")
        return self._binary_fallback(filepath)
    
    def _try_pypdf2(self, filepath: str) -> str:
        """Try PyPDF2 extraction."""
        try:
            import PyPDF2
            text_parts = []
            with open(filepath, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for i, page in enumerate(reader.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(f"\n--- Page {i+1} ---\n{page_text}")
            return "\n".join(text_parts)
        except ImportError:
            raise ImportError("PyPDF2 not installed")
    
    def _try_pdfplumber(self, filepath: str) -> str:
        """Try pdfplumber extraction."""
        try:
            import pdfplumber
            text_parts = []
            with pdfplumber.open(filepath) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(f"\n--- Page {i+1} ---\n{page_text}")
            return "\n".join(text_parts)
        except ImportError:
            raise ImportError("pdfplumber not installed")
    
    def _try_pdftotext(self, filepath: str) -> str:
        """Try pdftotext command-line tool."""
        import subprocess
        result = subprocess.run(
            ['pdftotext', filepath, '-'],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return result.stdout
        raise RuntimeError("pdftotext failed")
    
    def _binary_fallback(self, filepath: str) -> str:
        """Last resort: extract printable characters from binary."""
        with open(filepath, 'rb') as f:
            content = f.read()
        
        # Extract printable ASCII and common Unicode
        printable = []
        for byte in content:
            if 32 <= byte < 127 or byte in (10, 13):  # ASCII printable + newlines
                printable.append(chr(byte))
            elif byte == 0:  # Skip null bytes
                continue
            else:
                printable.append(' ')  # Replace non-printable with space
        
        return ''.join(printable)
    
    def _clean_text(self, text: str) -> str:
        """Clean text for storage."""
        # Remove null bytes
        text = text.replace('\x00', '')
        
        # Normalize newlines
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove excessive whitespace but preserve structure
        text = re.sub(r' +', ' ', text)  # Multiple spaces -> single
        text = re.sub(r'\n\n\n+', '\n\n', text)  # 3+ newlines -> 2
        
        return text.strip()
    
    async def _store_document_safe(self, doc_id: str, filename: str, content: str):
        """Store or update document record."""
        # Delete existing document
        await database.insert_document(
            doc_id=doc_id,
            filename=filename,
            content=content[:100000],  # Limit content size
            num_pages=max(1, len(content) // 2500),
            source_type='pdf'
        )
    
    async def _delete_old_chunks(self, doc_id: str):
        """Delete old chunks for this document."""
        async with database.pool.acquire() as conn:
            await conn.execute("DELETE FROM text_chunks WHERE doc_id = $1", doc_id)
    
    def _chunk_text_smart(self, text: str) -> List[str]:
        """Smart chunking that preserves structure."""
        chunks = []
        
        # First try to split by major sections (marked by --- Page or headers)
        sections = re.split(r'\n--- Page \d+ ---\n', text)
        
        if len(sections) > 1:
            # We have page markers - process each page
            for i, section in enumerate(sections):
                if not section.strip():
                    continue
                # Further split long sections
                section_chunks = self._split_long_text(section.strip())
                chunks.extend(section_chunks)
        else:
            # No page markers - use sliding window
            chunks = self._split_long_text(text)
        
        return [c for c in chunks if len(c.strip()) > 50]  # Filter tiny chunks
    
    def _split_long_text(self, text: str) -> List[str]:
        """Split long text into chunks."""
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = min(start + self.CHUNK_SIZE, text_len)
            
            # Try to break at a natural boundary (period + space)
            if end < text_len:
                # Look for sentence boundary in last 150 chars
                search_start = max(start, end - 150)
                boundary = text.rfind('. ', search_start, end)
                if boundary > search_start:
                    end = boundary + 1  # Include the period
            
            chunk = text[start:end].strip()
            if chunk:
                # Truncate if too long
                if len(chunk) > self.MAX_CHUNK_LENGTH:
                    chunk = chunk[:self.MAX_CHUNK_LENGTH] + "..."
                chunks.append(chunk)
            
            # Move start with overlap
            start = end - self.CHUNK_OVERLAP
            if start >= end or start >= text_len:
                break
        
        return chunks
    
    async def _store_chunks_with_embeddings_safe(self, doc_id: str, chunks: List[str]) -> int:
        """Store chunks with embeddings, using small batches."""
        count = 0
        total = len(chunks)
        
        for i in range(0, len(chunks), self.EMBEDDING_BATCH_SIZE):
            batch = chunks[i:i + self.EMBEDDING_BATCH_SIZE]
            batch_num = i // self.EMBEDDING_BATCH_SIZE + 1
            total_batches = (len(chunks) + self.EMBEDDING_BATCH_SIZE - 1) // self.EMBEDDING_BATCH_SIZE
            
            print(f"      Batch {batch_num}/{total_batches} (chunks {i+1}-{min(i+len(batch), total)})...")
            
            try:
                # Generate embeddings
                embeddings = await llm_client.embed(batch)
                
                # Store each chunk with its embedding
                for j, (chunk_text, embedding) in enumerate(zip(batch, embeddings)):
                    chunk_index = i + j
                    await database.insert_text_chunk(
                        doc_id=doc_id,
                        chunk_index=chunk_index,
                        chunk_text=chunk_text[:self.MAX_CHUNK_LENGTH],
                        embedding=embedding,
                        namespace=f"pdf_{doc_id[:40]}"
                    )
                    count += 1
                
                print(f"        ✓ Stored {len(batch)} chunks")
                
            except Exception as e:
                print(f"        ⚠️ Embedding failed: {e}")
                # Store without embedding as fallback
                for j, chunk_text in enumerate(batch):
                    chunk_index = i + j
                    await database.insert_text_chunk(
                        doc_id=doc_id,
                        chunk_index=chunk_index,
                        chunk_text=chunk_text[:self.MAX_CHUNK_LENGTH],
                        embedding=None,
                        namespace=f"pdf_{doc_id[:40]}"
                    )
                    count += 1
                print(f"        ⚠️ Stored {len(batch)} chunks without embeddings")
            
            # Small delay to prevent rate limiting
            await asyncio.sleep(0.1)
        
        return count


async def main():
    """Main entry point."""
    print("="*70)
    print("FIXING DOCUMENT INGESTION PIPELINE")
    print("="*70)
    
    await database.connect()
    
    ingester = FixedDocumentIngester()
    
    # PDFs to ingest
    pdfs = [
        ("/home/ganesh/Downloads/ibmb/[Axis] IBMB Bank Server API Specifications.pdf", "ibmb_axis_api_specs"),
        ("/home/ganesh/Downloads/ibmb/IBMB Acquiring - Merchant Integration.pdf", "ibmb_acquiring_guide"),
        ("/home/ganesh/Downloads/ibmb/IBMB BO_User Manual_PA Portal_v1.0 (2)-1.pdf", "ibmb_pa_portal_manual"),
    ]
    
    results = []
    
    for filepath, doc_id in pdfs:
        print(f"\n{'='*70}")
        try:
            result = await ingester.ingest_pdf_robust(filepath, doc_id)
            results.append((doc_id, True, result))
        except Exception as e:
            print(f"❌ Failed: {e}")
            results.append((doc_id, False, str(e)))
    
    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print("="*70)
    
    for doc_id, success, result in results:
        status = "✅" if success else "❌"
        if success:
            print(f"{status} {doc_id}: {result['chunks_created']} chunks")
        else:
            print(f"{status} {doc_id}: {result}")
    
    # Verify in database
    print(f"\n{'='*70}")
    print("DATABASE VERIFICATION")
    print("="*70)
    
    async with database.pool.acquire() as conn:
        # Documents
        docs = await conn.fetch("SELECT doc_id, total_chars FROM documents ORDER BY doc_id")
        print(f"\nDocuments: {len(docs)}")
        for d in docs:
            print(f"  • {d['doc_id']}: {d['total_chars']} chars")
        
        # Chunks
        chunks = await conn.fetch("""
            SELECT doc_id, COUNT(*) as cnt, 
                   COUNT(*) FILTER (WHERE embedding IS NOT NULL) as with_embed
            FROM text_chunks 
            GROUP BY doc_id
            ORDER BY doc_id
        """)
        print(f"\nChunks: {sum(c['cnt'] for c in chunks)} total")
        for c in chunks:
            pct = (c['with_embed'] / c['cnt'] * 100) if c['cnt'] > 0 else 0
            print(f"  • {c['doc_id']}: {c['cnt']} chunks ({pct:.0f}% with embeddings)")
    
    await database.close()
    print("\n✅ Done!")


if __name__ == "__main__":
    asyncio.run(main())
