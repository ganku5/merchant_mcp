"""
Contextual Embedding Generator

Generates Q&A pairs from text content using LLM and creates contextual embeddings.
"""

import json
import asyncio
from typing import List, Dict, Any, Optional
from ..utils.database import database
from ..utils.llm import llm_client


class ContextualEmbeddingGenerator:
    """Generates contextual embeddings (Q&A pairs) from text content."""
    
    # System prompt for generating Q&A pairs
    QA_GENERATION_PROMPT = """You are an expert at extracting knowledge from technical documentation.

Given a passage of text, generate 3-5 relevant question-and-answer pairs that capture the key information.

Guidelines:
1. Questions should be specific and natural (as if a developer is asking)
2. Answers should be concise but complete, using information from the text
3. Include different types:
   - Factual: "What is...?", "How does...?"
   - Procedural: "How do I...?", "What are the steps to...?"
   - Conceptual: "Why...?", "What is the purpose of...?"
4. If the text lacks sufficient detail, generate fewer pairs
5. Ensure answers are directly supported by the text

Format your response as a JSON array:
[
  {
    "question": "What is JWE and why is it used?",
    "answer": "JWE (JSON Web Encryption) is used to encrypt sensitive data during transmission, ensuring PII protection.",
    "type": "conceptual"
  }
]

Text to analyze:
{text}

Generate Q&A pairs (respond ONLY with valid JSON array):"""

    SUMMARY_GENERATION_PROMPT = """Summarize the following text in 2-3 sentences, capturing the main concepts and key points:

{text}

Summary:"""

    def __init__(self):
        self.stats = {
            "processed": 0,
            "generated": 0,
            "failed": 0
        }
    
    async def generate_qa_pairs(self, text: str) -> List[Dict[str, str]]:
        """Generate Q&A pairs from text using LLM."""
        try:
            prompt = self.QA_GENERATION_PROMPT.format(text=text[:3000])  # Limit context
            
            response = await llm_client.chat(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that extracts Q&A pairs from text. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            # Extract JSON from response
            content = response
            
            # Try to find JSON array in the response
            start_idx = content.find('[')
            end_idx = content.rfind(']')
            
            if start_idx != -1 and end_idx != -1:
                json_str = content[start_idx:end_idx + 1]
                qa_pairs = json.loads(json_str)
                
                # Validate structure
                valid_pairs = []
                for pair in qa_pairs:
                    if isinstance(pair, dict) and 'question' in pair and 'answer' in pair:
                        valid_pairs.append({
                            'question': pair['question'],
                            'answer': pair['answer'],
                            'type': pair.get('type', 'factual')
                        })
                
                return valid_pairs
            
            return []
            
        except Exception as e:
            print(f"⚠️ Error generating Q&A pairs: {e}")
            return []
    
    async def generate_summary(self, text: str) -> str:
        """Generate a summary of the text."""
        try:
            prompt = self.SUMMARY_GENERATION_PROMPT.format(text=text[:3000])
            
            response = await llm_client.chat(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes technical content."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            return response.strip()
            
        except Exception as e:
            print(f"⚠️ Error generating summary: {e}")
            return ""
    
    def combine_qa_to_context(self, qa_pairs: List[Dict], original_text: str, summary: str = "") -> str:
        """Combine Q&A pairs into a unified context string for embedding."""
        parts = []
        
        if summary:
            parts.append(f"Summary: {summary}")
        
        parts.append(f"Original Content: {original_text[:500]}...")
        
        if qa_pairs:
            parts.append("\nKey Questions and Answers:")
            for i, qa in enumerate(qa_pairs, 1):
                parts.append(f"\nQ{i}: {qa['question']}")
                parts.append(f"A{i}: {qa['answer']}")
        
        return "\n".join(parts)
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate vector embedding for text."""
        try:
            embedding = await llm_client.embed([text])
            return embedding[0] if embedding else []
        except Exception as e:
            print(f"⚠️ Error generating embedding: {e}")
            return []
    
    async def process_chunk(self, chunk_id: int, doc_id: str, content: str) -> Optional[int]:
        """Process a single text chunk and create contextual embedding."""
        try:
            # Generate Q&A pairs
            qa_pairs = await self.generate_qa_pairs(content)
            
            # Generate summary
            summary = await self.generate_summary(content)
            
            # Combine into context
            combined_context = self.combine_qa_to_context(qa_pairs, content, summary)
            
            # Generate embedding
            embedding = await self.generate_embedding(combined_context)
            
            # Store in database
            if database._pool is None:
                await database.connect()
            
            conn = database.pool
            async with conn.acquire() as db_conn:
                # Check if record exists
                existing = await db_conn.fetchval(
                    "SELECT context_id FROM contextual_embeddings WHERE source_chunk_id = $1",
                    chunk_id
                )
                
                if existing:
                    # Update existing
                    await db_conn.execute("""
                        UPDATE contextual_embeddings SET
                            original_content = $1,
                            content_summary = $2,
                            qa_pairs = $3,
                            combined_context = $4,
                            embedding = $5,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE source_chunk_id = $6
                    """,
                        content,
                        summary,
                        json.dumps(qa_pairs),
                        combined_context,
                        json.dumps(embedding) if embedding else None,
                        chunk_id
                    )
                    context_id = existing
                else:
                    # Insert new
                    context_id = await db_conn.fetchval("""
                        INSERT INTO contextual_embeddings (
                            source_chunk_id,
                            source_doc_id,
                            original_content,
                            content_summary,
                            qa_pairs,
                            combined_context,
                            embedding,
                            generation_prompt
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        RETURNING context_id
                    """,
                        chunk_id,
                        doc_id,
                        content,
                        summary,
                        json.dumps(qa_pairs),
                        combined_context,
                        json.dumps(embedding) if embedding else None,
                        self.QA_GENERATION_PROMPT[:200]
                    )
                
                self.stats["generated"] += 1
                return context_id
                
        except Exception as e:
            print(f"⚠️ Error processing chunk {chunk_id}: {e}")
            self.stats["failed"] += 1
            return None
    
    async def process_document(self, doc_id: str, batch_size: int = 3):
        """Process all chunks of a document."""
        if database._pool is None:
            await database.connect()
        
        conn = database.pool
        
        async with conn.acquire() as db_conn:
            # Get all chunks for the document that don't have contextual embeddings
            chunks = await db_conn.fetch("""
                SELECT tc.chunk_id, tc.chunk_text as content
                FROM text_chunks tc
                LEFT JOIN contextual_embeddings ce ON tc.chunk_id = ce.source_chunk_id
                WHERE tc.doc_id = $1
                  AND ce.context_id IS NULL
                ORDER BY tc.chunk_index
            """, doc_id)
            
            print(f"📄 Found {len(chunks)} chunks to process for {doc_id}")
            
            # Process in batches
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                for c in batch:
                    await self.process_chunk(c['chunk_id'], doc_id, c['content'])
                
                self.stats["processed"] += len(batch)
                print(f"  Progress: {self.stats['processed']}/{len(chunks)} chunks")
        
        return self.stats
    
    async def search_contextual(
        self, 
        query: str, 
        doc_id: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict]:
        """Search using contextual embeddings (keyword search fallback)."""
        try:
            if database._pool is None:
                await database.connect()
            
            conn = database.pool
            
            async with conn.acquire() as db_conn:
                # Use keyword search on combined context and Q&A
                search_pattern = f"%{query}%"
                
                if doc_id:
                    results = await db_conn.fetch("""
                        SELECT 
                            context_id,
                            source_doc_id,
                            original_content,
                            qa_pairs,
                            combined_context
                        FROM contextual_embeddings
                        WHERE source_doc_id = $1
                          AND (
                              combined_context ILIKE $2 
                              OR original_content ILIKE $2
                              OR qa_pairs::text ILIKE $2
                          )
                        LIMIT $3
                    """, doc_id, search_pattern, top_k)
                else:
                    results = await db_conn.fetch("""
                        SELECT 
                            context_id,
                            source_doc_id,
                            original_content,
                            qa_pairs,
                            combined_context
                        FROM contextual_embeddings
                        WHERE combined_context ILIKE $1 
                           OR original_content ILIKE $1
                           OR qa_pairs::text ILIKE $1
                        LIMIT $2
                    """, search_pattern, top_k)
                
                return [dict(r) for r in results]
                
        except Exception as e:
            print(f"⚠️ Error searching contextual embeddings: {e}")
            return []


# Convenience functions for MCP tools
async def generate_contextual_embeddings(doc_id: str) -> Dict[str, Any]:
    """Generate contextual embeddings for a document."""
    generator = ContextualEmbeddingGenerator()
    stats = await generator.process_document(doc_id)
    
    return {
        "content": [{
            "type": "text",
            "text": f"✅ Contextual embeddings generated for {doc_id}\n\n**Stats:**\n- Chunks processed: {stats['processed']}\n- Q&A pairs generated: {stats['generated']}\n- Failed: {stats['failed']}"
        }],
        "isError": False
    }


async def search_contextual_embeddings(query: str, doc_id: Optional[str] = None, top_k: int = 5) -> Dict[str, Any]:
    """Search using contextual embeddings."""
    generator = ContextualEmbeddingGenerator()
    results = await generator.search_contextual(query, doc_id, top_k)
    
    if not results:
        return {
            "content": [{
                "type": "text",
                "text": f"No contextual results found for: {query}"
            }],
            "isError": False
        }
    
    sections = [f"# Contextual Search Results: {query}\n"]
    
    for i, r in enumerate(results, 1):
        sections.append(f"## Result {i}")
        sections.append(f"**Source:** {r.get('source_doc_id', 'unknown')}")
        
        # Parse Q&A pairs
        qa_pairs = r.get('qa_pairs', [])
        if isinstance(qa_pairs, str):
            try:
                qa_pairs = json.loads(qa_pairs)
            except:
                qa_pairs = []
        
        if qa_pairs:
            sections.append("\n**Generated Q&A:**")
            for qa in qa_pairs[:3]:  # Show top 3
                sections.append(f"\nQ: {qa.get('question', 'N/A')}")
                sections.append(f"A: {qa.get('answer', 'N/A')}")
        
        sections.append(f"\n**Original Context:**")
        orig = r.get('original_content', '')[:300]
        sections.append(f"{orig}...")
        sections.append("\n---\n")
    
    return {
        "content": [{
            "type": "text",
            "text": "\n".join(sections)
        }],
        "isError": False
    }
