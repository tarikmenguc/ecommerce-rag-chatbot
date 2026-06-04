"""Search service — V3 (Week 6: Hybrid BM25+Vector + metadata filters).

V3 changes vs V2:
- hybrid_search: combines BM25 (lexical) + pgvector cosine (semantic) via RRF.
  BM25 runs on the full chunk corpus fetched without embeddings (light query).
- chunk_vector_search: now accepts category / min_price / max_price filters.
- get_product_by_sku: unchanged.

Scalability note on BM25:
  Fetching all chunk text into RAM is fine for datasets up to ~100K chunks.
  Beyond that, consider a dedicated BM25 index (Elasticsearch, Typesense) or
  a SPLADE sparse vector stored in pgvector (requires naver/splade-* model).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product, ProductChunk
from app.db import SessionLocal


# ── Reciprocal Rank Fusion ─────────────────────────────────────────────────────

def _rrf_score(rank: int, k: int = 60) -> float:
    """Standard RRF formula: 1 / (k + rank).  rank is 1-based."""
    return 1.0 / (k + rank)


# ── Internal lightweight chunk row (no embedding) ─────────────────────────────

@dataclass
class _ChunkRow:
    id: int
    product_sku: str
    chunk_type: str
    chunk_index: int
    content: str
    price_usd: float
    category: str


# ── Core search functions ──────────────────────────────────────────────────────

async def chunk_vector_search(
    query_embedding: list[float],
    limit: int = 20,
    chunk_type: str | None = None,
    category: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    session: AsyncSession | None = None,
) -> list[tuple[ProductChunk, Product]]:
    """Vector similarity search over ProductChunk table.

    Uses pgvector's native <=> (cosine distance) operator so the
    HNSW index is used — no Python-side computation.

    Args:
        query_embedding: 1024-dim bge-m3 vector of the user query.
        limit: Number of candidate chunks to return (default 20 for reranker).
        chunk_type: Optional filter ('metadata', 'description', 'review').
        category: Optional exact-match filter on Product.category.
        min_price: Optional lower bound on Product.price_usd.
        max_price: Optional upper bound on Product.price_usd.
        session: Optional existing AsyncSession; creates one if None.

    Returns:
        List of (ProductChunk, Product) tuples ordered by similarity (best first).
    """
    async def _execute(sess: AsyncSession):
        stmt = (
            select(ProductChunk, Product)
            .join(Product, Product.sku == ProductChunk.product_sku)
            .order_by(ProductChunk.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )
        if chunk_type:
            stmt = stmt.where(ProductChunk.chunk_type == chunk_type)
        if category:
            stmt = stmt.where(Product.category == category)
        if min_price is not None:
            stmt = stmt.where(Product.price_usd >= min_price)
        if max_price is not None:
            stmt = stmt.where(Product.price_usd <= max_price)

        result = await sess.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    if session is not None:
        return await _execute(session)

    async with SessionLocal() as sess:
        return await _execute(sess)


async def hybrid_search(
    query: str,
    query_embedding: list[float],
    limit: int = 20,
    category: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    bm25_weight: float = 0.3,
    vector_weight: float = 0.7,
    session: AsyncSession | None = None,
) -> list[tuple[ProductChunk, Product]]:
    """Two-stage hybrid retrieval: BM25 (lexical) + pgvector cosine (semantic).

    Pipeline:
        1. Fetch all chunk text (no embeddings) + filtered product metadata.
        2. Run BM25 → top-(limit*2) chunk IDs + ranks.
        3. Run pgvector vector search → top-(limit*2) chunk IDs + ranks.
        4. Merge via Reciprocal Rank Fusion (RRF).
        5. Fetch full (ProductChunk, Product) rows for the top `limit` chunk IDs.

    Args:
        query: Raw text query for BM25 tokenization.
        query_embedding: Pre-computed 1024-dim query vector.
        limit: Final number of results to return.
        category: Optional exact-match filter on Product.category.
        min_price: Optional lower bound on Product.price_usd.
        max_price: Optional upper bound on Product.price_usd.
        bm25_weight: Weight for BM25 ranks in RRF (default 0.3).
        vector_weight: Weight for vector ranks in RRF (default 0.7).
        session: Optional existing AsyncSession.

    Returns:
        List of (ProductChunk, Product) tuples, best first by RRF score.
    """
    candidate_limit = limit * 2

    async def _run(sess: AsyncSession):
        # ── Step 1: Fetch all chunk text + product metadata (no embedding col) ──
        text_stmt = (
            select(
                ProductChunk.id,
                ProductChunk.product_sku,
                ProductChunk.chunk_type,
                ProductChunk.chunk_index,
                ProductChunk.content,
                Product.price_usd,
                Product.category,
            )
            .join(Product, Product.sku == ProductChunk.product_sku)
        )
        if category:
            text_stmt = text_stmt.where(Product.category == category)
        if min_price is not None:
            text_stmt = text_stmt.where(Product.price_usd >= min_price)
        if max_price is not None:
            text_stmt = text_stmt.where(Product.price_usd <= max_price)

        rows_result = await sess.execute(text_stmt)
        all_rows = [
            _ChunkRow(
                id=r[0],
                product_sku=r[1],
                chunk_type=r[2],
                chunk_index=r[3],
                content=r[4],
                price_usd=r[5],
                category=r[6],
            )
            for r in rows_result.all()
        ]

        if not all_rows:
            return []

        # ── Step 2: BM25 ──────────────────────────────────────────────────────
        tokenized = [row.content.lower().split() for row in all_rows]
        bm25 = BM25Okapi(tokenized)
        query_tokens = query.lower().split()
        bm25_scores = bm25.get_scores(query_tokens)

        # Top candidate_limit by BM25 (index into all_rows)
        bm25_top_indices = sorted(
            range(len(all_rows)), key=lambda i: bm25_scores[i], reverse=True
        )[:candidate_limit]
        bm25_rank: dict[int, int] = {
            all_rows[idx].id: rank + 1  # 1-based
            for rank, idx in enumerate(bm25_top_indices)
        }

        # ── Step 3: Vector search ────────────────────────────────────────────
        vector_results = await chunk_vector_search(
            query_embedding=query_embedding,
            limit=candidate_limit,
            category=category,
            min_price=min_price,
            max_price=max_price,
            session=sess,
        )
        vector_rank: dict[int, int] = {
            chunk.id: rank + 1  # 1-based
            for rank, (chunk, _) in enumerate(vector_results)
        }

        # ── Step 4: RRF merge ────────────────────────────────────────────────
        all_chunk_ids = set(bm25_rank) | set(vector_rank)
        rrf_scores: dict[int, float] = {}
        for cid in all_chunk_ids:
            bm25_rrf = bm25_weight * _rrf_score(bm25_rank[cid]) if cid in bm25_rank else 0.0
            vec_rrf = vector_weight * _rrf_score(vector_rank[cid]) if cid in vector_rank else 0.0
            rrf_scores[cid] = bm25_rrf + vec_rrf

        top_chunk_ids = sorted(rrf_scores, key=lambda cid: rrf_scores[cid], reverse=True)[:limit]

        # ── Step 5: Fetch full ORM objects for top chunk IDs ────────────────
        fetch_stmt = (
            select(ProductChunk, Product)
            .join(Product, Product.sku == ProductChunk.product_sku)
            .where(ProductChunk.id.in_(top_chunk_ids))
        )
        fetch_result = await sess.execute(fetch_stmt)
        id_to_pair: dict[int, tuple[ProductChunk, Product]] = {
            row[0].id: (row[0], row[1]) for row in fetch_result.all()
        }

        # Return in RRF rank order
        return [id_to_pair[cid] for cid in top_chunk_ids if cid in id_to_pair]

    if session is not None:
        return await _run(session)

    async with SessionLocal() as sess:
        return await _run(sess)


async def get_product_by_sku(sku: str) -> Product | None:
    """Fetch a single Product row by SKU."""
    async with SessionLocal() as session:
        result = await session.execute(
            select(Product).where(Product.sku == sku)
        )
        return result.scalar_one_or_none()
