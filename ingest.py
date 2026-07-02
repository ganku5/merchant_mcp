#!/usr/bin/env python3
"""
Generic Ingestion System for Merchant MCP.

Automatically detects file type and extracts appropriate data:
- PDFs: Extract text, chunk, embed for semantic search
- CSVs: Extract structured data (error codes, endpoints)
- JSON/OpenAPI: Extract endpoint specifications
- Text/Markdown: Chunk and embed

Usage:
    python ingest.py <filepath> [options]
    python ingest.py /path/to/api-spec.pdf
    python ingest.py /path/to/errors.csv --type error-codes
    python ingest.py /path/to/openapi.json --type endpoints
"""

import argparse
import asyncio
import csv
import io
import json
import mimetypes
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Force unbuffered output for real-time feedback
sys.stdout.reconfigure(line_buffering=True)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

import pdfplumber
from src.utils.database import database
from src.utils.llm import llm_client
from src.tools.contextual_embedding_generator import ContextualEmbeddingGenerator


class FileTypeDetector:
    """Detect file type from content and extension."""
    
    @staticmethod
    def detect(filepath: str) -> Tuple[str, float]:
        """
        Detect file type and confidence.
        Returns: (file_type, confidence)
        """
        ext = Path(filepath).suffix.lower()
        mime, _ = mimetypes.guess_type(filepath)
        
        # Check by extension first
        if ext in ['.csv']:
            return ('csv', 0.9)
        elif ext in ['.json']:
            return ('json', 0.9)
        elif ext in ['.yaml', '.yml']:
            return ('yaml', 0.9)
        elif ext in ['.pdf']:
            return ('pdf', 0.95)
        elif ext in ['.md', '.markdown']:
            return ('markdown', 0.9)
        elif ext in ['.txt', '.text']:
            return ('text', 0.8)
        elif ext in ['.xlsx', '.xls']:
            return ('excel', 0.9)
        
        # Check MIME type
        if mime:
            if 'pdf' in mime:
                return ('pdf', 0.95)
            elif 'json' in mime:
                return ('json', 0.9)
            elif 'csv' in mime or 'spreadsheet' in mime:
                return ('csv', 0.85)
            elif 'text' in mime:
                return ('text', 0.7)
        
        # Peek at content
        try:
            with open(filepath, 'rb') as f:
                header = f.read(100)
                if header.startswith(b'%PDF'):
                    return ('pdf', 0.95)
                elif header.startswith(b'{') or header.startswith(b'['):
                    return ('json', 0.8)
                elif b',' in header and b'\n' in header:
                    return ('csv', 0.6)
        except:
            pass
        
        return ('unknown', 0.0)


