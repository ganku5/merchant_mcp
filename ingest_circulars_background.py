#!/usr/bin/env python3
"""
Background ingestion script for circular/TSD/RMD files.
Runs with contextual embedding generation.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ingest import GenericIngester

CIRCULARS = [
    (
        str(
            Path.home()
            / "Downloads/RMD 001 to prevent  misleading VPA creation_260620.pdf"
        ),
        "rmd_001_vpa_creation",
    ),
    (
        str(Path.home() / "Downloads/UPI+OC+141-Safeguarding+Users+on+UPI+(1).pdf"),
        "upi_oc_141_safeguard_users",
    ),
    (
        str(Path.home() / "Downloads/UPI_Error_and_Response_Codes_2_9.pdf"),
        "upi_error_response_codes",
    ),
    (str(Path.home() / "Downloads/TSD_IBMB_1.5.pdf"), "tsd_ibmb_1_5"),
    (
        str(Path.home() / "Downloads/TSD -AutoPay Interoperability V1.5.pdf"),
        "tsd_autopay_interoperability",
    ),
    (
        str(Path.home() / "Downloads/Multi-Signatory Accounts on UPI TSD v.1.4.pdf"),
        "tsd_multi_signatory_accounts",
    ),
    (
        str(Path.home() / "Downloads/Contextual_Payments_V1.1_TSD.pdf"),
        "contextual_payments_tsd",
    ),
]


async def ingest_all():
    """Ingest all circular files with contextual embeddings."""
    print("=" * 80)
    print("CIRCULAR/TSD/RMD INGESTION - BACKGROUND PROCESS")
    print("=" * 80)
    print(f"Files to process: {len(CIRCULARS)}")
    print("This will take approximately 2-3 hours for full contextual generation")
    print("=" * 80)

    ingester = GenericIngester(skip_contextual=False)
    results = []

    for filepath, doc_id in CIRCULARS:
        if not os.path.exists(filepath):
            print(f"\n❌ File not found: {filepath}")
            results.append(
                {"doc_id": doc_id, "status": "missing", "error": "File not found"}
            )
            continue

        print(f"\n{'=' * 80}")
        print(f"Processing: {os.path.basename(filepath)}")
        print(f"Doc ID: {doc_id}")
        print("=" * 80)

        try:
            result = await ingester.ingest(filepath=filepath, doc_id=doc_id)
            results.append(
                {
                    "doc_id": doc_id,
                    "status": "success",
                    "chunks": result.get("chunks", 0),
                    "pages": result.get("pages", 0),
                }
            )
            print(f"\n✅ Successfully ingested {doc_id}")
        except Exception as e:
            print(f"\n❌ Failed to ingest {doc_id}: {e}")
            import traceback

            traceback.print_exc()
            results.append({"doc_id": doc_id, "status": "failed", "error": str(e)})

    # Summary
    print("\n" + "=" * 80)
    print("CIRCULAR INGESTION COMPLETE")
    print("=" * 80)

    successful = sum(1 for r in results if r.get("status") == "success")
    failed = sum(1 for r in results if r.get("status") == "failed")
    missing = sum(1 for r in results if r.get("status") == "missing")

    print(f"\nTotal: {len(results)}")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    print(f"📄 Missing: {missing}")

    print("\nDetailed Results:")
    for r in results:
        status_icon = (
            "✅"
            if r["status"] == "success"
            else "❌"
            if r["status"] == "failed"
            else "📄"
        )
        print(f"{status_icon} {r['doc_id']}: {r['status']}")
        if "chunks" in r:
            print(f"   Chunks: {r['chunks']}, Pages: {r['pages']}")
        if "error" in r and r["status"] != "success":
            print(f"   Error: {r['error'][:100]}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(ingest_all())
