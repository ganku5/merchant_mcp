"""Full database operations with entity storage and vector search."""

import json
from typing import Any, List, Optional, Dict
import asyncpg
import numpy as np

from .config import Config


class FullDatabase:
    """Full database manager with entity storage."""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Create connection pool."""
        self.pool = await asyncpg.create_pool(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            database=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            min_size=5,
            max_size=20
        )
    
    async def close(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
    
    # Document operations
    async def insert_document(self, doc_id: str, filename: str, content: str, 
                              num_pages: int, total_chars: int):
        """Insert document record."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO documents (doc_id, filename, content, num_pages, total_chars)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (doc_id) DO UPDATE SET
                    content = EXCLUDED.content,
                    num_pages = EXCLUDED.num_pages,
                    total_chars = EXCLUDED.total_chars
            """, doc_id, filename, content, num_pages, total_chars)
    
    async def get_document(self, doc_id: str) -> Optional[Dict]:
        """Get document by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM documents WHERE doc_id = $1", doc_id
            )
            if row:
                return dict(row)
            return None
    
    # Text chunk operations
    async def insert_chunk(self, doc_id: str, chunk_index: int, 
                          chunk_text: str, embedding: List[float]):
        """Insert text chunk with embedding."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO text_chunks (doc_id, chunk_index, chunk_text, embedding)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (doc_id, chunk_index) DO UPDATE SET
                    chunk_text = EXCLUDED.chunk_text,
                    embedding = EXCLUDED.embedding
            """, doc_id, chunk_index, chunk_text, embedding)
    
    async def search_similar_chunks(self, query_embedding: List[float], 
                                    limit: int = 5) -> List[Dict]:
        """Search for similar chunks using cosine similarity."""
        async with self.pool.acquire() as conn:
            # Fetch all chunks and compute similarity
            # Note: For production, use pgvector for efficient search
            rows = await conn.fetch("""
                SELECT tc.*, d.filename 
                FROM text_chunks tc
                JOIN documents d ON tc.doc_id = d.doc_id
                WHERE tc.embedding IS NOT NULL
            """)
            
            results = []
            query_vec = np.array(query_embedding)
            
            for row in rows:
                if row['embedding']:
                    chunk_vec = np.array(row['embedding'])
                    # Cosine similarity
                    similarity = np.dot(query_vec, chunk_vec) / (
                        np.linalg.norm(query_vec) * np.linalg.norm(chunk_vec)
                    )
                    results.append({
                        'chunk_id': row['chunk_id'],
                        'doc_id': row['doc_id'],
                        'filename': row['filename'],
                        'chunk_text': row['chunk_text'][:500],
                        'similarity': float(similarity)
                    })
            
            # Sort by similarity and return top results
            results.sort(key=lambda x: x['similarity'], reverse=True)
            return results[:limit]
    
    # Endpoint operations
    async def insert_endpoint_spec(self, endpoint_id: str, method: str, path: str,
                                   description: str, auth_type: str, 
                                   request_schema: Dict, response_schema: Dict,
                                   error_responses: List, spec_data: Dict,
                                   source_doc_id: str = None):
        """Insert or update endpoint specification."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO endpoint_specs 
                (endpoint_id, method, path, description, auth_type, 
                 request_schema, response_schema, error_responses, 
                 spec_data, source_doc_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (endpoint_id) DO UPDATE SET
                    method = EXCLUDED.method,
                    path = EXCLUDED.path,
                    description = EXCLUDED.description,
                    request_schema = EXCLUDED.request_schema,
                    response_schema = EXCLUDED.response_schema,
                    spec_data = EXCLUDED.spec_data,
                    source_doc_id = EXCLUDED.source_doc_id
            """, endpoint_id, method, path, description, auth_type,
                json.dumps(request_schema), json.dumps(response_schema),
                json.dumps(error_responses), json.dumps(spec_data), source_doc_id)
    
    async def get_endpoint_spec(self, endpoint_id: str) -> Optional[Dict]:
        """Get endpoint specification."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM endpoint_specs WHERE endpoint_id = $1",
                endpoint_id
            )
            if row:
                return {
                    'endpoint_id': row['endpoint_id'],
                    'method': row['method'],
                    'path': row['path'],
                    'description': row['description'],
                    'auth_type': row['auth_type'],
                    'request_schema': row['request_schema'],
                    'response_schema': row['response_schema'],
                    'error_responses': row['error_responses'],
                    'spec_data': row['spec_data']
                }
            return None
    
    async def search_endpoints(self, query: str) -> List[Dict]:
        """Search endpoints by path or description."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT endpoint_id, method, path, description
                FROM endpoint_specs
                WHERE path ILIKE $1 OR description ILIKE $1
                ORDER BY path
            """, f"%{query}%")
            return [dict(r) for r in rows]
    
    # Error code operations
    async def insert_error_code(self, error_code: str, http_status: int,
                                category: str, message: str, description: str,
                                common_causes: List, fix_suggestions: List,
                                error_data: Dict, source_doc_id: str = None):
        """Insert or update error code."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO error_codes 
                (error_code, http_status, category, message, description,
                 common_causes, fix_suggestions, error_data, source_doc_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (error_code) DO UPDATE SET
                    category = EXCLUDED.category,
                    message = EXCLUDED.message,
                    description = EXCLUDED.description,
                    common_causes = EXCLUDED.common_causes,
                    fix_suggestions = EXCLUDED.fix_suggestions,
                    error_data = EXCLUDED.error_data
            """, error_code, http_status, category, message, description,
                json.dumps(common_causes), json.dumps(fix_suggestions),
                json.dumps(error_data), source_doc_id)
    
    async def get_error_code(self, error_code: str) -> Optional[Dict]:
        """Get error code details."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM error_codes WHERE error_code = $1",
                error_code
            )
            if row:
                return dict(row)
            return None
    
    # Integration flow operations
    async def insert_integration_flow(self, flow_id: str, name: str, 
                                      use_case: str, description: str,
                                      steps: List, flow_data: Dict,
                                      source_doc_id: str = None):
        """Insert or update integration flow."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO integration_flows 
                (flow_id, name, use_case, description, steps, flow_data, source_doc_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (flow_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    steps = EXCLUDED.steps,
                    flow_data = EXCLUDED.flow_data
            """, flow_id, name, use_case, description, 
                json.dumps(steps), json.dumps(flow_data), source_doc_id)
    
    async def get_integration_flow(self, flow_id: str) -> Optional[Dict]:
        """Get integration flow."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM integration_flows WHERE flow_id = $1",
                flow_id
            )
            if row:
                return {
                    'flow_id': row['flow_id'],
                    'name': row['name'],
                    'use_case': row['use_case'],
                    'description': row['description'],
                    'steps': row['steps']
                }
            return None
    
    async def get_flows_by_use_case(self, use_case: str) -> List[Dict]:
        """Get flows by use case."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM integration_flows WHERE use_case = $1",
                use_case
            )
            return [dict(r) for r in rows]
    
    # Statistics
    async def get_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        async with self.pool.acquire() as conn:
            return {
                'documents': await conn.fetchval("SELECT COUNT(*) FROM documents"),
                'chunks': await conn.fetchval("SELECT COUNT(*) FROM text_chunks"),
                'endpoints': await conn.fetchval("SELECT COUNT(*) FROM endpoint_specs"),
                'error_codes': await conn.fetchval("SELECT COUNT(*) FROM error_codes"),
                'flows': await conn.fetchval("SELECT COUNT(*) FROM integration_flows"),
            }


# Global instance
db_full = FullDatabase()
