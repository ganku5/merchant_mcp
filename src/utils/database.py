"""Unified database layer for all MCP tools."""

import json
import math
import re
from typing import Any, Dict, List, Optional
import asyncpg
from pgvector.asyncpg import register_vector

from .config import Config


def _parse_json(val):
    """Parse JSON value from database."""
    if val is None:
        return None
    if isinstance(val, str):
        try:
            return json.loads(val)
        except:
            return val
    # Already a dict/list from asyncpg
    return val


class Database:
    """Unified database with connection pooling and all required operations."""
    
    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Create and initialize connection pool."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                database=Config.DB_NAME,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            
            # Try to register pgvector (optional)
            try:
                async with self._pool.acquire() as conn:
                    await register_vector(conn)
            except Exception:
                # pgvector not available, continue without it
                pass
    
    async def close(self):
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
    
    @property
    def pool(self) -> asyncpg.Pool:
        """Get connection pool (ensure connected first)."""
        if self._pool is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._pool
    
    # ==================== Endpoint Operations ====================
    
    async def get_endpoint_spec(self, endpoint_id: str) -> Optional[Dict]:
        """Get endpoint specification by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM endpoint_specs WHERE endpoint_id = $1",
                endpoint_id
            )
            
            if row:
                data = dict(row)
                spec_data = _parse_json(data.get('spec_data')) or {}
                return {
                    'endpoint_id': data.get('endpoint_id'),
                    'method': data.get('method') or spec_data.get('method', 'POST'),
                    'path': data.get('path') or spec_data.get('path', '/'),
                    'description': data.get('description') or spec_data.get('description', ''),
                    'auth_type': data.get('auth_type') or spec_data.get('auth_type', 's2s'),
                    'request_schema': _parse_json(data.get('request_schema')) or {},
                    'response_schema': _parse_json(data.get('response_schema')) or {},
                    'error_responses': _parse_json(data.get('error_responses')) or [],
                    'spec_data': spec_data,
                    'rate_limit': _parse_json(data.get('rate_limit')),
                    'idempotency': _parse_json(data.get('idempotency')),
                    'related_webhooks': _parse_json(data.get('related_webhooks')) or [],
                    'related_flows': _parse_json(data.get('related_flows')) or [],
                    'code_examples': _parse_json(data.get('code_examples')) or {},
                    'sandbox_notes': data.get('sandbox_notes')
                }
            return None
    
    async def search_endpoints(self, query: str, limit: int = 10) -> List[Dict]:
        """Search endpoints by path or description."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT endpoint_id, 
                          COALESCE(spec_data->>'method', 'POST') as method,
                          COALESCE(spec_data->>'path', '/') as path,
                          COALESCE(spec_data->>'description', '') as description
                   FROM endpoint_specs
                   WHERE endpoint_id ILIKE $1 
                      OR COALESCE(spec_data->>'path', '') ILIKE $1 
                      OR COALESCE(spec_data->>'description', '') ILIKE $1
                   ORDER BY endpoint_id
                   LIMIT $2""",
                f"%{query}%", limit
            )
            return [dict(r) for r in rows]
    
    async def list_endpoints(self) -> List[Dict]:
        """List all endpoints."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT endpoint_id, method, path, description
                   FROM endpoint_specs
                   ORDER BY endpoint_id"""
            )
            return [dict(r) for r in rows]
    
    async def insert_endpoint_spec(self, endpoint_id: str, method: str, path: str,
                                   description: str, auth_type: str,
                                   request_schema: Dict, response_schema: Dict,
                                   error_responses: List, spec_data: Dict,
                                   is_ground_truth: bool = False,
                                   source_doc_id: str = None):
        """Insert or update endpoint specification."""
        async with self.pool.acquire() as conn:
            column_rows = await conn.fetch(
                """SELECT column_name
                   FROM information_schema.columns
                   WHERE table_name = 'endpoint_specs'"""
            )
            existing_columns = {row['column_name'] for row in column_rows}

            values = {
                'endpoint_id': endpoint_id,
                'method': method,
                'path': path,
                'description': description,
                'auth_type': auth_type,
                'request_schema': json.dumps(request_schema),
                'response_schema': json.dumps(response_schema),
                'error_responses': json.dumps(error_responses),
                'spec_data': json.dumps(spec_data),
                'is_ground_truth': is_ground_truth,
                'source_doc_id': source_doc_id,
            }
            values = {key: value for key, value in values.items() if key in existing_columns}
            columns = list(values.keys())
            placeholders = [f"${index}" for index in range(1, len(columns) + 1)]
            update_columns = [col for col in columns if col != 'endpoint_id']
            update_clause = ", ".join([f"{col} = EXCLUDED.{col}" for col in update_columns])
            if 'updated_at' in existing_columns:
                update_clause = f"{update_clause}, updated_at = CURRENT_TIMESTAMP" if update_clause else "updated_at = CURRENT_TIMESTAMP"

            conflict_clause = (
                f"DO UPDATE SET {update_clause}"
                if update_clause else
                "DO NOTHING"
            )

            await conn.execute(
                f"""INSERT INTO endpoint_specs ({', '.join(columns)})
                    VALUES ({', '.join(placeholders)})
                    ON CONFLICT (endpoint_id) {conflict_clause}""",
                *[values[column] for column in columns],
            )
    
    async def insert_integration_flow(self, flow_id: str, name: str,
                                      use_case: str, description: str,
                                      steps: List, flow_data: Dict,
                                      prerequisites: List = None,
                                      estimated_duration_minutes: int = None,
                                      source_doc_id: str = None):
        """Insert or update integration flow."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO integration_flows 
                (flow_id, name, use_case, description, steps, flow_data,
                 prerequisites, estimated_duration_minutes, source_doc_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (flow_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    steps = EXCLUDED.steps,
                    flow_data = EXCLUDED.flow_data,
                    prerequisites = EXCLUDED.prerequisites,
                    estimated_duration_minutes = EXCLUDED.estimated_duration_minutes,
                    updated_at = CURRENT_TIMESTAMP
            """, flow_id, name, use_case, description,
                json.dumps(steps), json.dumps(flow_data),
                json.dumps(prerequisites or []), estimated_duration_minutes, source_doc_id)
    
    # ==================== Error Code Operations ====================
    
    async def get_error_code(self, error_code: str) -> Optional[Dict]:
        """Get error code details."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT error_code, http_status, category, message,
                          description, retry_guidance, common_causes,
                          fix_suggestions, bank_specific, related_errors,
                          error_data
                   FROM error_codes 
                   WHERE error_code = $1""",
                error_code
            )
            
            if row:
                return {
                    'error_code': row['error_code'],
                    'http_status': row['http_status'],
                    'category': row['category'],
                    'message': row['message'],
                    'description': row['description'],
                    'retry_guidance': _parse_json(row['retry_guidance']),
                    'common_causes': _parse_json(row['common_causes']) or [],
                    'fix_suggestions': _parse_json(row['fix_suggestions']) or [],
                    'bank_specific': _parse_json(row['bank_specific']),
                    'related_errors': _parse_json(row['related_errors']) or [],
                    'error_data': _parse_json(row['error_data']) or {}
                }
            return None
    
    async def search_error_codes(self, query: str, category: Optional[str] = None, limit: int = 20) -> List[Dict]:
        """Search error codes."""
        async with self.pool.acquire() as conn:
            if category:
                rows = await conn.fetch(
                    """SELECT error_code, http_status, category, message, description
                       FROM error_codes
                       WHERE (error_code ILIKE $1 OR message ILIKE $1 OR description ILIKE $1)
                         AND category = $2
                       ORDER BY error_code
                       LIMIT $3""",
                    f"%{query}%", category, limit
                )
            else:
                rows = await conn.fetch(
                    """SELECT error_code, http_status, category, message, description
                       FROM error_codes
                       WHERE error_code ILIKE $1 OR message ILIKE $1 OR description ILIKE $1
                       ORDER BY error_code
                       LIMIT $2""",
                    f"%{query}%", limit
                )
            return [dict(r) for r in rows]
    
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
    
    # ==================== Integration Flow Operations ====================
    
    async def get_flow(self, flow_id: str) -> Optional[Dict]:
        """Get integration flow by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT flow_id, name, use_case, description, steps,
                          prerequisites, estimated_duration_minutes, flow_data
                   FROM integration_flows 
                   WHERE flow_id = $1""",
                flow_id
            )
            
            if row:
                return {
                    'flow_id': row['flow_id'],
                    'name': row['name'],
                    'use_case': row['use_case'],
                    'description': row['description'],
                    'steps': _parse_json(row['steps']) or [],
                    'prerequisites': _parse_json(row['prerequisites']) or [],
                    'estimated_duration_minutes': row['estimated_duration_minutes'],
                    'flow_data': _parse_json(row['flow_data']) or {}
                }
            return None
    
    async def get_flows_by_use_case(self, use_case: str) -> List[Dict]:
        """Get flows by use case."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT flow_id, name, use_case, description
                   FROM integration_flows 
                   WHERE use_case = $1
                   ORDER BY flow_id""",
                use_case
            )
            return [dict(r) for r in rows]
    
    async def list_flows(self) -> List[Dict]:
        """List all integration flows."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT flow_id, name, use_case, description
                   FROM integration_flows
                   ORDER BY flow_id"""
            )
            return [dict(r) for r in rows]
    
    # ==================== Webhook Event Operations ====================
    
    async def get_webhook_event(self, event_type: str) -> Optional[Dict]:
        """Get webhook event definition."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT event_type, description, payload_schema,
                          signature_algorithm, retry_policy, idempotency_key_field,
                          ordering_guarantee, sample_payload
                   FROM webhook_events 
                   WHERE event_type = $1""",
                event_type
            )
            
            if row:
                return {
                    'event_type': row['event_type'],
                    'description': row['description'],
                    'payload_schema': _parse_json(row['payload_schema']) or {},
                    'signature_algorithm': row['signature_algorithm'],
                    'retry_policy': _parse_json(row['retry_policy']),
                    'idempotency_key_field': row['idempotency_key_field'],
                    'ordering_guarantee': row['ordering_guarantee'],
                    'sample_payload': _parse_json(row['sample_payload']) or {}
                }
            return None
    
    async def list_webhook_events(self) -> List[Dict]:
        """List all webhook events."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT event_type, description
                   FROM webhook_events
                   ORDER BY event_type"""
            )
            return [dict(r) for r in rows]
    
    # ==================== Code Template Operations ====================
    
    async def get_code_template(self, endpoint_id: str, language: str) -> Optional[str]:
        """Get code template for endpoint and language."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT code_text FROM code_templates
                   WHERE endpoint_id = $1 AND language = $2
                   LIMIT 1""",
                endpoint_id, language
            )
            
            if row:
                return row['code_text']
            return None
    
    # ==================== Test Scenario Operations ====================
    
    async def get_test_scenarios(self, flow_type: str, priority: Optional[str] = None) -> List[Dict]:
        """Get test scenarios for flow type."""
        async with self.pool.acquire() as conn:
            if priority:
                rows = await conn.fetch(
                    """SELECT scenario_id, flow_type, name, description,
                              input_data, expected_http_status, sandbox_notes
                       FROM test_scenarios
                       WHERE flow_type = $1 AND priority = $2
                       ORDER BY scenario_id""",
                    flow_type, priority
                )
            else:
                rows = await conn.fetch(
                    """SELECT scenario_id, flow_type, name, description,
                              input_data, expected_http_status, sandbox_notes
                       FROM test_scenarios
                       WHERE flow_type = $1
                       ORDER BY scenario_id""",
                    flow_type
                )
            return [dict(r) for r in rows]
    
    # ==================== Document & Search Operations ====================
    
    async def insert_document(self, doc_id: str, filename: str, content: str,
                              num_pages: int = 0, source_type: str = 'pdf') -> None:
        """Insert document record."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO documents (doc_id, filename, source_type, content, num_pages, total_chars)
                   VALUES ($1, $2, $3, $4, $5, $6)
                   ON CONFLICT (doc_id) DO UPDATE SET
                       content = EXCLUDED.content,
                       num_pages = EXCLUDED.num_pages,
                       total_chars = EXCLUDED.total_chars,
                       updated_at = CURRENT_TIMESTAMP""",
                doc_id, filename, source_type, content, num_pages, len(content)
            )
    
    async def insert_text_chunk(self, doc_id: str, chunk_index: int, chunk_text: str,
                                 embedding: Optional[List[float]] = None,
                                 namespace: str = 'general') -> None:
        """Insert text chunk with optional embedding."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO text_chunks (doc_id, chunk_index, chunk_text, embedding, namespace)
                   VALUES ($1, $2, $3, $4, $5)
                   ON CONFLICT (doc_id, chunk_index) DO UPDATE SET
                       chunk_text = EXCLUDED.chunk_text,
                       embedding = EXCLUDED.embedding""",
                doc_id, chunk_index, chunk_text,
                embedding if embedding else None,
                namespace
            )
    async def search_similar_chunks(self, query_embedding: List[float],
                                    namespace: Optional[str] = None,
                                    limit: int = 5) -> List[Dict]:
        """Search for similar text chunks using cosine similarity."""
        async with self.pool.acquire() as conn:
            embedding_array = query_embedding

            try:
                if namespace:
                    rows = await conn.fetch(
                        """SELECT tc.doc_id,
                                  tc.chunk_index,
                                  tc.chunk_text,
                                  tc.namespace,
                                  d.filename,
                                  1 - (tc.embedding <=> $1::vector) as similarity
                           FROM text_chunks tc
                           JOIN documents d ON tc.doc_id = d.doc_id
                           WHERE tc.namespace = $2 AND tc.embedding IS NOT NULL
                           ORDER BY tc.embedding <=> $1::vector
                           LIMIT $3""",
                        embedding_array, namespace, limit
                    )
                else:
                    rows = await conn.fetch(
                        """SELECT tc.doc_id,
                                  tc.chunk_index,
                                  tc.chunk_text,
                                  tc.namespace,
                                  d.filename,
                                  1 - (tc.embedding <=> $1::vector) as similarity
                           FROM text_chunks tc
                           JOIN documents d ON tc.doc_id = d.doc_id
                           WHERE tc.embedding IS NOT NULL
                           ORDER BY tc.embedding <=> $1::vector
                           LIMIT $2""",
                        embedding_array, limit
                    )

                return [dict(r) for r in rows]
            except Exception:
                # Most local schemas store embeddings as JSONB instead of pgvector.
                # Keep semantic search usable by ranking in Python when vector ops are unavailable.
                if namespace:
                    rows = await conn.fetch(
                        """SELECT tc.doc_id, tc.chunk_index, tc.chunk_text, tc.namespace,
                                  tc.embedding, d.filename
                           FROM text_chunks tc
                           JOIN documents d ON tc.doc_id = d.doc_id
                           WHERE tc.namespace = $1 AND tc.embedding IS NOT NULL""",
                        namespace
                    )
                else:
                    rows = await conn.fetch(
                        """SELECT tc.doc_id, tc.chunk_index, tc.chunk_text, tc.namespace,
                                  tc.embedding, d.filename
                           FROM text_chunks tc
                           JOIN documents d ON tc.doc_id = d.doc_id
                           WHERE tc.embedding IS NOT NULL"""
                    )

                ranked = []
                for row in rows:
                    embedding = _parse_json(row["embedding"])
                    similarity = self._cosine_similarity(query_embedding, embedding)
                    if similarity is None:
                        continue

                    item = dict(row)
                    item.pop("embedding", None)
                    item["similarity"] = similarity
                    ranked.append(item)

                ranked.sort(key=lambda r: r["similarity"], reverse=True)
                return ranked[:limit]

    async def search_text_chunks_keyword(self, query: str,
                                         namespace: Optional[str] = None,
                                         limit: int = 5) -> List[Dict]:
        """Keyword fallback over existing text chunks joined to documents."""
        stop_words = {
            "the", "and", "for", "with", "from", "that", "this", "what",
            "does", "say", "says", "about", "into", "how", "are", "was",
            "were", "npci", "circular", "circulars", "mention", "mentions",
            "mentioned",
        }
        generic_terms = {
            "transaction", "transactions", "limit", "limits", "revision",
            "merchant", "merchants", "payment", "payments",
        }
        tokens = [
            token.lower()
            for token in re.findall(r"[a-zA-Z0-9]+", query)
            if len(token) > 2 and token.lower() not in stop_words
        ][:8]
        if not tokens:
            tokens = [query.lower()]

        params = [f"%{token}%" for token in tokens]
        clauses = []
        score_parts = []
        for index, token in enumerate(tokens, 1):
            chunk_weight = 2 if token in generic_terms else 5
            filename_weight = 4 if token in generic_terms else 9
            content_weight = 1 if token in generic_terms else 2
            clauses.append(
                f"(tc.chunk_text ILIKE ${index} OR d.filename ILIKE ${index} OR d.content ILIKE ${index})"
            )
            score_parts.extend([
                f"CASE WHEN tc.chunk_text ILIKE ${index} THEN {chunk_weight} ELSE 0 END",
                f"CASE WHEN d.filename ILIKE ${index} THEN {filename_weight} ELSE 0 END",
                f"CASE WHEN d.content ILIKE ${index} THEN {content_weight} ELSE 0 END",
            ])

        args = list(params)
        namespace_clause = ""
        if namespace:
            args.append(namespace)
            namespace_clause = f" AND tc.namespace = ${len(args)}"

        args.append(limit)
        limit_param = len(args)
        sql = f"""
            SELECT tc.doc_id,
                   tc.chunk_index,
                   tc.chunk_text,
                   tc.namespace,
                   d.filename,
                   ({' + '.join(score_parts)}) AS keyword_score
            FROM text_chunks tc
            JOIN documents d ON tc.doc_id = d.doc_id
            WHERE ({' OR '.join(clauses)}){namespace_clause}
            ORDER BY keyword_score DESC, d.filename, tc.chunk_index
            LIMIT ${limit_param}
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
        return [dict(r) for r in rows]

    async def search_api_business_use_cases(self, query_embedding: List[float],
                                            limit: int = 10) -> List[Dict]:
        """Search API specs by business-use-case embedding similarity."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT endpoint_id, method, path, api_version, summary,
                          description, business_use_case, when_newton_sends_it,
                          business_use_case_embedding
                   FROM api_specs_v2
                   WHERE business_use_case_embedding IS NOT NULL
                     AND (business_use_case IS NOT NULL OR when_newton_sends_it IS NOT NULL)"""
            )

            ranked = []
            for row in rows:
                embedding = _parse_json(row["business_use_case_embedding"])
                similarity = self._cosine_similarity(query_embedding, embedding)
                if similarity is None:
                    continue

                item = dict(row)
                item.pop("business_use_case_embedding", None)
                item["similarity"] = similarity
                ranked.append(item)

            ranked.sort(key=lambda r: r["similarity"], reverse=True)
            return ranked[:limit]

    async def search_api_business_use_cases_text(self, query: str,
                                                 limit: int = 10) -> List[Dict]:
        """Keyword fallback search over API business-use-case text."""
        stop_words = {
            "the", "and", "for", "with", "from", "that", "this", "when",
            "into", "api", "apis", "account", "customer", "merchant",
        }
        tokens = [
            token for token in re.findall(r"[a-zA-Z0-9]+", query.lower())
            if len(token) > 1 and token not in stop_words
        ][:8]
        if not tokens:
            tokens = [query]

        params = [f"%{token}%" for token in tokens]
        match_clauses = []
        score_parts = []
        for index in range(1, len(params) + 1):
            clause = (
                f"(business_use_case ILIKE ${index} OR summary ILIKE ${index} "
                f"OR description ILIKE ${index} OR path ILIKE ${index} "
                f"OR when_newton_sends_it ILIKE ${index})"
            )
            match_clauses.append(clause)
            score_parts.extend([
                f"CASE WHEN when_newton_sends_it ILIKE ${index} THEN 5 ELSE 0 END",
                f"CASE WHEN business_use_case ILIKE ${index} THEN 4 ELSE 0 END",
                f"CASE WHEN summary ILIKE ${index} THEN 2 ELSE 0 END",
                f"CASE WHEN path ILIKE ${index} THEN 2 ELSE 0 END",
                f"CASE WHEN description ILIKE ${index} THEN 1 ELSE 0 END",
            ])

        limit_param = len(params) + 1
        sql = f"""
            SELECT endpoint_id, method, path, api_version, summary,
                   description, business_use_case, when_newton_sends_it,
                   ({' + '.join(score_parts)}) AS keyword_score
            FROM api_specs_v2
            WHERE {' OR '.join(match_clauses)}
            ORDER BY keyword_score DESC, endpoint_id
            LIMIT ${limit_param}
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *params, limit)
            return [dict(row) for row in rows]

    async def get_document_content(self, doc_id: str) -> Optional[str]:
        """Get document content by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT content FROM documents WHERE doc_id = $1",
                doc_id
            )
            return row['content'] if row else None
    
    # ==================== Known Issues Operations ====================
    
    async def search_known_issues(self, query_embedding: List[float], limit: int = 5) -> List[Dict]:
        """Search known issues by similarity."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT title, description, symptoms, solution,
                          1 - (embedding::vector <=> $1::vector) as similarity
                   FROM known_issues
                   WHERE embedding IS NOT NULL
                   ORDER BY embedding::vector <=> $1::vector
                   LIMIT $2""",
                query_embedding, limit
            )
            return [dict(r) for r in rows]
    
    async def insert_known_issue(self, title: str, description: str,
                                  symptoms: Optional[str] = None,
                                  solution: Optional[str] = None,
                                  embedding: Optional[List[float]] = None) -> None:
        """Insert a known issue."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO known_issues (title, description, symptoms, solution, embedding)
                   VALUES ($1, $2, $3, $4, $5)""",
                title, description, symptoms, solution,
                json.dumps(embedding) if embedding else None
            )
    
    # ==================== Session & Logging Operations ====================
    
    async def create_session(self, session_id: str, api_key_hash: str,
                             expires_at: str, merchant_id: Optional[str] = None) -> None:
        """Create sandbox session."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO sandbox_sessions (session_id, api_key_hash, merchant_id, expires_at)
                   VALUES ($1, $2, $3, $4)""",
                session_id, api_key_hash, merchant_id, expires_at
            )
    
    async def log_request(self, tool_name: str, request_params: Dict,
                          response_status: str, latency_ms: int,
                          session_id: Optional[str] = None) -> None:
        """Log tool request for analytics."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO request_logs (session_id, tool_name, request_params, response_status, latency_ms)
                   VALUES ($1, $2, $3, $4, $5)""",
                session_id, tool_name, json.dumps(request_params),
                response_status, latency_ms
            )
    
    # ==================== Statistics ====================
    
    async def get_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        async with self.pool.acquire() as conn:
            stats = {}
            tables = [
                'documents', 'text_chunks', 'endpoint_specs', 'error_codes',
                'integration_flows', 'webhook_events', 'code_templates',
                'test_scenarios', 'known_issues', 'contextual_embeddings',
                'api_specs_v2', 'api_headers', 'api_fields', 'api_samples',
                'api_conditions'
            ]
            for table in tables:
                try:
                    count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                    stats[table] = count
                except:
                    stats[table] = 0
            return stats

    @staticmethod
    def _cosine_similarity(left: List[float], right: Any) -> Optional[float]:
        """Compute cosine similarity for JSONB/list embeddings."""
        if isinstance(right, str):
            try:
                right = json.loads(right)
            except Exception:
                return None

        if not isinstance(right, list) or not left or len(left) != len(right):
            return None

        try:
            dot = sum(float(a) * float(b) for a, b in zip(left, right))
            left_norm = math.sqrt(sum(float(a) * float(a) for a in left))
            right_norm = math.sqrt(sum(float(b) * float(b) for b in right))
        except (TypeError, ValueError):
            return None

        if left_norm == 0 or right_norm == 0:
            return None

        return dot / (left_norm * right_norm)


# Global database instance
database = Database()
