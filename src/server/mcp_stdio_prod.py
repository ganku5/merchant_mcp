import json
import logging
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastmcp import FastMCP
from src.utils.database import database
from src.utils.llm import llm_client

mcp = FastMCP("merchant-mcp")


def _extract(result):
    if isinstance(result, str):
        return result

    if isinstance(result, dict):
        if "content" in result:
            texts = [
                item.get("text", "")
                for item in result["content"]
                if isinstance(item, dict)
            ]
            return "\n\n".join(texts) if texts else json.dumps(result, indent=2)

        return json.dumps(result, indent=2)

    return str(result)


async def ensure_database():
    try:
        await database.get_stats()
    except Exception as e:
        if "not connected" in str(e).lower() or "connect()" in str(e).lower():
            await database.connect()
        else:
            raise


def _add_plan(plan, seen, query: str, namespace=None, weight: float = 1.0):
    key = (query.lower(), namespace)
    if key not in seen:
        seen.add(key)
        plan.append({"query": query, "namespace": namespace, "weight": weight})


def _build_retrieval_plan(question: str):
    q = (question or "").strip()
    q_lower = q.lower()

    plan = []
    seen = set()

    if any(k in q_lower for k in ["niubiz", "tpap", "tapp", "peru", "bcrp", "dpi", "qr", "s2s", "onboarding", "merchant integration"]):
        _add_plan(
            plan,
            seen,
            q,
            "ganesh_shared_docs",
            1.45,
        )
        _add_plan(
            plan,
            seen,
            "Niubiz merchant integration models QR TAPP Peru BCRP merchant flows",
            "ganesh_shared_docs",
            1.35,
        )
        _add_plan(
            plan,
            seen,
            "TPAP onboarding S2S Juspay NIUBIZ TAPP registration account management transaction flows",
            "ganesh_shared_docs",
            1.3,
        )

    if any(k in q_lower for k in ["deemed", "pending", "deliver", "goods", "service", "merchant", "success", "failure", "failed"]):
        _add_plan(
            plan,
            seen,
            "UPI deemed transaction status merchant deliver goods success failure pending reconciliation",
            None,
            1.35,
        )
        _add_plan(
            plan,
            seen,
            "deemed transaction final status merchant should not deliver goods until success confirmation",
            None,
            1.25,
        )
        _add_plan(
            plan,
            seen,
            "transaction status deemed pending success failure reversal reconciliation merchant",
            None,
            1.15,
        )

    if any(k in q_lower for k in ["upi", "transaction", "reqpay", "resppay", "payer", "payee", "end-to-end", "end to end"]):
        _add_plan(
            plan,
            seen,
            "UPI transaction flow payer payee PSP NPCI debit credit ReqPay RespPay",
            "pdf_upi_2_0_tsd_embedded",
            1.25,
        )
        _add_plan(
            plan,
            seen,
            "ReqPay RespPay transaction status debit credit payer payee confirmation",
            "pdf_upi_2_0_tsd_embedded",
            1.15,
        )

    if any(k in q_lower for k in ["sign", "signature", "signed", "encrypt", "encryption", "psp", "tsp", "header", "x-merchant"]):
        _add_plan(
            plan,
            seen,
            "Signature Calculation x-merchant-id x-merchant-channel-id x-timestamp RequestBody SHA256withRSA",
            "text_juspay_multibank_full_embedded",
            1.25,
        )
        _add_plan(
            plan,
            seen,
            "JWS Signature Calculation x-merchant-signature request headers",
            "text_juspay_multibank_full_embedded",
            1.15,
        )
        _add_plan(
            plan,
            seen,
            "RSA256 HMAC signature validation x-merchant-payload-signature x-response-signature",
            "text_juspay_multibank_full_embedded",
            1.1,
        )

    if any(k in q_lower for k in ["fetch", "account", "endpoint", "api spec", "request field", "response field"]):
        _add_plan(plan, seen, "fetch account details response fields accRefId maskedAccNum balance", None, 1.1)
        _add_plan(plan, seen, "API request response fields endpoint path method", None, 1.0)

    _add_plan(plan, seen, q, None, 1.0)

    return plan[:7]


