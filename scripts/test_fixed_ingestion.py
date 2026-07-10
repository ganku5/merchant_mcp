#!/usr/bin/env python3
"""Test the fixed ingestion pipeline with one document."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingestion.pipeline_fixed import DocumentIngester, database


async def test_ingestion():
    """Test ingestion with one PDF."""
    print("=" * 70)
    print("TESTING FIXED INGESTION PIPELINE")
    print("=" * 70)

    await database.connect()

    ingester = DocumentIngester()

    # Test with the main IBMB spec PDF
    pdf_path = str(
        Path.home() / "Downloads/ibmb/[Axis] IBMB Bank Server API Specifications.pdf"
    )
    doc_id = "ibmb_axis_api_specs"

    print(f"\n📄 Testing: {pdf_path}")

    try:
        result = await ingester.ingest_pdf(pdf_path, doc_id)
        print(f"\n✅ SUCCESS!")
        print(f"   Doc ID: {result['doc_id']}")
        print(f"   Total chars: {result['total_chars']}")
        print(f"   Chunks: {result['chunks_created']}")

        # Verify in DB
        async with database.pool.acquire() as conn:
            chunks = await conn.fetch(
                """
                SELECT COUNT(*) as total,
                       COUNT(*) FILTER (WHERE embedding IS NOT NULL) as with_embed
                FROM text_chunks WHERE doc_id = $1
            """,
                doc_id,
            )

            total = chunks[0]["total"]
            with_embed = chunks[0]["with_embed"]

            print(f"\n📊 Database Verification:")
            print(f"   Total chunks: {total}")
            print(f"   With embeddings: {with_embed}")
            print(
                f"   Embedding rate: {with_embed / total * 100:.1f}%"
                if total > 0
                else "   N/A"
            )

            # Show sample chunk
            if total > 0:
                sample = await conn.fetchrow(
                    """
                    SELECT chunk_text, embedding IS NOT NULL as has_embed
                    FROM text_chunks WHERE doc_id = $1 LIMIT 1
                """,
                    doc_id,
                )
                print(f"\n📝 Sample chunk (first 200 chars):")
                print(f"   {sample['chunk_text'][:200]}...")
                print(f"   Has embedding: {sample['has_embed']}")

    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback

        traceback.print_exc()

    await database.close()
    print("\n✅ Test complete!")


if __name__ == "__main__":
    asyncio.run(test_ingestion())
