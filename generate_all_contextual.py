#!/usr/bin/env python3
"""
Generate contextual embeddings for all IBMB PDF documents.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.tools.contextual_embedding_generator import ContextualEmbeddingGenerator
from src.utils.database import database

IBMB_DIR = str(Path.home() / "Downloads/ibmb")


async def get_pdf_documents():
    """Get all PDF documents from database."""
    if database._pool is None:
        await database.connect()

    conn = database.pool
    async with conn.acquire() as db_conn:
        # Get documents that are PDFs from IBMB folder
        docs = await db_conn.fetch("""
            SELECT doc_id, filename 
            FROM documents 
            WHERE filename LIKE '%.pdf%'
            ORDER BY doc_id
        """)
        return [(d["doc_id"], d["filename"]) for d in docs]


async def process_document(
    generator: ContextualEmbeddingGenerator, doc_id: str, filename: str
):
    """Process a single document."""
    print(f"\n{'=' * 70}")
    print(f"Processing: {filename}")
    print(f"Doc ID: {doc_id}")
    print("=" * 70)

    try:
        stats = await generator.process_document(doc_id)
        return {
            "doc_id": doc_id,
            "filename": filename,
            "success": True,
            "processed": stats["processed"],
            "generated": stats["generated"],
            "failed": stats["failed"],
        }
    except Exception as e:
        print(f"❌ Error processing {doc_id}: {e}")
        return {
            "doc_id": doc_id,
            "filename": filename,
            "success": False,
            "error": str(e),
        }


async def main():
    print("=" * 70)
    print("GENERATING CONTEXTUAL EMBEDDINGS FOR ALL IBMB PDFs")
    print("=" * 70)

    # Get all PDF documents
    documents = await get_pdf_documents()
    print(f"\nFound {len(documents)} PDF documents:\n")
    for doc_id, filename in documents:
        print(f"  - {doc_id}: {filename}")

    # Initialize generator
    generator = ContextualEmbeddingGenerator()

    # Process each document
    results = []
    for doc_id, filename in documents:
        result = await process_document(generator, doc_id, filename)
        results.append(result)

    # Summary
    print("\n" + "=" * 70)
    print("GENERATION SUMMARY")
    print("=" * 70)

    total_processed = sum(r.get("processed", 0) for r in results if r.get("success"))
    total_generated = sum(r.get("generated", 0) for r in results if r.get("success"))
    total_failed = sum(r.get("failed", 0) for r in results if r.get("success"))

    print(f"\nTotal Documents: {len(results)}")
    print(f"Successful: {sum(1 for r in results if r.get('success'))}")
    print(f"Failed: {sum(1 for r in results if not r.get('success'))}")
    print(f"\nTotal Chunks Processed: {total_processed}")
    print(f"Total Q&A Pairs Generated: {total_generated}")
    print(f"Total Failures: {total_failed}")

    print("\nPer-Document Breakdown:")
    print("-" * 70)
    for r in results:
        status = "✅" if r.get("success") else "❌"
        if r.get("success"):
            print(
                f"{status} {r['doc_id']}: {r['processed']} chunks, {r['generated']} Q&A pairs"
            )
        else:
            print(f"{status} {r['doc_id']}: FAILED - {r.get('error', 'Unknown error')}")

    await database.close()
    print("\n✅ All done!")


if __name__ == "__main__":
    asyncio.run(main())
