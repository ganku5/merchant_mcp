#!/usr/bin/env python3
"""Scrape web docs, convert to structured markdown, and optionally ingest.

Usage:
    # From env (WEB_SCRAPER_URLS="url1,url2")
    uv run python scripts/ingest_web_docs.py

    # From file
    uv run python scripts/ingest_web_docs.py --urls-file urls.txt

    # Scrape + ingest in one step
    uv run python scripts/ingest_web_docs.py --urls-file urls.txt --ingest

    # Just ingest an existing scraped_docs/ dir
    uv run python scripts/ingest_web_docs.py --ingest
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingestion.web_scraper import WebDocIngester
from src.utils.config import Config


def collect_urls(urls_file: str | None) -> list[str]:
    urls: list[str] = []

    env_urls = Config.WEB_SCRAPER_URLS.strip()
    if env_urls:
        urls.extend(u.strip() for u in env_urls.split(",") if u.strip())

    if urls_file:
        with open(urls_file, encoding="utf-8") as f:
            urls.extend(line.strip() for line in f if line.strip() and not line.startswith("#"))

    seen: set[str] = set()
    deduped: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            deduped.append(url)

    return deduped


async def main():
    parser = argparse.ArgumentParser(description="Scrape web docs and convert to structured markdown")
    parser.add_argument("--urls-file", help="File with one URL per line")
    parser.add_argument("--ingest", action="store_true", help="Ingest scraped docs after conversion")
    parser.add_argument("--output-dir", default=None, help="Output directory (default: scraped_docs)")
    args = parser.parse_args()

    ingester = WebDocIngester(output_dir=args.output_dir)

    if args.urls_file or Config.WEB_SCRAPER_URLS.strip():
        urls = collect_urls(args.urls_file)
        if not urls:
            print("No URLs found. Set WEB_SCRAPER_URLS or use --urls-file.")
            sys.exit(1)

        print(f"Scraping {len(urls)} URL(s)...")
        results = await ingester.scrape_and_convert(urls)

        ok = sum(1 for r in results if r["status"] == "ok")
        skipped = sum(1 for r in results if r["status"] == "skipped")
        errors = sum(1 for r in results if r["status"] == "fetch_error")
        files_written = sum(len(r.get("files_written", [])) for r in results)

        print(f"\nDone: {ok} ok, {skipped} skipped, {errors} errors, {files_written} files written")
        print(f"Output: {ingester.output_dir}/")
        print(f"Log: {ingester.output_dir}/_conversion_log.json")

        if not args.ingest:
            print("\nTo ingest: uv run python scripts/ingest_web_docs.py --ingest")
            return

    if args.ingest:
        from src.utils.database import database
        await database.connect()
        print("\nIngesting scraped docs...")
        result = await ingester.ingest()
        await database.close()
        if "content" in result:
            print(result["content"][0]["text"])
        else:
            print(f"Ingestion result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
