"""Read-only API use-case search tools."""

from ..utils.database import database


async def search_api_use_cases(query: str, limit: int = 10) -> dict:
    """Find APIs whose documented business use case matches a client query."""
    if database._pool is None:
        await database.connect()

    limit = max(1, min(limit, 25))

    search_mode = "vector"
    async with database.pool.acquire() as conn:
        embedding_count = await conn.fetchval(
            """SELECT COUNT(*) FROM api_specs_v2
               WHERE business_use_case_embedding IS NOT NULL"""
        )

    if not embedding_count:
        search_mode = "keyword"
        results = await database.search_api_business_use_cases_text(query, limit)
    else:
        try:
            from ..utils.llm import llm_client

            query_embedding = (await llm_client.embed([query]))[0]
            results = await database.search_api_business_use_cases(query_embedding, limit)
            if not results:
                search_mode = "keyword"
                results = await database.search_api_business_use_cases_text(query, limit)
        except Exception:
            search_mode = "keyword"
            results = await database.search_api_business_use_cases_text(query, limit)

    if not results:
        return {
            "content": [{
                "type": "text",
                "text": "No API business-use-case matches found. Run the docs zip ingestion first or try broader terms.",
            }],
            "isError": False,
        }

    sections = [f"# API Use Case Matches\n\nQuery: {query}\nSearch mode: {search_mode}"]
    for index, row in enumerate(results, 1):
        similarity = row.get("similarity")
        score = f"{similarity:.3f}" if isinstance(similarity, (int, float)) else None
        sections.extend([
            f"\n## {index}. {row['endpoint_id']}",
            f"**Endpoint:** `{row['method']} {row['path']}`",
        ])
        if score:
            sections.append(f"**Score:** {score}")
        if row.get("summary"):
            sections.append(f"**Summary:** {row['summary']}")
        if row.get("business_use_case"):
            sections.append(f"\n{row['business_use_case']}")
        if row.get("when_newton_sends_it"):
            sections.append(f"\n**When Newton Sends It**\n{row['when_newton_sends_it']}")

    return {
        "content": [{"type": "text", "text": "\n".join(sections)}],
        "isError": False,
    }
