"""Query expansion utilities — Week 6.

Two strategies:
    1. rewrite_query — LLM expands user query into N sub-queries (multi-query retrieval).
    2. hyde_embed   — Hypothetical Document Embeddings (Gao et al., 2022):
                      LLM writes a fake product description that would answer the query;
                      we embed THAT instead of the raw query text.

Why HyDE works: queries are short and vague, product descriptions are long and specific.
Embedding a hypothetical description brings the vector closer to real product embeddings.
"""
from __future__ import annotations

from app.llm import chat_completion, embed


async def rewrite_query(query: str, n: int = 3) -> list[str]:
    """Return `n` alternative phrasings of `query` using the default LLM.

    These alternatives are embedded and searched separately; results are merged
    (union) before reranking — multi-query retrieval.
    """
    messages = [
        {
            "role": "system",
            "content": (
                "You are a search query optimizer for an e-commerce product catalog. "
                "Given a user query, generate alternative search queries that capture "
                "different ways to express the same shopping intent. "
                f"Return exactly {n} alternative queries, one per line. "
                "No numbering, no explanations — just the queries."
            ),
        },
        {"role": "user", "content": f"Original query: {query}"},
    ]
    text, _, _ = await chat_completion(messages, max_tokens=256)
    alternatives = [line.strip() for line in text.strip().splitlines() if line.strip()]
    return alternatives[:n]


async def hyde_embed(query: str) -> list[float]:
    """Generate a hypothetical product description and return its embedding.

    Steps:
        1. Ask LLM to write a plausible product description that answers `query`.
        2. Embed that hypothetical description instead of the raw query.

    Returns:
        1024-dim embedding vector (same space as ProductChunk.embedding).
    """
    messages = [
        {
            "role": "system",
            "content": (
                "You are a product copywriter for an e-commerce site. "
                "Write a short product description (2–3 sentences) for a product "
                "that would perfectly satisfy the following search query. "
                "Be specific about features, materials, price range, and use case."
            ),
        },
        {"role": "user", "content": query},
    ]
    hypothetical_doc, _, _ = await chat_completion(messages, max_tokens=128)
    vectors = await embed([hypothetical_doc])
    return vectors[0]
