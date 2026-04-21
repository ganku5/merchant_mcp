#!/usr/bin/env python3
"""Ingest IBMB files from Downloads folder."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, '/home/ganesh/merchant_mcp')

from src.utils.db import db
from src.ingestion.pipeline import IngestionPipeline


async def main():
    """Ingest all IBMB PDFs."""
    # Connect to database
    await db.connect()
    await db.init_schema()
    
    # Setup ingestion pipeline
    pipeline = IngestionPipeline()
    
    # Path to IBMB folder
    ibmb_folder = Path("/home/ganesh/Downloads/ibmb")
    
    if not ibmb_folder.exists():
        print(f"Error: Folder not found: {ibmb_folder}")
        return 1
    
    print(f"Ingesting files from: {ibmb_folder}")
    print("=" * 60)
    
    # Ingest all PDFs
    results = await pipeline.ingest_directory(ibmb_folder, "*.pdf")
    
    # Print results
    for result in results:
        print(f"\nFile: {result['file']}")
        print(f"Status: {result.get('status', 'unknown')}")
        
        if result.get('status') == 'success':
            print(f"  - Document ID: {result.get('doc_id')}")
            print(f"  - Chunks: {result.get('chunks')}")
            print(f"  - Entities extracted: {result.get('entities_extracted', {})}")
            print(f"  - Pages: {result.get('pages')}")
        elif result.get('status') == 'skipped':
            print(f"  - Reason: {result.get('reason')}")
        elif result.get('status') == 'error':
            print(f"  - Error: {result.get('error')}")
    
    print("\n" + "=" * 60)
    print("Ingestion complete!")
    
    # Show summary
    success = sum(1 for r in results if r.get('status') == 'success')
    skipped = sum(1 for r in results if r.get('status') == 'skipped')
    failed = sum(1 for r in results if r.get('status') == 'error')
    
    print(f"\nSummary:")
    print(f"  ✓ Successful: {success}")
    print(f"  ⊘ Skipped: {skipped}")
    print(f"  ✗ Failed: {failed}")
    
    await db.close()
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
