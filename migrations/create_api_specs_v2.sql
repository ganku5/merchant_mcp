-- Migration: Create API Specs V2 Schema
-- Supports: headers, conditional fields, nested structures, samples

BEGIN;

-- Drop existing v2 tables if they exist (for clean migration)
DROP TABLE IF EXISTS api_samples CASCADE;
DROP TABLE IF EXISTS api_conditions CASCADE;
DROP TABLE IF EXISTS api_fields CASCADE;
DROP TABLE IF EXISTS api_headers CASCADE;
DROP TABLE IF EXISTS api_specs_v2 CASCADE;

-- Main API Specifications table
CREATE TABLE api_specs_v2 (
    spec_id SERIAL PRIMARY KEY,
    endpoint_id TEXT UNIQUE NOT NULL,
    
    -- Basic info
    method VARCHAR(10) NOT NULL CHECK (method IN ('GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD')),
    path TEXT NOT NULL,
    api_version TEXT DEFAULT 'v1',
    description TEXT,
    summary TEXT,
    documentation_url TEXT,
    changelog JSONB DEFAULT '[]',
    business_use_case TEXT,
    business_use_case_embedding JSONB,
    when_newton_sends_it TEXT,
    source_doc_id TEXT,
    source_file TEXT,
    source_hash TEXT,
    
    -- Rate limiting
    rate_limit JSONB DEFAULT '{}',
    -- e.g., {"requests_per_second": 100, "requests_per_minute": 1000, "burst_allowance": 200}
    
    -- Idempotency
    idempotency JSONB DEFAULT '{}',
    -- e.g., {"required": true, "header_name": "X-Idempotency-Key", "ttl_seconds": 86400}
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(method, path, api_version)
);

-- Headers table (request and response)
CREATE TABLE api_headers (
    header_id SERIAL PRIMARY KEY,
    spec_id INTEGER REFERENCES api_specs_v2(spec_id) ON DELETE CASCADE,
    header_type VARCHAR(10) NOT NULL CHECK (header_type IN ('request', 'response')),
    
    -- Header info
    name TEXT NOT NULL,
    value_template TEXT,
    required BOOLEAN DEFAULT TRUE,
    description TEXT,
    
    -- Conditional logic
    conditional_when TEXT,
    conditional_expression TEXT,
    
    -- Constraints
    pattern TEXT,
    enum_values JSONB,
    min_length INTEGER,
    max_length INTEGER,
    
    -- Examples
    example_value TEXT,
    default_value TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(spec_id, header_type, name)
);

-- Fields table (flattened hierarchy for request/response)
CREATE TABLE api_fields (
    field_id SERIAL PRIMARY KEY,
    spec_id INTEGER REFERENCES api_specs_v2(spec_id) ON DELETE CASCADE,
    context VARCHAR(20) NOT NULL CHECK (context IN ('request', 'response')),
    
    -- Field hierarchy
    parent_path TEXT DEFAULT '',
    field_name TEXT NOT NULL,
    full_path TEXT GENERATED ALWAYS AS (
        CASE 
            WHEN parent_path = '' THEN field_name
            WHEN parent_path LIKE '%[*]%' THEN 
                REPLACE(parent_path, '[*]', '') || '.' || field_name
            ELSE parent_path || '.' || field_name
        END
    ) STORED,
    
    -- Type info
    field_type VARCHAR(30) NOT NULL,
    subtype VARCHAR(30),
    format VARCHAR(50),
    
    -- Description
    description TEXT,
    placeholder TEXT,
    
    -- Requirement level
    requirement VARCHAR(20) DEFAULT 'optional' 
        CHECK (requirement IN ('mandatory', 'optional', 'conditional')),
    
    -- Conditional logic
    condition_description TEXT,
    condition_expression TEXT,
    condition_dependencies JSONB DEFAULT '[]',
    
    -- Constraints (flexible JSONB for various constraint types)
    constraints JSONB DEFAULT '{}',
    array_constraints JSONB DEFAULT '{}',
    object_constraints JSONB DEFAULT '{}',
    
    -- Examples
    example_value JSONB,
    default_value JSONB,
    
    -- Metadata
    is_sensitive BOOLEAN DEFAULT FALSE,
    encoding VARCHAR(20),
    
    -- Ordering for display
    display_order INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(spec_id, context, full_path)
);

-- Conditions table (shared conditional logic)
CREATE TABLE api_conditions (
    condition_id SERIAL PRIMARY KEY,
    spec_id INTEGER REFERENCES api_specs_v2(spec_id) ON DELETE CASCADE,
    
    condition_name TEXT NOT NULL,
    description TEXT,
    expression TEXT NOT NULL,
    trigger_field TEXT,
    trigger_values JSONB,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(spec_id, condition_name)
);

-- Samples table (complete request/response examples)
CREATE TABLE api_samples (
    sample_id SERIAL PRIMARY KEY,
    spec_id INTEGER REFERENCES api_specs_v2(spec_id) ON DELETE CASCADE,
    
    -- Sample identification
    sample_name TEXT NOT NULL,
    description TEXT,
    scenario VARCHAR(50),
    
    -- Complete request
    request JSONB NOT NULL DEFAULT '{}',
    -- Structure: {
    --   "headers": {},
    --   "query_params": {},
    --   "path_params": {},
    --   "body": {}
    -- }
    
    -- Expected response
    response JSONB NOT NULL DEFAULT '{}',
    -- Structure: {
    --   "status_code": 200,
    --   "headers": {},
    --   "body": {}
    -- }
    
    -- CURL command
    curl_command TEXT,
    
    -- Validation info
    expected_validation_errors JSONB,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(spec_id, sample_name)
);

-- Create indexes for efficient lookups
CREATE INDEX idx_api_specs_endpoint ON api_specs_v2(endpoint_id);
CREATE INDEX idx_api_specs_method_path ON api_specs_v2(method, path);
CREATE INDEX idx_api_specs_source_doc ON api_specs_v2(source_doc_id);
CREATE INDEX idx_api_specs_source_file ON api_specs_v2(source_file);

CREATE INDEX idx_api_headers_spec ON api_headers(spec_id, header_type);
CREATE INDEX idx_api_headers_name ON api_headers(spec_id, header_type, name);

CREATE INDEX idx_api_fields_spec ON api_fields(spec_id, context);
CREATE INDEX idx_api_fields_parent ON api_fields(spec_id, context, parent_path);
CREATE INDEX idx_api_fields_requirement ON api_fields(spec_id, requirement);

CREATE INDEX idx_api_conditions_spec ON api_conditions(spec_id);

CREATE INDEX idx_api_samples_spec ON api_samples(spec_id);
CREATE INDEX idx_api_samples_scenario ON api_samples(spec_id, scenario);

-- Create function to update timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
DROP TRIGGER IF EXISTS trg_api_specs_v2_updated ON api_specs_v2;
CREATE TRIGGER trg_api_specs_v2_updated
    BEFORE UPDATE ON api_specs_v2
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trg_api_fields_updated ON api_fields;
CREATE TRIGGER trg_api_fields_updated
    BEFORE UPDATE ON api_fields
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMIT;