def _term_boost(question: str, text: str) -> float:
    q_terms = {
        w.strip(".,:;!?()[]{}").lower()
        for w in question.split()
        if len(w.strip(".,:;!?()[]{}")) > 3
    }

    if not q_terms:
        return 0.0

    text_lower = text.lower()
    matched = sum(1 for term in q_terms if term in text_lower)
    return min(0.08, matched * 0.01)


async def _vector_search(query: str, namespace, limit: int):
    embedding = await llm_client.embed([query])
    return await database.search_similar_chunks(
        embedding[0],
        limit=limit,
        namespace=namespace,
    )


def _row_value(row: Any, key: str, default=None):
    try:
        return row[key]
    except Exception:
        return getattr(row, key, default)


def _merge_rank_results(question: str, planned_results, limit: int):
    merged = {}

    for plan_item, rows in planned_results:
        for row in rows:
            chunk_text = _row_value(row, "chunk_text", "") or ""
            namespace = _row_value(row, "namespace", "") or ""
            filename = _row_value(row, "filename", "") or ""
            doc_id = _row_value(row, "doc_id", namespace) or namespace
            chunk_index = _row_value(row, "chunk_index", -1)
            similarity = float(_row_value(row, "similarity", 0.0) or 0.0)

            key = (doc_id, chunk_index, chunk_text[:120])
            score = similarity * float(plan_item["weight"]) + _term_boost(question, chunk_text)

            existing = merged.get(key)
            if not existing or score > existing["score"]:
                merged[key] = {
                    "doc_id": doc_id,
                    "chunk_index": chunk_index,
                    "chunk_text": chunk_text,
                    "namespace": namespace,
                    "filename": filename,
                    "similarity": similarity,
                    "score": score,
                    "query": plan_item["query"],
                }

    return sorted(merged.values(), key=lambda x: x["score"], reverse=True)[:limit]


def _format_results(question: str, results):
    if not results:
        return ""

    sources = []
    sections = []

    for idx, row in enumerate(results, start=1):
        source = f"{row['namespace']} / {row['filename']}"
        if source not in sources:
            sources.append(source)

        snippet = row["chunk_text"][:1200]
        sections.append(
            f"## Result {idx}\n"
            f"Source: {source}\n"
            f"Similarity: {row['similarity']:.3f}\n"
            f"Score: {row['score']:.3f}\n\n"
            f"```\n{snippet}...\n```"
        )

    return (
        "# Documentation Context Retrieved\n\n"
        f"User question: {question}\n\n"
        "Answer using only the retrieved documentation context below. "
        "If the context does not provide a final answer, say what is missing.\n\n"
        "## Source Summary\n"
        + "\n".join(f"- {source}" for source in sources)
        + "\n\n"
        + "\n\n---\n\n".join(sections)
    )


@mcp.tool()
async def answer_from_docs(question: str, limit: int = 6) -> str:
    """Answer documentation questions using vector search."""
    await ensure_database()

    from src.tools.understanding_tools import search_docs

    q = (question or "").strip()
    plan = _build_retrieval_plan(q)

    planned_results = []
    vector_error = None

    for item in plan:
        try:
            rows = await _vector_search(item["query"], item["namespace"], max(limit * 3, 12))
            planned_results.append((item, rows))
        except Exception as e:
            vector_error = e

    ranked = _merge_rank_results(q, planned_results, limit)

    if ranked and ranked[0]["similarity"] >= 0.35:
        return _format_results(q, ranked)

    try:
        fallback = await search_docs(q, limit, None)
        extracted = _extract(fallback)
        reason = "vector search failed" if vector_error else "vector confidence was low"
        return (
            "# Documentation Context Retrieved\n\n"
            f"User question: {q}\n\n"
            f"Fallback used because {reason}.\n\n"
            f"{extracted}"
        )
    except Exception as e:
        if vector_error:
            return f"Unable to retrieve documentation context. Vector error: {vector_error}; fallback error: {e}"
        return f"Unable to retrieve documentation context. Error: {e}"


