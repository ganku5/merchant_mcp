"""Operational MCP tools for ingestion, context management, and answers."""

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.database import database


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _response(text: str, is_error: bool = False) -> Dict[str, Any]:
    return {
        "content": [{"type": "text", "text": text}],
        "isError": is_error,
    }


def _safe_doc_id(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("_")
    return cleaned.lower() or "document"


def _chunk_text(text: str, size: int = 900, overlap: int = 150) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunk = text[start:end].strip()
        if len(chunk) > 30:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


async def ingest_document(
    filepath: str,
    doc_id: Optional[str] = None,
    force_type: Optional[str] = None,
    skip_contextual: bool = True,
) -> Dict[str, Any]:
    """Ingest a local PDF, text, CSV, JSON, YAML, or OpenAPI file into the MCP tables."""
    path = Path(filepath).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path = path.resolve()

    if not path.exists() or not path.is_file():
        return _response(f"File not found: {path}", True)

    if database._pool is None:
        await database.connect()

    try:
        from ingest import GenericIngester

        ingester = GenericIngester(skip_contextual=skip_contextual)
        result = await ingester.ingest(
            filepath=str(path),
            doc_id=doc_id,
            force_type=force_type,
        )
        return _response(
            "# Ingestion Complete\n\n"
            f"Source: `{path}`\n\n"
            f"```json\n{json.dumps(result, indent=2, default=str)}\n```"
        )
    except Exception as exc:
        return _response(f"Ingestion failed for `{path}`: {exc}", True)


async def add_context(
    title: str,
    content: str,
    doc_id: Optional[str] = None,
    namespace: str = "manual_context",
    source_type: str = "manual",
    generate_contextual: bool = False,
) -> Dict[str, Any]:
    """Add direct text context into documents/text_chunks for later client Q&A."""
    if not content or not content.strip():
        return _response("content is required", True)

    if database._pool is None:
        await database.connect()

    doc_id = _safe_doc_id(doc_id or title)
    text = content.replace("\x00", "").strip()
    chunks = _chunk_text(text)

    await database.insert_document(
        doc_id=doc_id,
        filename=title,
        content=text[:100000],
        num_pages=1,
        source_type=source_type,
    )

    async with database.pool.acquire() as conn:
        await conn.execute("DELETE FROM text_chunks WHERE doc_id = $1", doc_id)

    embedded = 0
    for i in range(0, len(chunks), 5):
        batch = chunks[i:i + 5]
        try:
            from ..utils.llm import llm_client

            embeddings = await llm_client.embed(batch)
        except Exception:
            embeddings = [None] * len(batch)

        for j, chunk in enumerate(batch):
            embedding = embeddings[j] if embeddings and embeddings[j] else None
            if embedding:
                embedded += 1
            await database.insert_text_chunk(
                doc_id=doc_id,
                chunk_index=i + j,
                chunk_text=chunk,
                embedding=embedding,
                namespace=namespace,
            )

    contextual = None
    if generate_contextual:
        try:
            from .contextual_embedding_generator import ContextualEmbeddingGenerator

            generator = ContextualEmbeddingGenerator()
            contextual = await generator.process_document(doc_id)
        except Exception as exc:
            contextual = {"error": str(exc)}

    return _response(
        "# Context Added\n\n"
        f"- Document ID: `{doc_id}`\n"
        f"- Namespace: `{namespace}`\n"
        f"- Chunks: {len(chunks)}\n"
        f"- Embedded chunks: {embedded}\n"
        f"- Contextual generation: `{json.dumps(contextual) if contextual is not None else 'skipped'}`"
    )


async def add_api_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Add or update a rich v2 API specification."""
    if not isinstance(spec, dict):
        return _response("spec must be a JSON object", True)

    required = ["endpoint_id", "method", "path"]
    missing = [field for field in required if not spec.get(field)]
    if missing:
        return _response(f"Missing required spec fields: {', '.join(missing)}", True)

    from .api_specs_v2_tools import insert_api_spec_v2

    return await insert_api_spec_v2(spec)


async def list_queryable_tables() -> Dict[str, Any]:
    """List public tables available to the MCP database user."""
    if database._pool is None:
        await database.connect()

    async with database.pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT table_name
               FROM information_schema.tables
               WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
               ORDER BY table_name"""
        )

    tables = [row["table_name"] for row in rows]
    return _response("# Queryable Tables\n\n" + "\n".join(f"- `{table}`" for table in tables))


async def get_database_overview() -> Dict[str, Any]:
    """Get current MCP database counts and ingestion health."""
    if database._pool is None:
        await database.connect()

    stats = await database.get_stats()
    rows = [f"- `{key}`: {value}" for key, value in sorted(stats.items())]
    return _response("# MCP Database Overview\n\n" + "\n".join(rows))


async def answer_question(question: str, doc_id: Optional[str] = None, limit: int = 6) -> Dict[str, Any]:
    """Answer a client question using ingested API specs and document context."""
    if not question or not question.strip():
        return _response("question is required", True)

    if database._pool is None:
        await database.connect()

    from .improved_search import hybrid_search
    from ..utils.llm import llm_client

    results = await hybrid_search(question.strip(), doc_id=doc_id, top_k=limit)
    if not results:
        return _response(f"No ingested context matched: {question}", True)

    context_blocks = []
    sources = []
    for idx, result in enumerate(results, 1):
        source = f"{result.get('filename', 'unknown')}#{result.get('chunk_index', 'n/a')}"
        sources.append(source)
        content = (result.get("original_content") or result.get("content") or "")[:1400]
        context_blocks.append(f"[{idx}] Source: {source}\n{content}")

    prompt = (
        "Answer the client's question using only the provided MCP documentation context. "
        "If the context is insufficient, say what is missing and suggest the next MCP lookup.\n\n"
        f"Question: {question}\n\n"
        "Context:\n"
        + "\n\n---\n\n".join(context_blocks)
    )

    try:
        answer = await llm_client.chat(
            [
                {
                    "role": "system",
                    "content": "You answer merchant integration questions from retrieved documentation. Be precise and cite source numbers.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=900,
        )
    except Exception:
        answer = (
            "LLM answer generation failed, but relevant context was retrieved.\n\n"
            + "\n\n---\n\n".join(context_blocks)
        )

    source_lines = "\n".join(f"- [{i}] {source}" for i, source in enumerate(sources, 1))
    return _response(f"# Answer\n\n{answer.strip()}\n\n## Sources\n{source_lines}")


async def fingerprint_context(content: str) -> Dict[str, Any]:
    """Return a stable fingerprint for context before ingestion/deduplication."""
    digest = hashlib.sha256((content or "").encode("utf-8")).hexdigest()
    return _response(json.dumps({"sha256": digest, "chars": len(content or "")}, indent=2))
