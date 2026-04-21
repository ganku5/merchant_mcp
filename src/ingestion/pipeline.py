"""Document ingestion pipeline with embeddings support."""

import hashlib
import json
import re
from pathlib import Path
from typing import List, Optional

from ..utils.database import database
from ..utils.llm import llm_client


class DocumentIngester:
    """Ingest documents with text chunking and embedding generation."""
    
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200
    
    async def ingest_pdf(self, filepath: str, doc_id: Optional[str] = None) -> dict:
        """Ingest a PDF file.
        
        Args:
            filepath: Path to PDF file
            doc_id: Optional document ID (default: derived from filename)
        
        Returns:
            Ingestion result with counts
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {filepath}")
        
        if doc_id is None:
            doc_id = path.stem.lower().replace(' ', '_').replace('-', '_')
        
        # Extract text from PDF
        text = self._extract_pdf_text(str(path))
        
        # Clean text - remove null bytes and invalid characters
        text = self._clean_text(text)
        
        if not text or len(text.strip()) < 100:
            raise ValueError(f"Could not extract meaningful text from {filepath}")
        
        # Store document
        await database.insert_document(
            doc_id=doc_id,
            filename=path.name,
            content=text,
            num_pages=self._estimate_pages(text),
            source_type='pdf'
        )
        
        # Chunk and store with embeddings
        chunks = self._chunk_text(text)
        chunk_count = await self._store_chunks_with_embeddings(doc_id, chunks)
        
        return {
            "doc_id": doc_id,
            "filename": path.name,
            "total_chars": len(text),
            "chunks_created": chunk_count
        }
    
    def _extract_pdf_text(self, filepath: str) -> str:
        """Extract text from PDF using available libraries."""
        # Try PyPDF2 first
        try:
            import PyPDF2
            text_parts = []
            with open(filepath, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            return "\n\n".join(text_parts)
        except Exception as e:
            print(f"PyPDF2 failed: {e}")
        
        # Try pdfplumber
        try:
            import pdfplumber
            text_parts = []
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            return "\n\n".join(text_parts)
        except Exception as e:
            print(f"pdfplumber failed: {e}")
        
        # Fallback: try to extract using pdftotext if available
        try:
            import subprocess
            result = subprocess.run(
                ['pdftotext', filepath, '-'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return result.stdout
        except:
            pass
        
        return ""
    
    def _clean_text(self, text: str) -> str:
        """Clean text for database storage."""
        if not text:
            return ""
        
        # Remove null bytes
        text = text.replace('\x00', '')
        
        # Remove control characters except newlines and tabs
        import unicodedata
        cleaned = []
        for char in text:
            if char == '\n' or char == '\t' or char == '\r':
                cleaned.append(char)
            elif unicodedata.category(char)[0] != 'C':  # Not a control character
                cleaned.append(char)
            else:
                cleaned.append(' ')  # Replace control chars with space
        
        text = ''.join(cleaned)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        return text.strip()
    
    def _estimate_pages(self, text: str) -> int:
        """Estimate page count from character count."""
        # Assume ~3000 chars per page
        return max(1, len(text) // 3000)
    
    def _chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks."""
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = min(start + self.CHUNK_SIZE, text_len)
            chunk = text[start:end]
            
            # Try to break at sentence boundary if not at end
            if end < text_len:
                # Look for sentence ending in last 100 chars
                last_part = chunk[-100:] if len(chunk) > 100 else chunk
                match = re.search(r'[.!?]\s+', last_part)
                if match:
                    # Adjust end to include this sentence
                    adjustment = len(last_part) - match.end()
                    end = end - adjustment
                    chunk = text[start:end]
            
            if chunk.strip():
                chunks.append(chunk.strip())
            
            start = end - self.CHUNK_OVERLAP
            if start >= end:
                start = end
        
        return chunks
    
    async def _store_chunks_with_embeddings(self, doc_id: str, chunks: List[str]) -> int:
        """Store chunks with embeddings."""
        count = 0
        
        # Process in batches
        batch_size = 5
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            
            try:
                # Generate embeddings
                embeddings = await llm_client.embed(batch)
                
                for j, (chunk_text, embedding) in enumerate(zip(batch, embeddings)):
                    chunk_index = i + j
                    await database.insert_text_chunk(
                        doc_id=doc_id,
                        chunk_index=chunk_index,
                        chunk_text=chunk_text[:2000],  # Limit chunk size
                        embedding=embedding,
                        namespace='pdf_' + doc_id[:50]  # Truncate namespace
                    )
                    count += 1
            except Exception as e:
                # Store without embedding on error
                print(f"Embedding generation failed for batch: {e}")
                for j, chunk_text in enumerate(batch):
                    chunk_index = i + j
                    await database.insert_text_chunk(
                        doc_id=doc_id,
                        chunk_index=chunk_index,
                        chunk_text=chunk_text[:2000],
                        embedding=None,
                        namespace='pdf_' + doc_id[:50]
                    )
                    count += 1
        
        return count
    
    async def ingest_openapi_spec(self, spec: dict, source: str = "openapi") -> dict:
        """Ingest OpenAPI specification."""
        paths = spec.get('paths', {})
        info = spec.get('info', {})
        
        endpoints_created = 0
        
        for path, methods in paths.items():
            for method, operation in methods.items():
                if method.upper() not in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                    continue
                
                endpoint_id = operation.get('operationId', f"{method}_{path.replace('/', '_')}")
                
                spec_data = {
                    "endpoint_id": endpoint_id,
                    "method": method.upper(),
                    "path": path,
                    "description": operation.get('summary', operation.get('description', '')),
                    "request_schema": self._extract_request_schema(operation),
                    "response_schema": self._extract_response_schema(operation),
                    "error_responses": self._extract_errors(operation),
                    "parameters": operation.get('parameters', []),
                    "tags": operation.get('tags', [])
                }
                
                await database.insert_endpoint_spec(
                    endpoint_id=endpoint_id,
                    method=method.upper(),
                    path=path,
                    description=spec_data['description'],
                    auth_type='bearer',
                    request_schema=spec_data['request_schema'],
                    response_schema=spec_data['response_schema'],
                    error_responses=spec_data['error_responses'],
                    spec_data=spec_data,
                    is_ground_truth=False
                )
                
                endpoints_created += 1
        
        return {
            "endpoints_created": endpoints_created,
            "source": source,
            "api_title": info.get('title', 'Unknown'),
            "api_version": info.get('version', 'unknown')
        }
    
    def _extract_request_schema(self, operation: dict) -> dict:
        """Extract request schema from operation."""
        request_body = operation.get('requestBody', {})
        content = request_body.get('content', {})
        json_content = content.get('application/json', {})
        schema = json_content.get('schema', {})
        
        return self._convert_schema(schema)
    
    def _extract_response_schema(self, operation: dict) -> dict:
        """Extract response schema from operation."""
        responses = operation.get('responses', {})
        success = responses.get('200', responses.get('201', {}))
        content = success.get('content', {})
        json_content = content.get('application/json', {})
        schema = json_content.get('schema', {})
        
        return self._convert_schema(schema)
    
    def _extract_errors(self, operation: dict) -> List[dict]:
        """Extract error responses."""
        errors = []
        responses = operation.get('responses', {})
        
        for code, response in responses.items():
            if code.startswith('4') or code.startswith('5'):
                errors.append({
                    "http_status": int(code),
                    "description": response.get('description', ''),
                    "error_code": self._infer_error_code(response)
                })
        
        return errors
    
    def _convert_schema(self, schema: dict) -> dict:
        """Convert OpenAPI schema to internal format."""
        fields = []
        
        properties = schema.get('properties', {})
        required = schema.get('required', [])
        
        for name, prop in properties.items():
            field = {
                "field_name": name,
                "json_path": f"$..{name}",
                "field_type": self._map_type(prop.get('type', 'string')),
                "required": name in required,
                "description": prop.get('description', ''),
                "example": prop.get('example'),
                "format": prop.get('format'),
                "valid_values": prop.get('enum'),
                "constraints": self._extract_constraints(prop)
            }
            fields.append(field)
        
        return {"fields": fields}
    
    def _map_type(self, openapi_type: str) -> str:
        """Map OpenAPI type to internal type."""
        mapping = {
            'string': 'string',
            'integer': 'integer',
            'number': 'number',
            'boolean': 'boolean',
            'array': 'array',
            'object': 'object'
        }
        return mapping.get(openapi_type, 'string')
    
    def _extract_constraints(self, prop: dict) -> Optional[dict]:
        """Extract field constraints."""
        constraints = {}
        
        if 'minimum' in prop:
            constraints['min_value'] = prop['minimum']
        if 'maximum' in prop:
            constraints['max_value'] = prop['maximum']
        if 'minLength' in prop:
            constraints['min_length'] = prop['minLength']
        if 'maxLength' in prop:
            constraints['max_length'] = prop['maxLength']
        if 'pattern' in prop:
            constraints['pattern'] = prop['pattern']
        
        return constraints if constraints else None
    
    def _infer_error_code(self, response: dict) -> str:
        """Infer error code from response."""
        desc = response.get('description', '').upper()
        desc_clean = re.sub(r'[^A-Z0-9]', '_', desc)
        return desc_clean[:50] or 'ERROR'


# Global ingester instance
ingester = DocumentIngester()
