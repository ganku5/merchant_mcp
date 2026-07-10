#!/usr/bin/env python3
"""
Bulk ingest API specs from JSON files into the database.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.tools.api_specs_v2_tools import insert_api_spec_v2
from src.utils.database import database


API_SPECS_DIR = PROJECT_ROOT / "api_specs/ibmb"


async def load_and_insert_spec(filepath: str) -> dict:
    """Load a single API spec JSON file and insert into database."""
    try:
        with open(filepath, "r") as f:
            spec = json.load(f)

        # Insert using the tool
        result = await insert_api_spec_v2(spec)

        is_error = result.get("isError", False)
        content = result.get("content", [{}])[0].get("text", "Unknown result")

        return {
            "file": os.path.basename(filepath),
            "endpoint_id": spec.get("endpoint_id", "unknown"),
            "success": not is_error,
            "message": content[:200] if is_error else "Success",
        }
    except Exception as e:
        return {
            "file": os.path.basename(filepath),
            "endpoint_id": "unknown",
            "success": False,
            "message": str(e),
        }


async def clear_existing_data():
    """Clear existing API specs data."""
    conn = database.pool
    async with conn.acquire() as db_conn:
        print("Clearing existing API specs data...")
        await db_conn.execute("DELETE FROM api_samples")
        await db_conn.execute("DELETE FROM api_conditions")
        await db_conn.execute("DELETE FROM api_fields")
        await db_conn.execute("DELETE FROM api_headers")
        await db_conn.execute("DELETE FROM api_specs_v2")
        print("✅ Existing data cleared\n")


async def ingest_all_specs():
    """Ingest all API spec JSON files."""
    # Connect to database first
    await database.connect()
    print("✅ Database connected\n")

    # Clear existing data
    await clear_existing_data()

    # Find all JSON files (excluding combined/error/non-spec files)
    spec_files = []
    exclude_patterns = ["_all", "error_codes", "ibmb_error"]
    for filename in os.listdir(API_SPECS_DIR):
        if filename.endswith(".json") and not filename.startswith("_"):
            # Skip non-API spec files
            if any(pattern in filename.lower() for pattern in exclude_patterns):
                continue
            filepath = os.path.join(API_SPECS_DIR, filename)
            spec_files.append(filepath)

    print(f"Found {len(spec_files)} API spec files to ingest:\n")
    for f in spec_files:
        print(f"  - {os.path.basename(f)}")
    print()

    # Insert each spec
    results = []
    for filepath in spec_files:
        result = await load_and_insert_spec(filepath)
        results.append(result)

        status = "✅" if result["success"] else "❌"
        print(f"{status} {result['endpoint_id']}")
        if not result["success"]:
            print(f"   Error: {result['message']}")

    await database.close()

    # Summary
    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful

    print("\n" + "=" * 70)
    print("INGESTION SUMMARY")
    print("=" * 70)
    print(f"Total: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")

    if failed > 0:
        print("\nFailed inserts:")
        for r in results:
            if not r["success"]:
                print(f"  - {r['file']}: {r['message']}")

    return failed == 0


def main():
    """Main entry point."""
    print("=" * 70)
    print("BULK INGEST API SPECS")
    print("=" * 70)
    print(f"Source directory: {API_SPECS_DIR}\n")

    success = asyncio.run(ingest_all_specs())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
