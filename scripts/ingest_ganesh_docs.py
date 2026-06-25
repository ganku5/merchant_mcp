#!/usr/bin/env python3
import asyncio
import hashlib
import os
import re
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

from src.utils.llm import llm_client

DOC_DIR = Path("data/ganesh_docs")
NAMESPACE = "ganesh_shared_docs"


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def chunk_text(text: str, max_chars: int = 1800, overlap: int = 250):
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""

    for para in paras:
        if len(current) + len(para) + 2 <= max_chars:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            if len(para) > max_chars:
                start = 0
                while start < len(para):
                    chunks.append(para[start:start + max_chars])
                    start += max_chars - overlap
                current = ""
            else:
                current = para

    if current:
        chunks.append(current)

    return chunks


async def main():
    load_dotenv("load.env")

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL not found")

    files = sorted(list(DOC_DIR.glob("*.md")) + list(DOC_DIR.glob("*.txt")))
    if not files:
        raise RuntimeError(f"No md/txt files found in {DOC_DIR}")

    conn = await asyncpg.connect(db_url)

    try:
        total_chunks = 0

        for file_path in files:
            raw = file_path.read_text(encoding="utf-8")
            text = clean_text(raw)

            doc_hash = hashlib.sha1(str(file_path.name).encode()).hexdigest()[:10]
            doc_id = f"{NAMESPACE}_{doc_hash}"

            chunks = chunk_text(text)

            print(f"\nIngesting: {file_path.name}")
            print(f"doc_id={doc_id}, chars={len(text)}, chunks={len(chunks)}")

            await conn.execute("DELETE FROM text_chunks WHERE doc_id = $1", doc_id)

            await conn.execute(
                """
                INSERT INTO documents (doc_id, filename, source_type, content, num_pages, total_chars)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (doc_id) DO UPDATE SET
                    filename = EXCLUDED.filename,
                    source_type = EXCLUDED.source_type,
                    content = EXCLUDED.content,
                    num_pages = EXCLUDED.num_pages,
                    total_chars = EXCLUDED.total_chars,
                    updated_at = CURRENT_TIMESTAMP
                """,
                doc_id,
                file_path.name,
                "ganesh_google_doc_markdown",
                text,
                None,
                len(text),
            )

            batch_size = 20
            for start in range(0, len(chunks), batch_size):
                batch = chunks[start:start + batch_size]
                embeddings = await llm_client.embed(batch)

                for offset, (chunk, emb) in enumerate(zip(batch, embeddings)):
                    chunk_index = start + offset
                    emb_literal = "[" + ",".join(str(x) for x in emb) + "]"

                    await conn.execute(
                        """
                        INSERT INTO text_chunks (doc_id, chunk_index, chunk_text, embedding, namespace)
                        VALUES ($1, $2, $3, $4::vector, $5)
                        """,
                        doc_id,
                        chunk_index,
                        chunk,
                        emb_literal,
                        NAMESPACE,
                    )

                print(f"  inserted {min(start + batch_size, len(chunks))}/{len(chunks)} chunks")

            total_chunks += len(chunks)

        print(f"\nDone. Ingested {len(files)} docs, {total_chunks} chunks.")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
