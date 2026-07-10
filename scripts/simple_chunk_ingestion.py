#!/usr/bin/env python3
"""Ultra-simple chunk ingestion without heavy processing."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.database import database


async def simple_ingest():
    """Simple ingestion without embeddings."""
    print("=" * 70)
    print("SIMPLE CHUNK INGESTION (No Embeddings)")
    print("=" * 70)

    await database.connect()

    async with database.pool.acquire() as conn:
        # Get existing document
        doc = await conn.fetchrow(
            "SELECT doc_id, content FROM documents WHERE doc_id = 'ibmb_axis_api_specs'"
        )

        if not doc:
            print("No document found!")
            return

        print(f"Document: {doc['doc_id']}")
        print(f"Content size: {len(doc['content'])} chars")

        # Simple chunking by paragraphs/pages
        text = doc["content"]

        # Split by page markers
        pages = text.split("--- Page ")

        print(f"\nFound {len(pages)} sections")

        # Delete old chunks
        await conn.execute("DELETE FROM text_chunks WHERE doc_id = $1", doc["doc_id"])
        print("Old chunks deleted")

        # Store chunks (without embeddings for now)
        chunk_count = 0
        for i, page in enumerate(pages):
            if not page.strip():
                continue

            # Limit chunk size
            chunk_text = page.strip()[:1500]

            await conn.execute(
                """
                INSERT INTO text_chunks (doc_id, chunk_index, chunk_text, embedding, namespace)
                VALUES ($1, $2, $3, $4, $5)
            """,
                doc["doc_id"],
                i,
                chunk_text,
                None,
                "pdf_ibmb",
            )

            chunk_count += 1
            if chunk_count % 10 == 0:
                print(f"  Stored {chunk_count} chunks...")

        print(f"\n✅ Stored {chunk_count} chunks (no embeddings)")

        # Show stats
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM text_chunks WHERE doc_id = $1", doc["doc_id"]
        )
        print(f"Verified: {total} chunks in database")

    await database.close()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(simple_ingest())
