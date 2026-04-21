#!/usr/bin/env python3
"""Initialize complete merchant MCP database."""

import asyncio
import sys
sys.path.insert(0, '/home/ganesh/merchant_mcp')

import asyncpg
from src.utils.config import Config


CREATE_SCHEMA_SQL = """
-- Documents table (PDF sources)
CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    source_type TEXT DEFAULT 'pdf',  -- pdf, openapi, sdk, confluence
    content TEXT NOT NULL,
    num_pages INTEGER DEFAULT 0,
    total_chars INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Text chunks for search (store embeddings as JSON array, convert to vector later)
CREATE TABLE IF NOT EXISTS text_chunks (
    chunk_id SERIAL PRIMARY KEY,
    doc_id TEXT REFERENCES documents(doc_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding JSONB,  -- Store as JSON array, convert when pgvector available
    namespace TEXT DEFAULT 'general',  -- guides, faqs, error_descriptions, known_issues
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(doc_id, chunk_index)
);

-- Endpoint specifications (ground truth + ingested)
CREATE TABLE IF NOT EXISTS endpoint_specs (
    endpoint_id TEXT PRIMARY KEY,
    method VARCHAR(10) NOT NULL,
    path TEXT NOT NULL,
    description TEXT,
    auth_type VARCHAR(20) DEFAULT 'api_key',
    request_schema JSONB NOT NULL DEFAULT '{}',
    response_schema JSONB NOT NULL DEFAULT '{}',
    error_responses JSONB DEFAULT '[]',
    spec_data JSONB NOT NULL DEFAULT '{}',
    rate_limit JSONB,
    idempotency JSONB,
    related_webhooks JSONB DEFAULT '[]',
    related_flows JSONB DEFAULT '[]',
    code_examples JSONB DEFAULT '{}',
    sandbox_notes TEXT,
    source_doc_id TEXT REFERENCES documents(doc_id),
    is_ground_truth BOOLEAN DEFAULT FALSE,
    version TEXT DEFAULT 'v1',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Error codes registry
CREATE TABLE IF NOT EXISTS error_codes (
    error_code TEXT PRIMARY KEY,
    http_status INTEGER NOT NULL,
    category VARCHAR(30) NOT NULL CHECK (category IN ('retryable', 'terminal', 'merchant_action', 'system_error')),
    message TEXT NOT NULL,
    description TEXT,
    retry_guidance JSONB,
    common_causes JSONB DEFAULT '[]',
    fix_suggestions JSONB DEFAULT '[]',
    bank_specific JSONB,
    related_errors JSONB DEFAULT '[]',
    error_data JSONB NOT NULL DEFAULT '{}',
    source_doc_id TEXT REFERENCES documents(doc_id),
    occurrence_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Integration flows
CREATE TABLE IF NOT EXISTS integration_flows (
    flow_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    use_case VARCHAR(30) NOT NULL CHECK (use_case IN ('payment', 'collect', 'mandate', 'refund', 'subscription')),
    description TEXT,
    steps JSONB NOT NULL DEFAULT '[]',
    flow_data JSONB NOT NULL DEFAULT '{}',
    version TEXT DEFAULT 'v1',
    prerequisites JSONB DEFAULT '[]',
    estimated_duration_minutes INTEGER,
    source_doc_id TEXT REFERENCES documents(doc_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Webhook events
CREATE TABLE IF NOT EXISTS webhook_events (
    event_type TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    payload_schema JSONB NOT NULL DEFAULT '{}',
    signature_algorithm VARCHAR(20) DEFAULT 'hmac_sha256',
    retry_policy JSONB DEFAULT '{"max_retries": 5, "retry_intervals": [5, 10, 30, 60, 300]}',
    idempotency_key_field TEXT,
    ordering_guarantee VARCHAR(20) DEFAULT 'unordered',
    sample_payload JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Code templates
CREATE TABLE IF NOT EXISTS code_templates (
    template_id TEXT PRIMARY KEY,
    language VARCHAR(20) NOT NULL,
    endpoint_id TEXT REFERENCES endpoint_specs(endpoint_id),
    code_text TEXT NOT NULL,
    sdk_variant VARCHAR(20) DEFAULT 'sdk',
    includes_error_handling BOOLEAN DEFAULT TRUE,
    includes_comments BOOLEAN DEFAULT TRUE,
    dependencies JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Test scenarios
CREATE TABLE IF NOT EXISTS test_scenarios (
    scenario_id TEXT PRIMARY KEY,
    flow_type VARCHAR(30) NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    input_data JSONB NOT NULL DEFAULT '{}',
    expected_http_status INTEGER NOT NULL,
    expected_response_pattern TEXT,
    assertions JSONB DEFAULT '[]',
    sandbox_notes TEXT,
    priority VARCHAR(20) DEFAULT 'essential',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Known issues (support KB)
CREATE TABLE IF NOT EXISTS known_issues (
    issue_id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    symptoms TEXT,
    root_cause TEXT,
    solution TEXT,
    code_pattern TEXT,
    affected_versions TEXT,
    workaround TEXT,
    embedding JSONB,  -- Store as JSON for now
    occurrence_count INTEGER DEFAULT 0,
    resolution_rate FLOAT DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Session management for sandbox
CREATE TABLE IF NOT EXISTS sandbox_sessions (
    session_id TEXT PRIMARY KEY,
    api_key_hash TEXT NOT NULL,  -- Hashed, never store plain
    merchant_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Request logs for analytics
CREATE TABLE IF NOT EXISTS request_logs (
    log_id SERIAL PRIMARY KEY,
    session_id TEXT REFERENCES sandbox_sessions(session_id),
    tool_name TEXT NOT NULL,
    request_params JSONB,
    response_status TEXT,
    latency_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_chunks_namespace ON text_chunks(namespace);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON text_chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_endpoint_specs_path ON endpoint_specs(path);
CREATE INDEX IF NOT EXISTS idx_error_codes_category ON error_codes(category);
CREATE INDEX IF NOT EXISTS idx_error_codes_http_status ON error_codes(http_status);
CREATE INDEX IF NOT EXISTS idx_flows_use_case ON integration_flows(use_case);
CREATE INDEX IF NOT EXISTS idx_templates_endpoint ON code_templates(endpoint_id);
CREATE INDEX IF NOT EXISTS idx_logs_created_at ON request_logs(created_at);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_documents_updated_at ON documents;
CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_endpoint_specs_updated_at ON endpoint_specs;
CREATE TRIGGER update_endpoint_specs_updated_at BEFORE UPDATE ON endpoint_specs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_error_codes_updated_at ON error_codes;
CREATE TRIGGER update_error_codes_updated_at BEFORE UPDATE ON error_codes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_flows_updated_at ON integration_flows;
CREATE TRIGGER update_flows_updated_at BEFORE UPDATE ON integration_flows
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
"""


async def init_database():
    """Initialize database schema."""
    print(f"Connecting to database at {Config.DB_HOST}:{Config.DB_PORT}...")
    
    conn = await asyncpg.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        database=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD
    )
    
    try:
        print("Creating schema...")
        await conn.execute(CREATE_SCHEMA_SQL)
        print("✅ Schema created successfully")
        
        # Count existing tables
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """)
        table_names = [t['table_name'] for t in tables]
        print(f"✅ {len(tables)} tables ready: {', '.join(table_names)}")
        
        # Check if essential tables exist
        required_tables = [
            'documents', 'text_chunks', 'endpoint_specs', 'error_codes',
            'integration_flows', 'webhook_events', 'code_templates',
            'test_scenarios', 'known_issues', 'sandbox_sessions', 'request_logs'
        ]
        missing = [t for t in required_tables if t not in table_names]
        if missing:
            print(f"⚠️ Missing tables: {missing}")
        else:
            print("✅ All required tables present")
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(init_database())
