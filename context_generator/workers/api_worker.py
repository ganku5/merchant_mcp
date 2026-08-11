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


def build_context_packet(ctx: RepoContext, max_files: int = 5, max_snippets_per_file: int = 1) -> str:
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
            parts.append(snip[:1200])
            parts.append("```")

    return "\n".join(parts)


def generate_markdown(ctx: RepoContext, config: Dict[str, Any] | None = None) -> str:
    config = config or {}
    context_packet = build_context_packet(ctx)
    focus = config.get("documentation_focus", "merchant-facing API integration documentation")
    repo_name = config.get("repo_name", "the configured repository")
    forbidden_terms = ", ".join(config.get("forbidden_output_terms", []))
    style_guide = config.get("style_guide", {})
    preferred_structure = "\n".join(
        f"- {section}" for section in style_guide.get("preferred_structure", [])
    )

    system_instruction = f"""You are a senior business documentation writer for Juspay UPI Server-to-Server APIs.

Generate {focus} using only {repo_name} codebase evidence as the source of truth.

Primary goal:
Generate documentation in the same style as Newton server-to-server API guides: business-first, integration-flow oriented, with endpoint, headers, request, response, validation, error, and retry guidance.

Preferred documentation structure:
{preferred_structure}

Rules:
- Use only {repo_name} codebase evidence as the source of truth.
- Do not use existing generated docs, curated docs, external docs, assumptions, or general knowledge as facts.
- Existing Newton server-to-server docs may be used only as style/structure reference, never as factual source.
- Extract merchant-facing business and API details from route definitions, request/response types, validation branches, error constructors/messages, constants/enums, and product/business logic.
- Preserve all source-supported merchant-facing details such as endpoint, HTTP method, authentication, request fields, response fields, validations, errors, retry/status guidance, and response details.
- Include conditionally required fields when source evidence supports them. For example, include `payeeVpa` when dynamic VPA validation is present.
- Do not omit request fields that are referenced in validations or business behavior.
- Retry guidance must tell merchants to check transaction status for unknown outcomes before creating a new request; do not suggest blind retries.
- For endpoint URLs, prefer placeholder format using configured host and URI, for example `{{{{host}}}}/api/{{{{uri}}}}/merchants/transactions/<api-name>`, when the route path is available.
- Do not write unconfirmed placeholder text for missing host, URI, authentication, signing, or encryption details.
- For endpoint URLs, show the route URL with `{{{{host}}}}` and `{{{{uri}}}}` placeholders if host/URI are not present in code.
- For authentication, state only source-supported merchant-facing authentication details.
- If an exact value is not available in {repo_name} codebase evidence, omit that exact value instead of adding a placeholder.
- Do not create placeholder response fields for unknown values.
- Convert code evidence into merchant-facing language.
- Do not explain internal implementation details.
- Do not mention these internal/code terms in the final document: {forbidden_terms}.
- Do not mention source file names, code paths, function names, modules, predicates, transformers, handlers, or where something is defined in code.
- Do not include an Evidence Used section.
- Do not infer unsupported facts.
- Do not write "typically", "likely", "expected", "illustrative", or "general guidance".
- Do not analyze the source material in the response.
- Do not explain your plan.
- Start directly with the markdown title.
- Keep the document concise.
- Sample request may use realistic example values for readability when field names are supported by {repo_name} codebase evidence.
- Sample response must use placeholders unless exact literal values are supported by {repo_name} codebase evidence.
- If `flow` is included and evidence says it must be TRANSACTION, use "TRANSACTION"; otherwise omit it.
- Sample response must not invent success codes/messages.
- For Sample Response, include the response envelope and structurally supported fields. Use generic placeholder values such as "<response_code>", "<response_message>", "<gateway_transaction_id>", and "<order_id>" when exact literal values are not present in codebase evidence.
- Do not use unconfirmed placeholder text.
- Use markdown only.
- Do not write analysis, planning, reasoning, or explanation before the final markdown.
- Start the response directly with the H1 title.

Wording examples:
Bad: "the predicate checks merchantRequestId"
Good: "`merchantRequestId` is used as the merchant reference/idempotency identifier for the request."

Bad: "the transformer builds CoreRegisterIntentResponsePayload"
Good: "On success, the API returns identifiers and payment details required to continue the UPI journey."
"""

    generation_request = f"""Generate an API integration guide for `{ctx.api}` using only the source material below.

Return only the final markdown document.
Start directly with the H1 title.
Do not include analysis, planning, internal notes, source-code walkthrough, or evidence listing.
Keep the output concise and merchant-facing. Preserve source-supported endpoint, auth, request fields, response fields, validations, errors, and retry/status guidance. Use `{{{{host}}}}/api/{{{{uri}}}}/...` style endpoint placeholders when host or URI is not available in source evidence. Omit unsupported exact values instead of adding unconfirmed placeholder text.

Required markdown structure.
All sections below are mandatory. Follow the Newton server-to-server guide style where possible.
Do not leave any markdown code fence unclosed.

Required markdown structure:

# {ctx.api} API Integration Guide

## Overview
Source endpoint: use the discovered method and route path.

## Overview
## Business Use Case
## Integration Flow
## Endpoint
## Request
### Required Minimum
### Field Reference
### Defaults and Omitted Field Behavior
## Response
### Success Response
### Field Reference
## Error Handling
## Retry / Status Guidance
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


def run_api_worker(ctx: RepoContext, out_dir: str, config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    out = Path(out_dir)
    docs_dir = out / "docs"
    evidence_dir = out / "evidence"

    docs_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    slug = slugify_api(ctx.api)
    doc_id = doc_id_for_api(ctx.api)

    md_path = docs_dir / f"{slug}.md"
    evidence_path = evidence_dir / f"{slug}.evidence.json"

    md = generate_markdown(ctx, config=config)
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
