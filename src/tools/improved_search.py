"""
Improved hybrid search combining text chunks and contextual embeddings.
"""

import json
import numpy as np
from typing import List, Dict, Any, Optional
from ..utils.database import database
from ..utils.llm import llm_client


async def hybrid_search(
    query: str,
    doc_id: Optional[str] = None,
    top_k: int = 5,
    use_keyword: bool = True,
    use_contextual: bool = True
) -> List[Dict]:
    """
    Hybrid search combining keyword search on text chunks and contextual embeddings.
    Falls back to raw text chunks which contain the actual detailed documentation.
    """
    results = []
    seen_chunks = set()
    
    if database._pool is None:
        await database.connect()
    
    conn = database.pool
    
    async with conn.acquire() as db_conn:
        # PRIMARY: Keyword search on RAW text chunks (always works, has full content)
        if use_keyword:
            # Split query into words for broader matching
            search_terms = query.lower().split()
            
            if doc_id:
                # Get chunks matching ANY search term
                chunk_results = await db_conn.fetch("""
                    SELECT 
                        tc.chunk_id,
                        tc.doc_id,
                        tc.chunk_text as content,
                        tc.chunk_index,
                        d.filename,
                        CASE 
                            WHEN tc.chunk_text ILIKE $2 THEN 2.0
                            WHEN tc.chunk_text ILIKE $3 THEN 1.5
                            WHEN tc.chunk_text ILIKE $4 THEN 1.0
                            ELSE 0.5
                        END as relevance
                    FROM text_chunks tc
                    JOIN documents d ON tc.doc_id = d.doc_id
                    WHERE tc.doc_id = $1 
                      AND (
                          tc.chunk_text ILIKE $2 
                          OR tc.chunk_text ILIKE $3 
                          OR tc.chunk_text ILIKE $4
                      )
                    ORDER BY relevance DESC, tc.chunk_index
                    LIMIT $5
                """, 
                    doc_id, 
                    f"%{query}%",  # Exact phrase
                    f"%{search_terms[0]}%" if search_terms else f"%{query}%",  # First word
                    f"%{search_terms[-1]}%" if len(search_terms) > 1 else f"%{query}%",  # Last word
                    top_k * 2
                )
            else:
                chunk_results = await db_conn.fetch("""
                    SELECT 
                        tc.chunk_id,
                        tc.doc_id,
                        tc.chunk_text as content,
                        tc.chunk_index,
                        d.filename,
                        LENGTH(tc.chunk_text) as relevance
                    FROM text_chunks tc
                    JOIN documents d ON tc.doc_id = d.doc_id
                    WHERE tc.chunk_text ILIKE $1
                    ORDER BY LENGTH(tc.chunk_text) DESC
                    LIMIT $2
                """, f"%{query}%", top_k * 2)
            
            for r in chunk_results:
                if r['chunk_id'] not in seen_chunks:
                    results.append({
                        'source': 'text_chunk',
                        'doc_id': r['doc_id'],
                        'filename': r['filename'],
                        'content': r['content'],
                        'chunk_index': r['chunk_index'],
                        'score': r.get('relevance', 0.5)
                    })
                    seen_chunks.add(r['chunk_id'])
        
        # 2. Search contextual embeddings (higher quality when available)
        if use_contextual:
            search_pattern = f"%{query}%"
            
            if doc_id:
                ctx_results = await db_conn.fetch("""
                    SELECT 
                        ce.context_id,
                        ce.source_doc_id as doc_id,
                        ce.original_content as content,
                        ce.qa_pairs,
                        ce.combined_context,
                        tc.chunk_index,
                        d.filename
                    FROM contextual_embeddings ce
                    JOIN text_chunks tc ON ce.source_chunk_id = tc.chunk_id
                    JOIN documents d ON ce.source_doc_id = d.doc_id
                    WHERE ce.source_doc_id = $1
                      AND (
                          ce.combined_context ILIKE $2 
                          OR ce.original_content ILIKE $2
                          OR ce.qa_pairs::text ILIKE $2
                      )
                    LIMIT $3
                """, doc_id, search_pattern, top_k * 2)
            else:
                ctx_results = await db_conn.fetch("""
                    SELECT 
                        ce.context_id,
                        ce.source_doc_id as doc_id,
                        ce.original_content as content,
                        ce.qa_pairs,
                        ce.combined_context,
                        tc.chunk_index,
                        d.filename
                    FROM contextual_embeddings ce
                    JOIN text_chunks tc ON ce.source_chunk_id = tc.chunk_id
                    JOIN documents d ON ce.source_doc_id = d.doc_id
                    WHERE ce.combined_context ILIKE $1 
                       OR ce.original_content ILIKE $1
                       OR ce.qa_pairs::text ILIKE $1
                    LIMIT $2
                """, search_pattern, top_k * 2)
            
            for r in ctx_results:
                chunk_key = f"{r['doc_id']}_{r['chunk_index']}"
                
                # Parse Q&A pairs
                qa_pairs = r['qa_pairs'] or '[]'
                if isinstance(qa_pairs, str):
                    try:
                        qa_pairs = json.loads(qa_pairs)
                    except:
                        qa_pairs = []
                
                result = {
                    'source': 'contextual_embedding',
                    'doc_id': r['doc_id'],
                    'filename': r['filename'],
                    'content': r['combined_context'] or r['content'],
                    'original_content': r['content'],
                    'chunk_index': r['chunk_index'],
                    'qa_pairs': qa_pairs,
                    'score': 1.0  # Higher score for contextual match
                }
                
                if chunk_key in seen_chunks:
                    # Upgrade existing result
                    for i, existing in enumerate(results):
                        if existing.get('chunk_index') == r['chunk_index'] and existing.get('doc_id') == r['doc_id']:
                            results[i] = result
                            break
                else:
                    results.append(result)
                    seen_chunks.add(chunk_key)
    
    # Sort by score and return top_k
    results.sort(key=lambda x: x.get('score', 0), reverse=True)
    return results[:top_k]


async def search_with_qa_format(query: str, doc_id: Optional[str] = None, top_k: int = 5) -> str:
    """
    Search and return formatted results with Q&A when available.
    """
    results = await hybrid_search(query, doc_id, top_k)
    
    if not results:
        return f"No results found for: {query}"
    
    sections = [f"# Search Results: {query}\n"]
    
    for i, r in enumerate(results, 1):
        sections.append(f"## Result {i} ({r['source']})")
        sections.append(f"**Source:** {r['filename']} (Chunk {r['chunk_index']})")
        
        # Show Q&A pairs if available
        if r.get('qa_pairs') and len(r['qa_pairs']) > 0:
            sections.append("\n**Generated Q&A:**")
            for qa in r['qa_pairs'][:3]:
                q = qa.get('question', 'N/A')
                a = qa.get('answer', 'N/A')
                sections.append(f"\n**Q:** {q}")
                sections.append(f"**A:** {a}")
        
        # Show content preview
        content = r.get('content', '')
        if len(content) > 500:
            content = content[:500] + "..."
        sections.append(f"\n**Content:**\n{content}")
        sections.append("\n---\n")
    
    return "\n".join(sections)
