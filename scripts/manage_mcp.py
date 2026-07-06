#!/usr/bin/env python3
"""Manage the Merchant MCP database, ingestion, and server host."""

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.tools.admin_tools import (  # noqa: E402
    add_api_spec,
    add_context,
    get_database_overview,
    ingest_document,
    list_queryable_tables,
)
from src.ingestion.docs_zip_ingester import ingest_docs_zip  # noqa: E402
from src.utils.database import database  # noqa: E402


def _extract_text(result: dict) -> str:
    content = result.get("content", []) if isinstance(result, dict) else []
    texts = [item.get("text", "") for item in content if isinstance(item, dict)]
    return "\n\n".join(texts) if texts else json.dumps(result, indent=2, default=str)


async def _with_db(coro):
    await database.connect()
    try:
        return await coro
    finally:
        await database.close()


async def cmd_ingest(args):
    return await _with_db(
        ingest_document(
            filepath=args.filepath,
            doc_id=args.doc_id,
            force_type=args.type,
            skip_contextual=args.skip_contextual,
        )
    )


async def cmd_ingest_docs_zip(args):
    if args.dry_run:
        return await ingest_docs_zip(
            zip_path=args.zip_path,
            source_name=args.source_name,
            skip_embeddings=args.skip_embeddings,
            dry_run=True,
        )

    return await _with_db(
        ingest_docs_zip(
            zip_path=args.zip_path,
            source_name=args.source_name,
            skip_embeddings=args.skip_embeddings,
            dry_run=args.dry_run,
        )
    )


async def cmd_add_api_spec(args):
    with open(args.filepath, "r", encoding="utf-8") as handle:
        spec = json.load(handle)
    return await _with_db(add_api_spec(spec))


async def cmd_add_context(args):
    if args.content_file:
        content = Path(args.content_file).read_text(encoding="utf-8")
    else:
        content = args.content

    return await _with_db(
        add_context(
            title=args.title,
            content=content,
            doc_id=args.doc_id,
            namespace=args.namespace,
            source_type=args.source_type,
            generate_contextual=args.generate_contextual,
        )
    )


async def cmd_stats(_args):
    return await _with_db(get_database_overview())


async def cmd_tables(_args):
    return await _with_db(list_queryable_tables())


def cmd_serve(args):
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "src.server.mcp_server:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    if args.reload:
        command.append("--reload")
    try:
        return subprocess.call(command, cwd=PROJECT_ROOT)
    except KeyboardInterrupt:
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Merchant MCP management script")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser(
        "ingest", help="Ingest a document, CSV, JSON, YAML, PDF, or OpenAPI spec"
    )
    ingest.add_argument("filepath")
    ingest.add_argument("--doc-id")
    ingest.add_argument(
        "--type",
        choices=[
            "pdf",
            "csv",
            "json",
            "yaml",
            "text",
            "markdown",
            "endpoints",
            "errors",
        ],
    )
    ingest.add_argument(
        "--with-contextual",
        action="store_false",
        dest="skip_contextual",
        default=True,
        help="Also generate contextual Q&A embeddings after chunk ingestion",
    )
    ingest.set_defaults(async_handler=cmd_ingest)

    docs_zip = subparsers.add_parser(
        "ingest-docs-zip",
        help="Ingest generated server-to-server API markdown docs from docs.zip",
    )
    docs_zip.add_argument("zip_path")
    docs_zip.add_argument("--source-name", default="s2s_api_docs")
    docs_zip.add_argument("--skip-embeddings", action="store_true")
    docs_zip.add_argument("--dry-run", action="store_true")
    docs_zip.set_defaults(async_handler=cmd_ingest_docs_zip)

    add_spec = subparsers.add_parser(
        "add-api-spec", help="Add or update a rich API spec from JSON"
    )
    add_spec.add_argument("filepath")
    add_spec.set_defaults(async_handler=cmd_add_api_spec)

    context = subparsers.add_parser(
        "add-context", help="Add direct text context for client Q&A"
    )
    context.add_argument("--title", required=True)
    source = context.add_mutually_exclusive_group(required=True)
    source.add_argument("--content")
    source.add_argument("--content-file")
    context.add_argument("--doc-id")
    context.add_argument("--namespace", default="manual_context")
    context.add_argument("--source-type", default="manual")
    context.add_argument("--generate-contextual", action="store_true")
    context.set_defaults(async_handler=cmd_add_context)

    stats = subparsers.add_parser("stats", help="Show table counts")
    stats.set_defaults(async_handler=cmd_stats)

    tables = subparsers.add_parser("tables", help="List queryable public tables")
    tables.set_defaults(async_handler=cmd_tables)

    serve = subparsers.add_parser("serve", help="Host the MCP HTTP tool server")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")
    serve.set_defaults(sync_handler=cmd_serve)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if hasattr(args, "sync_handler"):
        return int(args.sync_handler(args) or 0)

    result = asyncio.run(args.async_handler(args))
    print(_extract_text(result))
    return 0 if not result.get("isError") else 1


if __name__ == "__main__":
    raise SystemExit(main())
