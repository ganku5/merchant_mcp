"""Fixed document ingestion pipeline with robust error handling."""

import asyncio
import json
import re
import subprocess
from pathlib import Path
from typing import List, Optional

from ..utils.database import database
from ..utils.llm import llm_client


class DocumentIngester:
    """Fixed ingestion pipeline with proper error handling."""
    
    CHUNK_SIZE = 800
    CHUNK_OVERLAP = 150
    EMBEDDING_BATCH_SIZE = 2
    MAX_CHUNK_LENGTH = 1500
    
    async def ingest_pdf(self, filepath: str, doc_id: Optional[str] = None) -> dict:
        """Ingest PDF with robust error handling."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {filepath}")
        
        if doc_id is None:
            doc_id = path.stem.lower().replace(' ', '_').replace('-', '_').replace('.', '_')
        
        # Extract text safely
        text = self._extract_pdf_text_safe(str(path))
        
        if not text or len(text.strip()) < 100:
            raise ValueError(f"Could not extract text from {filepath}")
        
        # Clean text
        text = self._clean_text(text)
        
        # Store document (updates if exists)
        await self._store_document(doc_id, path.name, text)
        
        # Delete old chunks
        await self._delete_old_chunks(doc_id)
        
        # Create smart chunks
        chunks = self._chunk_text_smart(text)
        
        # Store with embeddings
        chunk_count = await self._store_chunks_with_embeddings(doc_id, chunks)
        
        return {
            "doc_id": doc_id,
            "filename": path.name,
            "total_chars": len(text),
            "chunks_created": chunk_count
        }
    
    def _extract_pdf_text_safe(self, filepath: str) -> str:
        """Safely extract text using multiple methods."""
        # Try PyPDF2
        try:
            import PyPDF2
            text_parts = []
            with open(filepath, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for i, page in enumerate(reader.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(f"\n--- Page {i+1} ---\n{page_text}")
            result = "\n".join(text_parts)
            if len(result.strip()) > 100:
                return result
        except Exception:
            pass
        
        # Try pdfplumber
        try:
            import pdfplumber
            text_parts = []
            with pdfplumber.open(filepath) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(f"\n--- Page {i+1} ---\n{page_text}")
            result = "\n".join(text_parts)
            if len(result.strip()) > 100:
                return result
        except Exception:
            pass
        
        # Try pdftotext
        try:
            result = subprocess.run(
                ['pdftotext', filepath, '-'],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 and len(result.stdout.strip()) > 100:
                return result.stdout
        except Exception:
            pass
        
        # Fallback: binary read
        return self._binary_fallback(filepath)
    
    def _binary_fallback(self, filepath: str) -> str:
        """Extract printable characters from binary."""
        with open(filepath, 'rb') as f:
            content = f.read()
        
        printable = []
        for byte in content:
            if 32 <= byte < 127:
                printable.append(chr(byte))
            elif byte in (10, 13):
                printable.append(chr(byte))
            elif byte == 0:
                continue
            else:
                printable.append(' ')
        
        return ''.join(printable)
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text."""
        text = text.replace('\x00', '')
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = re.sub(r' +', ' ', text)
        text = re.sub(r'\n\n\n+', '\n\n', text)
        return text.strip()
    
    async def _store_document(self, doc_id: str, filename: str, content: str):
        """Store document."""
        await database.insert_document(
            doc_id=doc_id,
            filename=filename,
            content=content[:100000],
            num_pages=max(1, len(content) // 2500),
            source_type='pdf'
        )
    
    async def _delete_old_chunks(self, doc_id: str):
        """Remove old chunks."""
        async with database.pool.acquire() as conn:
            await conn.execute("DELETE FROM text_chunks WHERE doc_id = $1", doc_id)
    
    def _chunk_text_smart(self, text: str) -> List[str]:
        """Smart chunking preserving structure."""
        chunks = []
        
        # Split by page markers if present
        sections = re.split(r'\n--- Page \d+ ---\n', text)
        
        if len(sections) > 1:
            for section in sections:
                if section.strip():
                    chunks.extend(self._split_long_text(section.strip()))
        else:
            chunks = self._split_long_text(text)
        
        return [c for c in chunks if len(c.strip()) > 50]
    
    def _split_long_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks."""
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = min(start + self.CHUNK_SIZE, text_len)
            
            if end < text_len:
                search_start = max(start, end - 150)
                boundary = text.rfind('. ', search_start, end)
                if boundary > search_start:
                    end = boundary + 1
            
            chunk = text[start:end].strip()
            if chunk:
                if len(chunk) > self.MAX_CHUNK_LENGTH:
                    chunk = chunk[:self.MAX_CHUNK_LENGTH] + "..."
                chunks.append(chunk)
            
            start = end - self.CHUNK_OVERLAP
            if start >= end:
                break
        
        return chunks
    
    async def _store_chunks_with_embeddings(self, doc_id: str, chunks: List[str]) -> int:
        """Store chunks with embeddings."""
        count = 0
        
        for i in range(0, len(chunks), self.EMBEDDING_BATCH_SIZE):
            batch = chunks[i:i + self.EMBEDDING_BATCH_SIZE]
            
            try:
                embeddings = await llm_client.embed(batch)
                
                for j, (chunk_text, embedding) in enumerate(zip(batch, embeddings)):
                    await database.insert_text_chunk(
                        doc_id=doc_id,
                        chunk_index=i + j,
                        chunk_text=chunk_text[:self.MAX_CHUNK_LENGTH],
                        embedding=embedding,
                        namespace=f"pdf_{doc_id[:40]}"
                    )
                    count += 1
                    
            except Exception:
                # Store without embeddings
                for j, chunk_text in enumerate(batch):
                    await database.insert_text_chunk(
                        doc_id=doc_id,
                        chunk_index=i + j,
                        chunk_text=chunk_text[:self.MAX_CHUNK_LENGTH],
                        embedding=None,
                        namespace=f"pdf_{doc_id[:40]}"
                    )
                    count += 1
            
            await asyncio.sleep(0.1)
        
        return count


# Global instance
ingester = DocumentIngester()
