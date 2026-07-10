#!/usr/bin/env python3
"""
Ingest IBMB API Authentication (JWE) document into the database.
"""

import pdfplumber
import json
import os
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.utils.database import database

PDF_PATH = str(
    Path.home() / "Downloads/ibmb/API Auth _ JSON Web Encryption (JWE) - IBMB .pdf"
)
DOC_ID = "ibmb-api-auth-jwe"


def extract_text_from_pdf(pdf_path):
    """Extract all text from PDF."""
    print(f"Reading: {pdf_path}")
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(f"\n\n--- Page {i + 1} ---\n\n")
                text_parts.append(page_text)
    return "\n".join(text_parts)


async def ingest_document():
    """Ingest the auth document into database."""

    # Check if PDF exists
    if not os.path.exists(PDF_PATH):
        print(f"❌ Error: PDF not found: {PDF_PATH}")
        return False

    # Extract text
    print("=" * 70)
    print("INGESTING IBMB API AUTH DOCUMENT")
    print("=" * 70)

    full_text = extract_text_from_pdf(PDF_PATH)
    print(f"\nExtracted {len(full_text)} characters")

    # Connect to database
    await database.connect()
    print("✅ Database connected")

    conn = database.pool

    async with conn.acquire() as db_conn:
        # Check if document already exists
        existing = await db_conn.fetchval(
            "SELECT doc_id FROM documents WHERE doc_id = $1", DOC_ID
        )

        if existing:
            print(f"\nDocument '{DOC_ID}' already exists. Updating...")
            await db_conn.execute(
                """
                UPDATE documents 
                SET filename = $1, 
                    source_type = $2,
                    content = $3,
                    num_pages = $4,
                    total_chars = $5,
                    updated_at = CURRENT_TIMESTAMP
                WHERE doc_id = $6
            """,
                os.path.basename(PDF_PATH),
                "technical_spec",
                full_text,
                10,
                len(full_text),
                DOC_ID,
            )
        else:
            # Insert document record
            await db_conn.execute(
                """
                INSERT INTO documents (doc_id, filename, source_type, content, num_pages, total_chars)
                VALUES ($1, $2, $3, $4, $5, $6)
            """,
                DOC_ID,
                os.path.basename(PDF_PATH),
                "technical_spec",
                full_text,
                10,
                len(full_text),
            )

        print(f"✅ Document ingested: {DOC_ID}")

        # Verify
        doc = await db_conn.fetchrow(
            "SELECT doc_id, filename, num_pages, total_chars FROM documents WHERE doc_id = $1",
            DOC_ID,
        )

        print(f"\n" + "=" * 70)
        print("INGESTION COMPLETE")
        print("=" * 70)
        print(f"Document ID: {doc['doc_id']}")
        print(f"Filename: {doc['filename']}")
        print(f"Pages: {doc['num_pages']}")
        print(f"Characters: {doc['total_chars']}")

    await database.close()
    return True


if __name__ == "__main__":
    success = asyncio.run(ingest_document())
    sys.exit(0 if success else 1)
