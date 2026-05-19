"""
Contextual Embedding Generator

Generates Q&A pairs from text content using LLM and creates contextual embeddings.
"""

import json
import re
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

    CONTEXTUAL_QA_GENERATION_PROMPT = """You are an expert at extracting knowledge from technical documentation.

Given a passage of text WITH its surrounding context, generate 3-5 relevant question-and-answer pairs that capture the key information.

Guidelines:
1. Questions should be specific and natural (as if a developer is asking)
2. Answers should be concise but complete, using information from the CURRENT CHUNK
3. Use surrounding context (Previous/Next chunks) to better understand the CURRENT CHUNK
4. Include different types:
   - Factual: "What is...?", "How does...?"
   - Procedural: "How do I...?", "What are the steps to...?"
   - Conceptual: "Why...?", "What is the purpose of...?"
5. If the text lacks sufficient detail, generate fewer pairs
6. Ensure answers are directly supported by the CURRENT CHUNK

Context Structure:
- Previous Chunk: Contains context that occurred before the current section
- Current Chunk: The main content to analyze (this is where answers come from)
- Next Chunk: Contains context that follows the current section

Format your response as a JSON array with this EXACT structure (do not deviate):
[{"question": "What is JWE?", "answer": "JSON Web Encryption is used for secure data transmission.", "type": "conceptual"}]

{{context_block}}

Generate Q&A pairs (respond ONLY with valid JSON array, no extra text):"""

    def __init__(self):
        self.stats = {
            "processed": 0,
            "generated": 0,
            "failed": 0
        }
    
    def _extract_json_array(self, content: str) -> List[Dict]:
        """Extract JSON array from LLM response, handling reasoning/thinking output."""
        # Find the first '[' and last ']'
        start_idx = content.find('[')
        end_idx = content.rfind(']')
        
        if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
            return []
        
        json_str = content[start_idx:end_idx + 1]
        
        # Try direct parsing first
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        # Try cleaning up common issues
        try:
            # Remove markdown code blocks if present
            if '```json' in json_str:
                json_str = json_str.split('```json')[1].split('```')[0]
            elif '```' in json_str:
                json_str = json_str.split('```')[1].split('```')[0]
            
            # Fix trailing commas before closing brackets
            cleaned = re.sub(r',\s*}', '}', json_str)
            cleaned = re.sub(r',\s*\]', ']', cleaned)
            
            # Fix newlines in property names (common with kimi-latest)
            cleaned = re.sub(r'\n\s*"', '\n"', cleaned)
            
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        
        # Try to find individual JSON objects as fallback
        try:
            # Find all {...} patterns
            objects = re.findall(r'\{[^{}]*"question"[^{}]*"answer"[^{}]*\}', json_str, re.DOTALL)
            pairs = []
            for obj in objects:
                try:
                    parsed = json.loads(obj)
                    if 'question' in parsed and 'answer' in parsed:
                        pairs.append(parsed)
                except:
                    continue
            if pairs:
                return pairs
        except:
            pass
        
        return []
    
    async def generate_qa_pairs(self, text: str, prev_chunk: str = "", next_chunk: str = "") -> List[Dict[str, str]]:
        """Generate Q&A pairs from text using LLM with surrounding context."""
        try:
            # Build context block with prev/current/next chunks
            context_parts = []
            if prev_chunk:
                context_parts.append(f"PREVIOUS CHUNK:\n{prev_chunk[:800]}...")
            context_parts.append(f"CURRENT CHUNK (Analyze this):\n{text[:1500]}")
            if next_chunk:
                context_parts.append(f"NEXT CHUNK:\n{next_chunk[:800]}...")
            
            context_block = "\n\n".join(context_parts)
            
            prompt = self.CONTEXTUAL_QA_GENERATION_PROMPT.replace('{{context_block}}', context_block)
            
            response = await llm_client.chat(
                messages=[
                    {"role": "system", "content": "You are a JSON-generating assistant. Extract Q&A pairs and output ONLY a valid JSON array. No explanation, no markdown formatting, just raw JSON starting with [ and ending with ]."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Lower temp for more consistent JSON
                max_tokens=1200
            )
            
            # Extract JSON from response
            content = response.strip()
            
            # Extract JSON array
            qa_pairs = self._extract_json_array(content)
            
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
            
        except Exception as e:
            import traceback
            print(f"⚠️ Error generating Q&A pairs: {repr(str(e)[:200])}")
            traceback.print_exc()
            return []
    
    async def generate_summary(self, text: str) -> str:
        """Generate a summary of the text."""
        try:
            prompt = self.SUMMARY_GENERATION_PROMPT.format(text=text[:3000])
            
            response = await llm_client.chat(
                messages=[
                    {"role": "system", "content": "You are a summarization assistant. Provide a concise 2-3 sentence summary. Output ONLY the summary text, no preamble, no explanation."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            # Clean up any reasoning/thinking output
            content = response.strip()
            
            # If response contains thinking markers, extract just the actual summary
            # Look for the last sentence that seems like a summary
            lines = [l.strip() for l in content.split('\n') if l.strip()]
            
            # Filter out meta-commentary lines
            summary_lines = []
            for line in lines:
                line_lower = line.lower()
                # Skip lines that look like internal thinking
                if any(marker in line_lower for marker in [
                    'the user wants', 'i need to', 'draft:', 'let me', 
                    'i should', 'actually,', 'looking at', 'this appears',
                    'wait,', 'hmm,', 'okay,', 'so,', 'first,', 'next,'
                ]):
                    continue
                summary_lines.append(line)
            
            # If we filtered too much, return last non-empty lines
            if not summary_lines and lines:
                summary_lines = lines[-3:]  # Last 3 lines as fallback
            
            return ' '.join(summary_lines)
            
        except Exception as e:
            print(f"⚠️ Error generating summary: {e}")
            return ""
    
    def combine_qa_to_context(
        self, 
        qa_pairs: List[Dict], 
        original_text: str, 
        summary: str = "",
        prev_chunk: str = "",
        next_chunk: str = ""
    ) -> str:
        """Combine Q&A pairs into a unified context string for embedding."""
        parts = []
        
        if summary:
            parts.append(f"Summary: {summary}")
        
        # Include context window for better semantic understanding
        if prev_chunk:
            parts.append(f"\n[Context - Previous]: {prev_chunk[:400]}...")
        
        parts.append(f"\nCurrent Content: {original_text[:500]}...")
        
        if next_chunk:
            parts.append(f"\n[Context - Following]: {next_chunk[:400]}...")
        
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
    
    async def process_chunk(
        self, 
        chunk_id: int, 
        doc_id: str, 
        content: str,
        prev_chunk: str = "",
        next_chunk: str = ""
    ) -> Optional[int]:
        """Process a single text chunk and create contextual embedding with surrounding context."""
        try:
            # Generate Q&A pairs with surrounding context
            qa_pairs = await self.generate_qa_pairs(content, prev_chunk, next_chunk)
            
            # Generate summary
            summary = await self.generate_summary(content)
            
            # Combine into context including prev/next chunks
            combined_context = self.combine_qa_to_context(qa_pairs, content, summary, prev_chunk, next_chunk)
            
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
    
    async def process_document(self, doc_id: str, batch_size: int = 3, force_regenerate: bool = False):
        """Process all chunks of a document with prev/next context awareness."""
        if database._pool is None:
            await database.connect()
        
        conn = database.pool
        
        async with conn.acquire() as db_conn:
            # Get ALL chunks ordered by index so we can build context windows
            if force_regenerate:
                chunks = await db_conn.fetch("""
                    SELECT tc.chunk_id, tc.chunk_text as content, tc.chunk_index
                    FROM text_chunks tc
                    WHERE tc.doc_id = $1
                    ORDER BY tc.chunk_index
                """, doc_id)
            else:
                # Get only chunks that don't have contextual embeddings yet
                chunks = await db_conn.fetch("""
                    SELECT tc.chunk_id, tc.chunk_text as content, tc.chunk_index
                    FROM text_chunks tc
                    LEFT JOIN contextual_embeddings ce ON tc.chunk_id = ce.source_chunk_id
                    WHERE tc.doc_id = $1
                      AND ce.context_id IS NULL
                    ORDER BY tc.chunk_index
                """, doc_id)
            
            if not chunks:
                print(f"📄 No new chunks to process for {doc_id}")
                return self.stats
            
            print(f"📄 Found {len(chunks)} chunks to process for {doc_id}")
            
            # Build a lookup for all chunks to get prev/next content
            chunk_lookup = {}
            for i, c in enumerate(chunks):
                chunk_lookup[c['chunk_id']] = {
                    'index': i,
                    'content': c['content']
                }
            
            # Process in batches with context
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                for c in batch:
                    idx = chunk_lookup[c['chunk_id']]['index']
                    
                    # Get prev/next chunk content
                    prev_content = chunks[idx - 1]['content'] if idx > 0 else ""
                    next_content = chunks[idx + 1]['content'] if idx < len(chunks) - 1 else ""
                    
                    await self.process_chunk(
                        c['chunk_id'], 
                        doc_id, 
                        c['content'],
                        prev_chunk=prev_content,
                        next_chunk=next_content
                    )
                
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
