#!/usr/bin/env python3
"""
Ingest all IBMB documents with full contextual embedding generation.
Skips documents that are already ingested.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ingest import GenericIngester

IBMB_FOLDER = "/home/ganesh/Downloads/ibmb"

# All documents except Merchant Integration
DOCUMENTS = [
    ("API Auth _ JSON Web Encryption (JWE) - IBMB .pdf", "api_auth_jwe"),
    ("[Axis] IBMB Bank Server API Specifications.pdf", "axis_bank_api_specs"),
    ("IBMB BO_User Manual_PA Portal_v1.0 (2)-1.pdf", "ibmb_pa_portal_manual"),
    ("IBMB Error Codes with Description v 3 2.xlsx - IBMB to PA & Bank.csv", "ibmb_error_codes"),
]


async def ingest_document(ingester: GenericIngester, filename: str, doc_id: str) -> dict:
    """Ingest a single document with full contextual embeddings."""
    filepath = os.path.join(IBMB_FOLDER, filename)
    
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return {"success": False, "error": "File not found", "doc_id": doc_id}
    
    print(f"\n{'='*70}")
    print(f"Processing: {filename}")
    print(f"Doc ID: {doc_id}")
    print('='*70)
    
    try:
        result = await ingester.ingest(filepath=filepath, doc_id=doc_id)
        print(f"\n✅ Successfully ingested {doc_id}")
        return {"success": True, "result": result, "doc_id": doc_id}
    except Exception as e:
        print(f"\n❌ Failed to ingest {doc_id}: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e), "doc_id": doc_id}


async def main():
    print("="*70)
    print("IBMB DOCUMENT FULL INGESTION")
    print("="*70)
    print(f"Folder: {IBMB_FOLDER}")
    print(f"Documents to process: {len(DOCUMENTS)}")
    print("Note: Full contextual embedding generation will take 30-60 minutes per PDF")
    print("="*70)
    
    ingester = GenericIngester(skip_contextual=False)
    
    results = []
    for filename, doc_id in DOCUMENTS:
        result = await ingest_document(ingester, filename, doc_id)
        results.append(result)
    
    # Summary
    print("\n" + "="*70)
    print("FULL INGESTION SUMMARY")
    print("="*70)
    
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
        if r.get("success") and r.get("result"):
            res = r["result"]
            if "chunks" in res:
                print(f"   Chunks: {res.get('chunks', 'N/A')}")
            if "count" in res:
                print(f"   Records: {res.get('count', 'N/A')}")
        if not r.get("success") and r.get("error"):
            print(f"   Error: {r['error'][:100]}")
    
    print("\n" + "="*70)
    if failed == 0:
        print("🎉 All documents ingested successfully with contextual embeddings!")
    else:
        print(f"⚠️  {failed} document(s) failed")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
