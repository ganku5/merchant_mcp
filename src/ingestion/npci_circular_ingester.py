"""Ingestion for NPCI circular PDFs."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..ingestion.pdf_parser import PDFParser
from ..utils.database import database


NAMESPACE = "npci_circulars"
SOURCE_TYPE = "npci_circular"


def _safe_doc_id(path: Path) -> str:
    stem = re.sub(r"_[0-9a-f]{8,}$", "", path.stem.lower())
    stem = re.sub(r"[^a-z0-9]+", "_", stem).strip("_")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return f"npci_circular__{stem[:80]}__{digest}"


def _title_from_filename(path: Path) -> str:
    stem = re.sub(r"_[0-9a-f]{8,}$", "", path.stem)
    return re.sub(r"_+", " ", stem).strip()


def _run_pdftotext(path: Path) -> Tuple[List[str], str]:
    try:
        proc = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
        )
    except Exception:
        return [], ""

    if proc.returncode != 0 or not proc.stdout:
        return [], proc.stderr.strip()

    pages = [page.strip() for page in proc.stdout.split("\f")]
    return pages, ""


def _extract_with_pdfplumber(path: Path) -> Tuple[List[str], int]:
    try:
        parsed = PDFParser().parse(path)
    except Exception:
        return [], 0
    pages = [page.get("text", "").strip() for page in parsed.get("pages", [])]
    return pages, parsed.get("metadata", {}).get("num_pages", len(pages))


def _extract_pdf(path: Path) -> Tuple[List[str], int, str]:
    pages, error = _run_pdftotext(path)
    text_chars = sum(len(page.strip()) for page in pages)
    if text_chars > 100:
        return pages, len(pages), "parsed"

    fallback_pages, page_count = _extract_with_pdfplumber(path)
    fallback_chars = sum(len(page.strip()) for page in fallback_pages)
    if fallback_chars > text_chars:
        status = "parsed" if fallback_chars > 100 else "metadata_only"
        return fallback_pages, page_count, status

    status = "metadata_only"
    if error:
        status = f"metadata_only: {error[:120]}"
    return pages, len(pages), status


def _full_text(path: Path, title: str, pages: List[str], status: str) -> str:
    parts = []
    for index, page in enumerate(pages, 1):
        text = page.strip()
        if text:
            parts.append(f"--- Page {index} ---\n{text}")

    if parts:
        return "\n\n".join(parts)

    return (
        f"NPCI circular: {title}\n"
        f"File: {path.name}\n"
        f"Extraction status: {status}. Text could not be extracted from this PDF. "
        "The file may be scanned or image-only and may require OCR."
    )


def _chunk_pages(pages: List[str], fallback_text: str,
                 chunk_size: int = 1600, overlap: int = 180) -> List[Dict[str, Any]]:
    page_items = [(idx + 1, page.strip()) for idx, page in enumerate(pages) if page.strip()]
    if not page_items:
        return [{"text": fallback_text, "page_start": None, "page_end": None}]

    chunks: List[Dict[str, Any]] = []
    current = ""
    start_page: Optional[int] = None
    end_page: Optional[int] = None

    def flush() -> None:
        nonlocal current, start_page, end_page
        text = current.strip()
        if text:
            chunks.append({"text": text, "page_start": start_page, "page_end": end_page})
        if len(text) > overlap:
            current = text[-overlap:]
            start_page = end_page
        else:
            current = ""
            start_page = None

    for page_num, page_text in page_items:
        page_block = f"\n\n--- Page {page_num} ---\n{page_text}"
        if start_page is None:
            start_page = page_num
        end_page = page_num

        if len(current) + len(page_block) > chunk_size and current:
            flush()
            if start_page is None:
                start_page = page_num
            end_page = page_num

        current += page_block

        while len(current) > chunk_size:
            chunk_text = current[:chunk_size].strip()
            chunks.append({"text": chunk_text, "page_start": start_page, "page_end": end_page})
            current = current[max(0, chunk_size - overlap):]
            start_page = end_page

    if current.strip():
        chunks.append({"text": current.strip(), "page_start": start_page, "page_end": end_page})

    return [chunk for chunk in chunks if len(chunk["text"]) > 30]


async def _embed_batch(texts: List[str]) -> List[Optional[List[float]]]:
    try:
        from ..utils.llm import llm_client

        return await llm_client.embed(texts)
    except Exception:
        return [None] * len(texts)


async def _replace_chunks(doc_id: str, chunks: List[Dict[str, Any]],
                          with_embeddings: bool) -> Tuple[int, int]:
    async with database.pool.acquire() as conn:
        await conn.execute("DELETE FROM text_chunks WHERE doc_id = $1", doc_id)

    inserted = 0
    embedded = 0
    for offset in range(0, len(chunks), 8):
        batch = chunks[offset:offset + 8]
        embeddings = await _embed_batch([chunk["text"] for chunk in batch]) if with_embeddings else [None] * len(batch)
        async with database.pool.acquire() as conn:
            for index, chunk in enumerate(batch, offset):
                embedding = embeddings[index - offset] if embeddings else None
                if embedding:
                    embedded += 1
                await conn.execute(
                    """INSERT INTO text_chunks (doc_id, chunk_index, chunk_text, embedding, namespace)
                       VALUES ($1, $2, $3, $4, $5)
                       ON CONFLICT (doc_id, chunk_index) DO UPDATE SET
                           chunk_text = EXCLUDED.chunk_text,
                           embedding = EXCLUDED.embedding,
                           namespace = EXCLUDED.namespace""",
                    doc_id,
                    index,
                    chunk["text"],
                    json.dumps(embedding) if embedding else None,
                    NAMESPACE,
                )
                inserted += 1
    return inserted, embedded


async def ingest_npci_circulars(directory: str = "downloads/npci_circulars",
                                limit: Optional[int] = None,
                                with_embeddings: bool = False,
                                dry_run: bool = False) -> Dict[str, Any]:
    base = Path(directory).expanduser()
    if not base.is_absolute():
        base = Path.cwd() / base
    base = base.resolve()

    files = sorted(base.glob("*.pdf"))
    if limit:
        files = files[:limit]

    if dry_run:
        return {
            "content": [{
                "type": "text",
                "text": f"Dry run found {len(files)} NPCI circular PDFs in {base}",
            }],
            "isError": False,
        }

    if database._pool is None:
        await database.connect()

    stats = {
        "files": len(files),
        "documents": 0,
        "chunks": 0,
        "embedded_chunks": 0,
        "metadata_only": 0,
        "failed": [],
    }

    for path in files:
        try:
            title = _title_from_filename(path)
            doc_id = _safe_doc_id(path)
            pages, num_pages, status = _extract_pdf(path)
            text = _full_text(path, title, pages, status)
            chunks = _chunk_pages(pages, text)

            await database.insert_document(
                doc_id=doc_id,
                filename=path.name,
                content=text,
                num_pages=num_pages,
                source_type=SOURCE_TYPE,
            )

            chunk_count, embedded = await _replace_chunks(doc_id, chunks, with_embeddings)

            stats["documents"] += 1
            stats["chunks"] += chunk_count
            stats["embedded_chunks"] += embedded
            if status.startswith("metadata_only"):
                stats["metadata_only"] += 1
        except Exception as exc:
            stats["failed"].append({"file": path.name, "error": str(exc)})

    failed_lines = "\n".join(f"- {item['file']}: {item['error']}" for item in stats["failed"][:10])
    text = (
        "# NPCI Circular Ingestion Complete\n\n"
        f"- PDFs found: {stats['files']}\n"
        f"- Documents stored: {stats['documents']}\n"
        f"- Chunks stored: {stats['chunks']}\n"
        f"- Embedded chunks: {stats['embedded_chunks']}\n"
        f"- Metadata-only PDFs: {stats['metadata_only']}\n"
        f"- Failed: {len(stats['failed'])}"
    )
    if failed_lines:
        text += f"\n\n## Failures\n{failed_lines}"

    return {"content": [{"type": "text", "text": text}], "isError": bool(stats["failed"])}