@mcp.tool()
async def get_api_spec(endpoint_id: str) -> str:
    """Get API specification for an exact endpoint_id."""
    await ensure_database()

    from src.tools.understanding_tools import get_api_spec as fn

    return _extract(await fn(endpoint_id))



@mcp.tool()
async def get_context(query: str, limit: int = 5) -> str:
    """Get relevant documentation context for a query."""
    await ensure_database()

    from src.tools.understanding_tools import search_docs as fn

    return _extract(await fn(query, limit, None))


@mcp.tool()
async def search_docs(query: str, limit: int = 5, namespace: str | None = None) -> str:
    """Search indexed documentation."""
    await ensure_database()

    from src.tools.understanding_tools import search_docs as fn

    return _extract(await fn(query, limit, namespace))


@mcp.tool()
async def get_flow(flow_type: str) -> str:
    """Get API flow for a known flow type."""
    await ensure_database()

    from src.tools.understanding_tools import get_flow as fn

    return _extract(await fn(flow_type, None))


@mcp.tool()
async def get_integration_guide(use_case: str, language: str = "general") -> str:
    """Get integration guide for a use case."""
    await ensure_database()

    from src.tools.understanding_tools import get_integration_guide as fn

    return _extract(await fn(use_case, language))


@mcp.tool()
async def generate_payload(endpoint_id: str) -> str:
    """Generate sample payload for an endpoint."""
    await ensure_database()

    from src.tools.building_tools import generate_payload as fn

    return _extract(await fn(endpoint_id))


@mcp.tool()
async def get_code_example(endpoint_id: str, language: str = "python") -> str:
    """Get code example for an endpoint."""
    await ensure_database()

    from src.tools.building_tools import get_code_example as fn

    return _extract(await fn(endpoint_id, language))


@mcp.tool()
async def get_test_cases(flow_type: str) -> str:
    """Get test cases for a flow type."""
    await ensure_database()

    from src.tools.testing_tools import get_test_cases as fn

    return _extract(await fn(flow_type))



@mcp.tool()
async def list_apis(limit: int = 100, query: str = "") -> str:
    """List available ingested APIs/endpoints."""
    await ensure_database()

    limit = max(1, min(int(limit or 100), 500))
    q = (query or "").strip()

    async with database.pool.acquire() as conn:
        if q:
            rows = await conn.fetch("""
                SELECT endpoint_id, method, path, description, source_doc_id
                FROM endpoint_specs
                WHERE endpoint_id ILIKE $1
                   OR path ILIKE $1
                   OR method ILIKE $1
                   OR description ILIKE $1
                   OR source_doc_id ILIKE $1
                ORDER BY endpoint_id
                LIMIT $2
            """, f"%{q}%", limit)
        else:
            rows = await conn.fetch("""
                SELECT endpoint_id, method, path, description, source_doc_id
                FROM endpoint_specs
                ORDER BY endpoint_id
                LIMIT $1
            """, limit)

    if not rows:
        return "No APIs found."

    lines = [
        "# Available APIs",
        "",
        "Use endpoint_id with get_api_spec / generate_payload / get_code_example.",
        "",
    ]

    for i, r in enumerate(rows, start=1):
        desc = (r["description"] or "").strip().replace("\n", " ")
        if len(desc) > 160:
            desc = desc[:157] + "..."

        lines.append(
            f"{i}. `{r['endpoint_id']}`\n"
            f"   Method: `{r['method']}`\n"
            f"   Path: `{r['path']}`\n"
            f"   Source: `{r['source_doc_id'] or '-'}`"
        )
        if desc:
            lines.append(f"   Description: {desc}")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
async def health_check() -> str:
    """Check MCP server and database health."""
    try:
        await ensure_database()
        stats = await database.get_stats()
        return json.dumps({"status": "healthy", "stats": stats}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


def main():
    logging.getLogger().setLevel(logging.WARNING)
    sys.stderr.write("Starting merchant MCP stdio server\n")
    sys.stderr.flush()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
