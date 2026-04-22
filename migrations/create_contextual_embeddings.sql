-- Migration: Create Contextual Embeddings Table
-- Stores Q&A pairs generated from content for better semantic search

BEGIN;

-- Drop existing table if exists
DROP TABLE IF EXISTS contextual_embeddings CASCADE;

-- Contextual embeddings table (using JSONB for embeddings instead of vector type)
CREATE TABLE contextual_embeddings (
    context_id SERIAL PRIMARY KEY,
    source_chunk_id INTEGER,
    source_doc_id TEXT REFERENCES documents(doc_id) ON DELETE CASCADE,
    
    -- Original content reference
    original_content TEXT NOT NULL,
    content_summary TEXT,
    
    -- Generated Q&A pairs (stored as JSON array)
    qa_pairs JSONB NOT NULL DEFAULT '[]',
    -- Format: [
    --   {"question": "...", "answer": "...", "type": "factual|procedural|conceptual"},
    --   ...
    -- ]
    
    -- Combined context text (Q+A concatenated) used for embedding
    combined_context TEXT NOT NULL,
    
    -- Vector embedding of combined context (stored as JSONB array)
    embedding JSONB,
    embedding_dimensions INTEGER DEFAULT 768,
    
    -- Metadata
    context_type VARCHAR(30) DEFAULT 'qa_pairs' 
        CHECK (context_type IN ('qa_pairs', 'summary', 'keywords', 'expanded')),
    
    -- Generation metadata
    generation_model TEXT DEFAULT 'gpt-4o-mini',
    generation_prompt TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_contextual_embeddings_doc ON contextual_embeddings(source_doc_id);
CREATE INDEX idx_contextual_embeddings_chunk ON contextual_embeddings(source_chunk_id);
CREATE INDEX idx_contextual_embeddings_type ON contextual_embeddings(context_type);

-- Create GIN index for qa_pairs JSONB
CREATE INDEX idx_contextual_embeddings_qa ON contextual_embeddings USING GIN(qa_pairs);

-- Create trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS trg_contextual_embeddings_updated ON contextual_embeddings;
CREATE TRIGGER trg_contextual_embeddings_updated
    BEFORE UPDATE ON contextual_embeddings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Create view for easy querying
CREATE OR REPLACE VIEW vw_contextual_search AS
SELECT 
    ce.context_id,
    ce.source_doc_id,
    ce.source_chunk_id,
    ce.original_content,
    ce.qa_pairs,
    ce.combined_context,
    ce.embedding,
    ce.context_type,
    d.filename as source_filename
FROM contextual_embeddings ce
LEFT JOIN documents d ON ce.source_doc_id = d.doc_id;

COMMIT;