class GenericIngester:
    """Generic file ingester that adapts to file type."""
    
    def __init__(self, skip_contextual: bool = False):
        self.results = {
            "documents": [],
            "endpoints": [],
            "error_codes": [],
            "chunks": 0
        }
        self.skip_contextual = skip_contextual
    
    async def ingest(self, filepath: str, doc_id: Optional[str] = None, 
                     force_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Ingest a file automatically detecting its type.
        
        Args:
            filepath: Path to file to ingest
            doc_id: Optional document ID (auto-generated if not provided)
            force_type: Force specific type (pdf, csv, json, endpoints, errors)
        
        Returns:
            Ingestion results summary
        """
        filepath = os.path.abspath(filepath)
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        
        # Determine file type
        if force_type:
            file_type = force_type
            confidence = 1.0
        else:
            file_type, confidence = FileTypeDetector.detect(filepath)
        
        print(f"📁 File: {os.path.basename(filepath)}")
        print(f"🔍 Detected type: {file_type} (confidence: {confidence:.0%})")
        print(f"📊 Size: {os.path.getsize(filepath):,} bytes")
        
        # Generate doc_id if not provided
        if not doc_id:
            doc_id = Path(filepath).stem.lower()
            doc_id = re.sub(r'[^a-z0-9_]', '_', doc_id)
            doc_id = re.sub(r'_+', '_', doc_id).strip('_')
        
        print(f"🏷️  Doc ID: {doc_id}\n")
        
        # Route to appropriate handler
        handlers = {
            'pdf': self._ingest_pdf,
            'csv': self._ingest_csv,
            'json': self._ingest_json,
            'yaml': self._ingest_yaml,
            'markdown': self._ingest_text,
            'text': self._ingest_text,
            'endpoints': self._ingest_csv,
            'errors': self._ingest_csv,
            'excel': self._ingest_csv,  # Convert excel to CSV-like processing
        }
        
        handler = handlers.get(file_type, self._ingest_generic)
        
        await database.connect()
        try:
            result = await handler(filepath, doc_id, file_type)
            await self._show_summary()
            return result
        finally:
            await database.close()
    
    async def _ingest_pdf(self, filepath: str, doc_id: str, file_type: str) -> Dict:
        """Ingest PDF for semantic search and endpoint extraction."""
        print("=" * 60)
        print("STEP 1: Extracting text from PDF")
        print("=" * 60)
        
        # Extract text
        text_parts = []
        with pdfplumber.open(filepath) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"\n--- Page {i+1} ---\n{page_text}")
        
        full_text = "\n".join(text_parts)
        full_text = self._clean_text(full_text)
        
        print(f"✓ Extracted {len(full_text):,} characters from {len(pdf.pages)} pages")
        
        # Step 1: Store for semantic search
        print("\n" + "=" * 60)
        print("STEP 2: Creating semantic search index")
        print("=" * 60)
        
        chunks = self._chunk_text(full_text)
        print(f"Created {len(chunks)} chunks")
        
        # Store document
        await database.insert_document(
            doc_id=doc_id,
            filename=os.path.basename(filepath),
            content=full_text[:100000],
            num_pages=len(pdf.pages),
            source_type='pdf'
        )
        
        # Delete old chunks
        async with database.pool.acquire() as conn:
            await conn.execute("DELETE FROM text_chunks WHERE doc_id = $1", doc_id)
        
        # Store chunks with embeddings
        embedded_count = 0
        for i in range(0, len(chunks), 3):
            batch = chunks[i:i+3]
            try:
                embeddings = await llm_client.embed(batch)
                for j, (chunk_text, embedding) in enumerate(zip(batch, embeddings)):
                    await database.insert_text_chunk(
                        doc_id=doc_id,
                        chunk_index=i + j,
                        chunk_text=chunk_text[:1500],
                        embedding=embedding,
                        namespace=f"pdf_{doc_id[:40]}"
                    )
                embedded_count += len(batch)
            except Exception as e:
                print(f"  ⚠️  Batch {i//3 + 1} failed: {e}")
                # Store without embeddings
                for j, chunk_text in enumerate(batch):
                    await database.insert_text_chunk(
                        doc_id=doc_id,
                        chunk_index=i + j,
                        chunk_text=chunk_text[:1500],
                        embedding=None,
                        namespace=f"pdf_{doc_id[:40]}"
                    )
            await asyncio.sleep(0.2)
        
        print(f"✓ Stored {len(chunks)} chunks ({embedded_count} with embeddings)")
        
        # Step 2: Generate contextual embeddings with prev/next chunk context
        if not self.skip_contextual:
            print("\n" + "=" * 60)
            print("STEP 3: Generating contextual embeddings with context windows")
            print("=" * 60)
            print("(Use --skip-contextual to skip this step for faster ingestion)")
            
            try:
                generator = ContextualEmbeddingGenerator()
                ctx_stats = await generator.process_document(doc_id)
                print(f"✓ Generated {ctx_stats['generated']} contextual embeddings")
                if ctx_stats['failed'] > 0:
                    print(f"  ⚠️  {ctx_stats['failed']} failed")
            except Exception as e:
                print(f"  ⚠️  Contextual embedding generation failed: {e}")
        else:
            print("\n⏩ Skipping contextual embedding generation (--skip-contextual)")
        
        # Step 4: Try to extract structured data (endpoints)
        print("\n" + "=" * 60)
        print("STEP 4: Extracting API endpoints (if present)")
        print("=" * 60)
        
        endpoints = await self._extract_endpoints_from_text(full_text, doc_id)
        
        # Step 5: Try to extract error codes
        print("\n" + "=" * 60)
        print("STEP 5: Extracting error codes (if present)")
        print("=" * 60)
        
        errors = await self._extract_errors_from_text(full_text, doc_id)
        
        self.results["documents"].append(doc_id)
        self.results["chunks"] += len(chunks)
        
        return {
            "doc_id": doc_id,
            "type": "pdf",
            "chars": len(full_text),
            "pages": len(pdf.pages),
            "chunks": len(chunks),
            "embedded": embedded_count,
            "endpoints_extracted": len(endpoints),
            "errors_extracted": len(errors)
        }
    
    async def _ingest_csv(self, filepath: str, doc_id: str, file_type: str) -> Dict:
        """Ingest CSV as error codes or endpoints."""
        print("=" * 60)
        print("PARSING CSV FILE")
        print("=" * 60)
        
        rows = []
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        
        print(f"✓ Found {len(rows)} rows")
        
        # Auto-detect content type
        sample_keys = list(rows[0].keys()) if rows else []
        print(f"Columns: {sample_keys}")
        
        # Detect if error codes or endpoints
        sample_keys_lower = [k.lower() for k in sample_keys]
        is_errors = any(k in sample_keys_lower for k in ['error codes', 'error_code', 'errorcode', 'code', 'error']) and \
                    any(k in sample_keys_lower for k in ['description', 'desc', 'message'])
        
        if file_type == "errors" or is_errors:
            return await self._ingest_error_csv(rows, doc_id, filepath)
        return await self._ingest_endpoint_csv(rows, doc_id, filepath)
    
    async def _ingest_error_csv(self, rows: List[Dict], doc_id: str, filepath: str) -> Dict:
        """Ingest CSV as error codes."""
        print("\nDetected: Error codes CSV")
        
        # Find relevant columns - also check for "Error Codes" (with space)
        code_candidates = ['error codes', 'error_code', 'errorcode', 'error codes', 'code', 'error']
        desc_candidates = ['description', 'desc', 'message', 'error_message', 'error description']
        
        code_col = self._find_column(rows[0].keys(), code_candidates)
        desc_col = self._find_column(rows[0].keys(), desc_candidates)
        
        if not code_col:
            print(f"❌ Could not find error code column. Available: {list(rows[0].keys())}")
            return {"error": "No code column found"}
        
        print(f"  Using column '{code_col}' for error codes")
        if desc_col:
            print(f"  Using column '{desc_col}' for descriptions")
        
        count = 0
        for row in rows:
            error_code = row.get(code_col, '').strip()
            description = row.get(desc_col, '').strip() if desc_col else ''
            
            if not error_code:
                continue
            
            # Determine category
            category = self._categorize_error(error_code, description)
            
            try:
                await database.insert_error_code(
                    error_code=error_code,
                    http_status=400,
                    category=category,
                    message=description[:200] if description else error_code,
                    description=description,
                    common_causes=[],
                    fix_suggestions=["See documentation for resolution"],
                    error_data={"source": "csv", "row": row},
                    source_doc_id=None  # No foreign key constraint
                )
                count += 1
            except Exception as e:
                print(f"  ⚠️  {error_code}: {e}")
        
        print(f"✓ Ingested {count} error codes")
        self.results["error_codes"].extend([r.get(code_col) for r in rows if r.get(code_col)])
        
        return {"doc_id": doc_id, "type": "error_codes", "count": count}
    
    async def _ingest_endpoint_csv(self, rows: List[Dict], doc_id: str, filepath: str) -> Dict:
        """Ingest CSV as endpoint definitions."""
        print("\nDetected: Endpoint definitions CSV")
        
        # Find columns
        name_col = self._find_column(rows[0].keys(), ['endpoint', 'name', 'api', 'path'])
        method_col = self._find_column(rows[0].keys(), ['method', 'http', 'verb'])
        path_col = self._find_column(rows[0].keys(), ['path', 'url', 'route'])
        desc_col = self._find_column(rows[0].keys(), ['description', 'desc'])
        
        count = 0
        for row in rows:
            endpoint_id = row.get(name_col, f"endpoint_{count}").strip()
            method = row.get(method_col, 'POST').strip().upper() if method_col else 'POST'
            path = row.get(path_col, '/').strip() if path_col else '/'
            desc = row.get(desc_col, '').strip() if desc_col else ''
            
            try:
                await database.insert_endpoint_spec(
                    endpoint_id=re.sub(r'[^a-z0-9_.]', '_', endpoint_id.lower()),
                    method=method,
                    path=path,
                    description=desc,
                    auth_type='api_key',
                    request_schema={"fields": []},
                    response_schema={"fields": []},
                    error_responses=[],
                    spec_data={"source": "csv", "row": row},
                    is_ground_truth=False,
                    source_doc_id=None  # No FK constraint
                )
                count += 1
            except Exception as e:
                print(f"  ⚠️  {endpoint_id}: {e}")
        
        print(f"✓ Ingested {count} endpoints")
        self.results["endpoints"].extend([r.get(name_col) for r in rows if r.get(name_col)])
        
        return {"doc_id": doc_id, "type": "endpoints", "count": count}

    async def _ingest_error_json(self, rows: List[Dict], doc_id: str, filepath: str) -> Dict:
        """Ingest JSON array as error codes."""
        count = 0
        for row in rows:
            if not isinstance(row, dict):
                continue

            error_code = str(row.get('error_code') or row.get('code') or row.get('error') or '').strip()
            description = str(row.get('description') or row.get('message') or '').strip()
            if not error_code:
                continue

            try:
                await database.insert_error_code(
                    error_code=error_code,
                    http_status=int(row.get('http_status') or row.get('status') or 400),
                    category=row.get('category') or self._categorize_error(error_code, description),
                    message=(row.get('message') or description or error_code)[:200],
                    description=description,
                    common_causes=row.get('common_causes') or [],
                    fix_suggestions=row.get('fix_suggestions') or [],
                    error_data={"source": "json", "row": row},
                    source_doc_id=None
                )
                count += 1
            except Exception as e:
                print(f"  ⚠️  {error_code}: {e}")

        print(f"✓ Ingested {count} error codes")
        self.results["error_codes"].extend([
            r.get('error_code') or r.get('code') for r in rows if isinstance(r, dict)
        ])

        return {"doc_id": doc_id, "type": "error_codes", "count": count}
    
    async def _ingest_json(self, filepath: str, doc_id: str, file_type: str) -> Dict:
        """Ingest JSON (OpenAPI spec or endpoint definitions)."""
        print("=" * 60)
        print("PARSING JSON FILE")
        print("=" * 60)
        
        with open(filepath) as f:
            data = json.load(f)
        
        # Detect if OpenAPI spec
        if file_type == 'errors':
            print("Detected: Error codes JSON")
            rows = data if isinstance(data, list) else data.get('errors', data.get('error_codes', []))
            if not isinstance(rows, list):
                rows = []
            return await self._ingest_error_json(rows, doc_id, filepath)
        elif file_type == 'endpoints' and isinstance(data, list):
            print("Detected: Endpoint list JSON")
            return await self._ingest_endpoint_list(data, doc_id, filepath)
        elif isinstance(data, dict) and ('openapi' in data or 'swagger' in data or 'paths' in data):
            print("Detected: OpenAPI/Swagger specification")
            return await self._ingest_openapi(data, doc_id, filepath)
        elif isinstance(data, list):
            print("Detected: Endpoint list JSON")
            return await self._ingest_endpoint_list(data, doc_id, filepath)
        else:
            print("Detected: Generic JSON - storing as document")
            return await self._ingest_generic_json(data, doc_id, filepath)
    
    async def _ingest_openapi(self, spec: Dict, doc_id: str, filepath: str) -> Dict:
        """Ingest OpenAPI specification."""
        paths = spec.get('paths', {})
        info = spec.get('info', {})
        
        print(f"API: {info.get('title', 'Unknown')}")
        print(f"Version: {info.get('version', 'unknown')}")
        print(f"Paths: {len(paths)}")
        
        count = 0
        for path, methods in paths.items():
            for method, operation in methods.items():
                if method.upper() not in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                    continue
                
                endpoint_id = operation.get('operationId', f"{method}_{path.replace('/', '_')}")
                
                # Extract schemas
                request_schema = self._extract_schema_from_operation(operation, 'requestBody')
                response_schema = self._extract_schema_from_operation(operation, 'responses')
                
                try:
                    await database.insert_endpoint_spec(
                        endpoint_id=endpoint_id,
                        method=method.upper(),
                        path=path,
                        description=operation.get('summary', operation.get('description', '')),
                        auth_type='bearer',
                        request_schema=request_schema,
                        response_schema=response_schema,
                        error_responses=self._extract_errors_from_operation(operation),
                        spec_data={"openapi": True, "operation": operation},
                        is_ground_truth=False,
                        source_doc_id=doc_id
                    )
                    count += 1
                    print(f"  ✓ {method.upper()} {path}")
                except Exception as e:
                    print(f"  ⚠️  {path}: {e}")
        
        self.results["endpoints"].append(doc_id)
        return {"doc_id": doc_id, "type": "openapi", "endpoints": count}
    
    async def _ingest_yaml(self, filepath: str, doc_id: str, file_type: str) -> Dict:
        """Ingest YAML (treat as text or convert to JSON)."""
        try:
            import yaml
            with open(filepath) as f:
                data = yaml.safe_load(f)
            
            # If it looks like OpenAPI, process as such
            if isinstance(data, dict) and ('openapi' in data or 'paths' in data):
                return await self._ingest_openapi(data, doc_id, filepath)
            else:
                # Store as text
                with open(filepath) as f:
                    text = f.read()
                return await self._ingest_text_direct(text, doc_id, filepath)
        except ImportError:
            print("PyYAML not installed, treating as text")
            with open(filepath) as f:
                text = f.read()
            return await self._ingest_text_direct(text, doc_id, filepath)
    
    async def _ingest_text(self, filepath: str, doc_id: str, file_type: str) -> Dict:
        """Ingest text/markdown file."""
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        
        return await self._ingest_text_direct(text, doc_id, filepath)
    
    async def _ingest_text_direct(self, text: str, doc_id: str, filepath: str) -> Dict:
        """Ingest text directly."""
        print("=" * 60)
        print("PROCESSING TEXT FILE")
        print("=" * 60)
        
        text = self._clean_text(text)
        print(f"✓ Read {len(text):,} characters")
        
        # Store document
        await database.insert_document(
            doc_id=doc_id,
            filename=os.path.basename(filepath),
            content=text[:100000],
            num_pages=1,
            source_type='text'
        )
        
        # Chunk and embed
        chunks = self._chunk_text(text)
        print(f"Created {len(chunks)} chunks")
        
        async with database.pool.acquire() as conn:
            await conn.execute("DELETE FROM text_chunks WHERE doc_id = $1", doc_id)
        
        embedded = 0
        for i in range(0, len(chunks), 3):
            batch = chunks[i:i+3]
            try:
                embeddings = await llm_client.embed(batch)
                for j, (chunk_text, embedding) in enumerate(zip(batch, embeddings)):
                    await database.insert_text_chunk(
                        doc_id=doc_id,
                        chunk_index=i + j,
                        chunk_text=chunk_text[:1500],
                        embedding=embedding,
                        namespace=f"text_{doc_id[:40]}"
                    )
                embedded += len(batch)
            except Exception as e:
                for j, chunk_text in enumerate(batch):
                    await database.insert_text_chunk(
                        doc_id=doc_id,
                        chunk_index=i + j,
                        chunk_text=chunk_text[:1500],
                        embedding=None,
                        namespace=f"text_{doc_id[:40]}"
                    )
            await asyncio.sleep(0.2)
        
        print(f"✓ Stored {len(chunks)} chunks ({embedded} with embeddings)")
        
        # Generate contextual embeddings with prev/next chunk context
        if not self.skip_contextual:
            print("\nGenerating contextual embeddings with context windows...")
            try:
                generator = ContextualEmbeddingGenerator()
                ctx_stats = await generator.process_document(doc_id)
                print(f"✓ Generated {ctx_stats['generated']} contextual embeddings")
                if ctx_stats['failed'] > 0:
                    print(f"  ⚠️  {ctx_stats['failed']} failed")
            except Exception as e:
                print(f"  ⚠️  Contextual embedding generation failed: {e}")
        else:
            print("\n⏩ Skipping contextual embedding generation (--skip-contextual)")
        
        self.results["documents"].append(doc_id)
        self.results["chunks"] += len(chunks)
        
        return {"doc_id": doc_id, "type": "text", "chunks": len(chunks), "embedded": embedded}
    
    async def _ingest_generic(self, filepath: str, doc_id: str, file_type: str) -> Dict:
        """Generic ingestion for unknown file types - try as text."""
        print(f"Unknown file type, attempting text extraction...")
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
            return await self._ingest_text_direct(text, doc_id, filepath)
        except Exception as e:
            print(f"❌ Cannot read file as text: {e}")
            return {"error": str(e)}
    
    async def _extract_endpoints_from_text(self, text: str, doc_id: str) -> List[str]:
        """Use LLM to extract endpoints from text."""
        # Only process if text is substantial
        if len(text) < 1000:
            return []
        
        # Take first 4000 chars for analysis
        sample = text[:4000]
        
        prompt = f"""Analyze this API documentation and extract endpoint definitions.

DOCUMENT SAMPLE:
{sample}

Does this document contain API endpoint specifications (URLs like /api/... or http methods like GET/POST)?

If YES, extract them as JSON array:
[{{
    "endpoint_id": "unique.identifier",
    "method": "POST",
    "path": "/api/v1/example",
    "description": "What this endpoint does"
}}]

If NO or unclear, return empty array: []

Return ONLY the JSON array, no explanation."""
        
        try:
            response = await llm_client.chat([{"role": "user", "content": prompt}], temperature=0.1)
            
            # Extract JSON
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                endpoints = json.loads(json_match.group())
                
                for ep in endpoints:
                    try:
                        await database.insert_endpoint_spec(
                            endpoint_id=ep.get('endpoint_id', 'unknown'),
                            method=ep.get('method', 'POST'),
                            path=ep.get('path', '/'),
                            description=ep.get('description', ''),
                            auth_type='api_key',
                            request_schema={"fields": []},
                            response_schema={"fields": []},
                            error_responses=[],
                            spec_data={"extracted_by_llm": True, "source_doc": doc_id},
                            is_ground_truth=False,
                            source_doc_id=doc_id
                        )
                        print(f"  ✓ {ep.get('method', 'POST')} {ep.get('path', '/')}")
                    except Exception as e:
                        print(f"  ⚠️  {ep.get('endpoint_id')}: {e}")
                
                return [ep.get('endpoint_id') for ep in endpoints]
        except Exception as e:
            print(f"  ⚠️  LLM extraction failed: {e}")
        
        return []
    
    async def _extract_errors_from_text(self, text: str, doc_id: str) -> List[str]:
        """Use LLM to extract error codes from text."""
        if len(text) < 1000:
            return []
        
        sample = text[:4000]
        
        prompt = f"""Analyze this document and extract error codes.

DOCUMENT SAMPLE:
{sample}

Does this document contain error codes (like ERR001, ERROR_XYZ, etc.) with descriptions?

If YES, extract them as JSON array:
[{{
    "error_code": "ERR001",
    "description": "What this error means"
}}]

If NO or unclear, return empty array: []

Return ONLY the JSON array, no explanation."""
        
        try:
            response = await llm_client.chat([{"role": "user", "content": prompt}], temperature=0.1)
            
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                errors = json.loads(json_match.group())
                
                for err in errors:
                    try:
                        await database.insert_error_code(
                            error_code=err.get('error_code', 'UNKNOWN'),
                            http_status=400,
                            category='system_error',
                            message=err.get('description', '')[:200],
                            description=err.get('description', ''),
                            common_causes=[],
                            fix_suggestions=[],
                            error_data={"extracted_by_llm": True, "source_doc": doc_id},
                            source_doc_id=doc_id
                        )
                    except Exception as e:
                        pass
                
                if errors:
                    print(f"  ✓ Extracted {len(errors)} error codes")
                
                return [e.get('error_code') for e in errors]
        except Exception as e:
            pass
        
        return []
    
    def _clean_text(self, text: str) -> str:
        """Clean text."""
        text = text.replace('\x00', '')
        text = re.sub(r' +', ' ', text)
        text = re.sub(r'\n\n\n+', '\n\n', text)
        return text.strip()
    
    def _chunk_text(self, text: str, size: int = 600, overlap: int = 100) -> List[str]:
        """Split text into chunks."""
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            piece = text[start:end].strip()
            if len(piece) > 30:
                chunks.append(piece[:1200])
            start = max(end - overlap, start + 1)
        return chunks
    
    def _find_column(self, keys, candidates):
        """Find column name from candidates."""
        keys_lower = {k.lower(): k for k in keys}
        for cand in candidates:
            if cand.lower() in keys_lower:
                return keys_lower[cand.lower()]
        return None
    
    def _categorize_error(self, error_code: str, description: str) -> str:
        """Categorize error code."""
        text = (error_code + " " + description).upper()
        if any(x in text for x in ['TIMEOUT', 'GATEWAY', 'NETWORK', 'UNAVAILABLE']):
            return 'retryable'
        elif any(x in text for x in ['INVALID', 'MISSING', 'REQUIRED', 'NOT_FOUND']):
            return 'merchant_action'
        elif any(x in text for x in ['DECLINED', 'REJECTED', 'BLOCKED', 'UNAUTHORIZED']):
            return 'terminal'
        return 'system_error'
    
    def _extract_schema_from_operation(self, operation: Dict, key: str) -> Dict:
        """Extract schema from OpenAPI operation."""
        if key == 'requestBody':
            body = operation.get('requestBody', {})
            content = body.get('content', {})
            json_content = content.get('application/json', {})
            return json_content.get('schema', {})
        elif key == 'responses':
            responses = operation.get('responses', {})
            success = responses.get('200', responses.get('201', {}))
            content = success.get('content', {})
            json_content = content.get('application/json', {})
            return json_content.get('schema', {})
        return {}
    
    def _extract_errors_from_operation(self, operation: Dict) -> List[Dict]:
        """Extract error responses from operation."""
        errors = []
        for code, resp in operation.get('responses', {}).items():
            if code.startswith('4') or code.startswith('5'):
                errors.append({
                    "error_code": f"HTTP_{code}",
                    "http_status": int(code),
                    "description": resp.get('description', '')
                })
        return errors
    
    async def _ingest_endpoint_list(self, data: List[Dict], doc_id: str, filepath: str) -> Dict:
        """Ingest list of endpoint definitions."""
        count = 0
        for item in data:
            try:
                await database.insert_endpoint_spec(
                    endpoint_id=item.get('endpoint_id', f"ep_{count}"),
                    method=item.get('method', 'POST'),
                    path=item.get('path', '/'),
                    description=item.get('description', ''),
                    auth_type=item.get('auth_type', 'api_key'),
                    request_schema=item.get('request_schema', {"fields": []}),
                    response_schema=item.get('response_schema', {"fields": []}),
                    error_responses=item.get('error_responses', []),
                    spec_data=item,
                    is_ground_truth=False,
                    source_doc_id=doc_id
                )
                count += 1
            except Exception as e:
                print(f"  ⚠️  {item.get('endpoint_id')}: {e}")
        
        self.results["endpoints"].append(doc_id)
        return {"doc_id": doc_id, "type": "endpoint_list", "count": count}
    
    async def _ingest_generic_json(self, data: Any, doc_id: str, filepath: str) -> Dict:
        """Store generic JSON as document."""
        text = json.dumps(data, indent=2)
        return await self._ingest_text_direct(text, doc_id, filepath)
    
    async def _show_summary(self):
        """Show final summary."""
        print("\n" + "=" * 60)
        print("INGESTION SUMMARY")
        print("=" * 60)
        
        stats = await self._get_db_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
    
    async def _get_db_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        async with database.pool.acquire() as conn:
            return {
                "Documents": await conn.fetchval("SELECT COUNT(*) FROM documents"),
                "Text chunks": await conn.fetchval("SELECT COUNT(*) FROM text_chunks"),
                "Embedded chunks": await conn.fetchval("SELECT COUNT(*) FROM text_chunks WHERE embedding IS NOT NULL"),
                "Contextual embeddings": await conn.fetchval("SELECT COUNT(*) FROM contextual_embeddings"),
                "Endpoints": await conn.fetchval("SELECT COUNT(*) FROM endpoint_specs"),
                "Error codes": await conn.fetchval("SELECT COUNT(*) FROM error_codes"),
            }


async def main():
    parser = argparse.ArgumentParser(
        description="Generic file ingestion for Merchant MCP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python ingest.py /path/to/spec.pdf
    python ingest.py /path/to/errors.csv
    python ingest.py /path/to/openapi.json
    python ingest.py /path/to/doc.md --doc-id my_doc
        """
    )
    parser.add_argument("filepath", help="Path to file to ingest")
    parser.add_argument("--doc-id", help="Custom document ID (auto-generated if not provided)")
    parser.add_argument("--type", choices=['pdf', 'csv', 'json', 'text', 'endpoints', 'errors'],
                       help="Force specific file type (auto-detected if not provided)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Preview what would be ingested without saving")
    parser.add_argument("--skip-contextual", action="store_true",
                       help="Skip contextual embedding generation (faster ingestion)")
    
    args = parser.parse_args()
    
    ingester = GenericIngester(skip_contextual=args.skip_contextual)
    
    try:
        result = await ingester.ingest(
            filepath=args.filepath,
            doc_id=args.doc_id,
            force_type=args.type
        )
        
        print("\n✅ Ingestion complete!")
        
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
