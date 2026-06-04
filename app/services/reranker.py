"""Cross-encoder reranker using ms-marco-MiniLM-L-6-v2.

Pipeline:
    1. Vector search returns Top-20 candidate chunks (fast, approximate)
    2. CrossEncoder scores each (query, chunk_content) pair (precise, slower)
    3. We return the Top-5 highest-scoring chunks

Why two stages?
    - HNSW vector search is O(log n) — very fast but approximate (ANN).
    - CrossEncoder reads query + chunk together → more accurate relevance
      but O(n) so we only run it on the 20 pre-filtered candidates.

Model: cross-encoder/ms-marco-MiniLM-L-6-v2
    - 22M params, runs on CPU in ~50ms for 20 candidates.
    - No API cost, fully local.
"""
from __future__ import annotations

import asyncio

_cross_encoder = None


def _get_cross_encoder():
    """Lazy-load the CrossEncoder model on first call."""
    global _cross_encoder
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder
        print("Loading reranker model: cross-encoder/ms-marco-MiniLM-L-6-v2 ...")
        _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        print("Reranker model loaded.")
    return _cross_encoder


def _do_rerank(query: str, candidates: list[tuple], top_k: int) -> list[tuple]:
    """Synchronous reranking — runs in a thread to avoid blocking the event loop."""
    model = _get_cross_encoder()

    # candidates: list of (ProductChunk, Product) tuples
    pairs = [(query, chunk.content) for chunk, product in candidates]
    scores = model.predict(pairs)

    scored = list(zip(candidates, scores))
    scored.sort(key=lambda x: x[1], reverse=True)

    return [(item[0], item[1], float(score)) for item, score in scored[:top_k]]


async def rerank(
    query: str,
    candidates: list[tuple],
    top_k: int = 5,
) -> list[tuple]:
    """Async wrapper — offloads CPU work to a thread pool.

    Args:
        query: The user's original search query string.
        candidates: List of (ProductChunk, Product) tuples from vector search.
        top_k: Number of results to return after reranking.

    Returns:
        List of (ProductChunk, Product, rerank_score) tuples, best first.
    """
    if not candidates:
        return []

    return await asyncio.to_thread(_do_rerank, query, candidates, top_k)
