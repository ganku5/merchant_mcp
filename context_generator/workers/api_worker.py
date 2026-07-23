import json
import re
from pathlib import Path
from typing import Dict, Any, List

from context_generator.schemas import RepoContext, to_dict
from context_generator.generation_client import request_documentation


def slugify_api(api: str) -> str:
    s = re.sub(r"([a-z])([A-Z])", r"\1-\2", api).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "api"


def doc_id_for_api(api: str) -> str:
    return slugify_api(api).replace("-", "_")


def build_context_packet(ctx: RepoContext, max_files: int = 8, max_snippets_per_file: int = 2) -> str:
    parts: List[str] = []

    parts.append(f"API NAME: {ctx.api}")
    parts.append("")
    parts.append("KEYWORDS USED:")
    parts.append(", ".join(ctx.keywords))
    parts.append("")
    parts.append("SOURCE FILES AND SNIPPETS:")

    for f in ctx.files[:max_files]:
        parts.append("")
        parts.append(f"FILE: {f.path}")
        parts.append(f"MATCHED TERMS: {', '.join(f.matched_terms)}")

        for i, snip in enumerate(f.snippets[:max_snippets_per_file], start=1):
            parts.append(f"\nSNIPPET {i}:")
            parts.append("```text")
            parts.append(snip[:2500])
            parts.append("```")

    return "\n".join(parts)


def generate_markdown(ctx: RepoContext) -> str:
    context_packet = build_context_packet(ctx)

    system_instruction = """You are a senior technical writer for Juspay UPI Server-to-Server APIs.

You must generate merchant-facing integration documentation from source-code evidence.

Rules:
- Do not infer unsupported facts.
- Do not write "typically", "likely", "expected", "illustrative", or "general guidance".
- If endpoint, HTTP method, authentication, response envelope, retry rule, status code, or response detail is not clear from source material, write "To be confirmed with Juspay integration team".
- Sample request must only include values supported by evidence.
- If `flow` is included and evidence says it must be TRANSACTION, use "TRANSACTION"; otherwise omit it.
- Sample response must not invent success codes/messages. If exact response is not confirmed, show only a minimal placeholder with "Not confirmed from source material".
- Keep documentation practical for merchant developers.
- Do not expose internal implementation details unnecessarily.
- Use markdown only.
- Include a final "Evidence Used" section listing source files.
"""

    generation_request = f"""Generate an API integration guide for `{ctx.api}` using only the source material below.

Required markdown structure:

# {ctx.api} API Integration Guide

## Overview
## When to Use
## Endpoint
## Authentication
## Request Fields
## Response Fields
## Validations
## Error Handling
## Retry / Status Guidance
## Sample Request
## Sample Response
## Notes and Assumptions
## Evidence Used

Source material:

{context_packet}
"""

    return request_documentation(
        [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": generation_request},
        ],
        temperature=0.1,
    )


def run_api_worker(ctx: RepoContext, out_dir: str) -> Dict[str, Any]:
    out = Path(out_dir)
    docs_dir = out / "docs"
    evidence_dir = out / "evidence"

    docs_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    slug = slugify_api(ctx.api)
    doc_id = doc_id_for_api(ctx.api)

    md_path = docs_dir / f"{slug}.md"
    evidence_path = evidence_dir / f"{slug}.evidence.json"

    md = generate_markdown(ctx)
    md_path.write_text(md)

    evidence = {
        "api": ctx.api,
        "doc_id": doc_id,
        "keywords": ctx.keywords,
        "source_files_count": len(ctx.files),
        "source_files": [to_dict(f) for f in ctx.files],
    }

    evidence_path.write_text(json.dumps(evidence, indent=2))

    return {
        "api": ctx.api,
        "doc_id": doc_id,
        "markdown_path": str(md_path),
        "evidence_path": str(evidence_path),
    }
