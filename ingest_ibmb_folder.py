#!/usr/bin/env python3
"""
Batch ingestion script for IBMB folder documents.

Usage:
    python ingest_ibmb_folder.py [--skip-contextual]
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ingest import GenericIngester

IBMB_FOLDER = str(Path.home() / "Downloads/ibmb")

DOCUMENTS = [
    ("API Auth _ JSON Web Encryption (JWE) - IBMB .pdf", "api_auth_jwe"),
    ("[Axis] IBMB Bank Server API Specifications.pdf", "axis_bank_api_specs"),
    ("IBMB Acquiring - Merchant Integration.pdf", "ibmb_merchant_integration"),
    ("IBMB BO_User Manual_PA Portal_v1.0 (2)-1.pdf", "ibmb_pa_portal_manual"),
    (
        "IBMB Error Codes with Description v 3 2.xlsx - IBMB to PA & Bank.csv",
        "ibmb_error_codes",
    ),
]


async def ingest_document(
    ingester: GenericIngester, filename: str, doc_id: str
) -> dict:
    """Ingest a single document."""
    filepath = os.path.join(IBMB_FOLDER, filename)

    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return {"success": False, "error": "File not found", "doc_id": doc_id}

    print(f"\n{'=' * 70}")
    print(f"Processing: {filename}")
    print(f"Doc ID: {doc_id}")
    print("=" * 70)

    try:
        result = await ingester.ingest(filepath=filepath, doc_id=doc_id)
        print(f"✅ Successfully ingested {doc_id}")
        return {"success": True, "result": result, "doc_id": doc_id}
    except Exception as e:
        print(f"❌ Failed to ingest {doc_id}: {e}")
        import traceback

        traceback.print_exc()
        return {"success": False, "error": str(e), "doc_id": doc_id}


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Batch ingest IBMB documents")
    parser.add_argument(
        "--skip-contextual",
        action="store_true",
        help="Skip contextual embedding generation for faster ingestion",
    )
    parser.add_argument(
        "--single",
        metavar="DOC_ID",
        help="Ingest only a specific document by its doc_id",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("IBMB DOCUMENT BATCH INGESTION")
    print("=" * 70)
    print(f"Folder: {IBMB_FOLDER}")
    print(f"Documents: {len(DOCUMENTS)}")
    print(f"Skip contextual: {args.skip_contextual}")
    print(f"Single doc: {args.single or 'None (all documents)'}")

    ingester = GenericIngester(skip_contextual=args.skip_contextual)

    # Filter documents if single mode
    docs_to_process = DOCUMENTS
    if args.single:
        docs_to_process = [(f, d) for f, d in DOCUMENTS if d == args.single]
        if not docs_to_process:
            print(f"❌ Document '{args.single}' not found in list!")
            print(f"Available: {[d for _, d in DOCUMENTS]}")
            sys.exit(1)

    results = []
    for filename, doc_id in docs_to_process:
        result = await ingest_document(ingester, filename, doc_id)
        results.append(result)

    # Summary
    print("\n" + "=" * 70)
    print("BATCH INGESTION SUMMARY")
    print("=" * 70)

    successful = sum(1 for r in results if r.get("success"))
    failed = sum(1 for r in results if not r.get("success"))

    print(f"\nTotal: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")

    print("\nPer-Document Results:")
    print("-" * 70)
    for r in results:
        status = "✅" if r.get("success") else "❌"
        print(f"{status} {r['doc_id']}")
        if not r.get("success") and r.get("error"):
            print(f"   Error: {r['error'][:100]}")

    print("\n" + "=" * 70)
    if failed == 0:
        print("🎉 All documents ingested successfully!")
    else:
        print(f"⚠️  {failed} document(s) failed to ingest")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
