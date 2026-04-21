"""Database connection and operations."""

import json
from typing import Any, Optional
import asyncpg
from pgvector.asyncpg import register_vector

from .config import Config


class Database:
    """Database manager with pgvector support."""
    
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
        
        # Register pgvector extension
        async with self.pool.acquire() as conn:
            await register_vector(conn)
    
    async def init_schema(self):
        """Initialize database schema."""
        async with self.pool.acquire() as conn:
            # Enable pgvector
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            
            # Endpoint specs table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS endpoint_specs (
                    endpoint_id TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    spec_data JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Error codes table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS error_codes (
                    error_code TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    error_data JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Webhook events table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS webhook_events (
                    event_type TEXT PRIMARY KEY,
                    payload_schema JSONB NOT NULL,
                    sig_algorithm TEXT NOT NULL,
                    event_data JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Integration flows table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS integration_flows (
                    flow_id TEXT PRIMARY KEY,
                    steps JSONB NOT NULL,
                    version TEXT NOT NULL,
                    flow_data JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Code templates table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS code_templates (
                    template_id TEXT PRIMARY KEY,
                    language TEXT NOT NULL,
                    endpoint_id TEXT,
                    code_text TEXT NOT NULL,
                    template_data JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Known issues table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS known_issues (
                    issue_id TEXT PRIMARY KEY,
                    pattern TEXT NOT NULL,
                    resolution TEXT NOT NULL,
                    category TEXT,
                    affected_endpoints JSONB,
                    issue_data JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Test scenarios table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS test_scenarios (
                    scenario_id TEXT PRIMARY KEY,
                    flow_type TEXT NOT NULL,
                    input_data JSONB NOT NULL,
                    expected_output JSONB NOT NULL,
                    scenario_data JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Embeddings table with pgvector
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    id SERIAL PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    embedding vector(768),
                    chunk_text TEXT NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(namespace, entity_id)
                )
            """)
            
            # Source documents table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS source_documents (
                    doc_id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    raw_content TEXT,
                    hash TEXT NOT NULL,
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create HNSW index for embeddings
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS embeddings_hnsw_idx 
                ON embeddings USING hnsw (embedding vector_cosine_ops)
            """)
            
            # Create namespace index
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS embeddings_namespace_idx 
                ON embeddings(namespace)
            """)
    
    async def insert_endpoint_spec(self, endpoint_id: str, version: str, spec_data: dict):
        """Insert or update endpoint spec."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO endpoint_specs (endpoint_id, version, spec_data, updated_at)
                VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
                ON CONFLICT (endpoint_id) DO UPDATE SET
                    version = EXCLUDED.version,
                    spec_data = EXCLUDED.spec_data,
                    updated_at = CURRENT_TIMESTAMP
            """, endpoint_id, version, json.dumps(spec_data))
    
    async def get_endpoint_spec(self, endpoint_id: str) -> Optional[dict]:
        """Get endpoint spec by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT spec_data FROM endpoint_specs WHERE endpoint_id = $1",
                endpoint_id
            )
            return json.loads(row['spec_data']) if row else None
    
    async def insert_embedding(self, namespace: str, entity_id: str, 
                                embedding: list[float], chunk_text: str,
                                metadata: dict = None):
        """Insert embedding vector."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO embeddings (namespace, entity_id, embedding, chunk_text, metadata)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (namespace, entity_id) DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    chunk_text = EXCLUDED.chunk_text,
                    metadata = EXCLUDED.metadata,
                    created_at = CURRENT_TIMESTAMP
            """, namespace, entity_id, embedding, chunk_text, json.dumps(metadata or {}))
    
    async def search_embeddings(self, namespace: str, query_embedding: list[float],
                                 limit: int = 5) -> list[dict]:
        """Search embeddings by cosine similarity."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT entity_id, chunk_text, metadata,
                       1 - (embedding <=> $1::vector) as similarity
                FROM embeddings
                WHERE namespace = $2
                ORDER BY embedding <=> $1::vector
                LIMIT $3
            """, query_embedding, namespace, limit)
            
            return [
                {
                    'entity_id': r['entity_id'],
                    'chunk_text': r['chunk_text'],
                    'metadata': json.loads(r['metadata']),
                    'similarity': r['similarity']
                }
                for r in rows
            ]
    
    async def close(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()


# Global database instance
db = Database()
