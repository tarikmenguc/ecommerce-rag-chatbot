"""Search router — V3 (Week 6: Hybrid search + HyDE + query expansion + filters).

Pipeline:
    1. (Optional HyDE)             Embed a hypothetical product description instead of raw query
    2. (Optional query expansion)  Expand query into N alternatives via LLM
    3. Embed query (+ alternatives if expansion enabled)
    4. Hybrid search               BM25 + pgvector cosine via RRF, with category/price filters
    5. CrossEncoder reranker       Top-5 from merged candidates
    6. LLM synthesis               Claude Haiku → natural language answer
"""
import asyncio
import time
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.llm import embed, chat_completion
from app.limiter import limiter
from app.auth import verify_api_key
from app.services.search_service import hybrid_search
from app.services.reranker import rerank
from app.services.query_expansion import rewrite_query, hyde_embed
from app.logger import LlmCall, log_llm_call
from app.schemas import ProductQuery, ProductSearchResponse, ProductHit

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=ProductSearchResponse)
@limiter.limit("10/minute")
async def post_search(
    request: Request,
    req: ProductQuery,
    session: AsyncSession = Depends(get_session),
    api_key: str = Depends(verify_api_key),
) -> ProductSearchResponse:
    from app.llm import check_moderation, ModerationFlagged
    try:
        await check_moderation(req.query)
    except ModerationFlagged:
        raise HTTPException(status_code=400, detail="Arama sorgunuz güvenlik politikalarımıza aykırıdır.")
        
    t0 = time.perf_counter()

    # ── Stage 1: Embed query (HyDE or standard) ───────────────────────────────
    try:
        if req.use_hyde:
            # HyDE: embed a hypothetical product description instead of raw query
            query_vector = await hyde_embed(req.query)
        else:
            query_vectors = await embed([req.query])
            query_vector = query_vectors[0]
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Embedding error: {e}")

    # ── Stage 2: (Optional) Query expansion → additional embeddings ───────────
    extra_embeddings: list[list[float]] = []
    if req.use_query_expansion:
        try:
            alternatives = await rewrite_query(req.query, n=3)
            if alternatives:
                extra_embeddings = await embed(alternatives)
        except Exception as e:
            # Non-fatal: fall back to single-query search
            pass

    # ── Stage 3: Hybrid search (BM25 + vector) for each query vector ──────────
    filter_kwargs = dict(
        category=req.category,
        min_price=req.min_price,
        max_price=req.max_price,
        session=session,
    )

    try:
        # Run primary query hybrid search
        primary_candidates = await hybrid_search(
            query=req.query,
            query_embedding=query_vector,
            limit=20,
            **filter_kwargs,
        )

        # Run hybrid search for each expanded query and union results
        if extra_embeddings:
            extra_results = await asyncio.gather(*[
                hybrid_search(
                    query=req.query,
                    query_embedding=vec,
                    limit=10,
                    **filter_kwargs,
                )
                for vec in extra_embeddings
            ])
            # Union: add candidates not already in primary (by chunk id)
            seen_ids = {chunk.id for chunk, _ in primary_candidates}
            for result_list in extra_results:
                for chunk, product in result_list:
                    if chunk.id not in seen_ids:
                        seen_ids.add(chunk.id)
                        primary_candidates.append((chunk, product))

        candidates = primary_candidates

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {e}")

    if not candidates:
        raise HTTPException(status_code=404, detail="No products found matching your query.")

    # ── Stage 4: CrossEncoder reranker → Top-K ────────────────────────────────
    try:
        reranked = await rerank(query=req.query, candidates=candidates, top_k=req.top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reranker error: {e}")

    # ── Stage 5: Build response hits + RAG context ────────────────────────────
    seen_skus: set[str] = set()
    hits: list[ProductHit] = []
    context_parts: list[str] = []

    for chunk, product, rerank_score in reranked:
        if product.sku not in seen_skus:
            seen_skus.add(product.sku)
            hits.append(
                ProductHit(
                    sku=product.sku,
                    title=product.title,
                    category=product.category,
                    price_usd=product.price_usd,
                    score=rerank_score,
                )
            )
        context_parts.append(
            f"[{chunk.chunk_type.upper()}] {chunk.content}\n"
            f"Price: ${product.price_usd} | Rating: {product.avg_rating}/5"
        )

    context = "\n---\n".join(context_parts)

    # ── Stage 6: LLM RAG synthesis ────────────────────────────────────────────
    system_prompt = (
        "You are a helpful e-commerce assistant specializing in beauty and personal care products. "
        "Use ONLY the product information provided below to answer the user's question. "
        "Be concise, friendly, and specific. "
        "If the context includes customer reviews, cite them to support your recommendation.\n"
        "IMPORTANT: You MUST return a JSON object with 'is_product_related' (boolean) and 'answer' (string). "
        "If the user's query is completely unrelated to products or e-commerce, set 'is_product_related' to false.\n\n"
        f"PRODUCT CONTEXT:\n{context}"
    )
    if req.user_id:
        system_prompt += f"\n\n[System Note: Request from user_id: {req.user_id}]"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": req.query},
    ]

    from pydantic import BaseModel
    
    class AssistantOutput(BaseModel):
        is_product_related: bool
        answer: str

    try:
        max_retries = 2
        for attempt in range(max_retries):
            try:
                text, in_tok, out_tok = await chat_completion(messages, response_schema=AssistantOutput)
                import json
                try:
                    if isinstance(text, str):
                        parsed = AssistantOutput.model_validate_json(text)
                    else:
                        parsed = AssistantOutput.model_validate(text)
                    
                    if not parsed.is_product_related:
                        answer = "Üzgünüm, sadece e-ticaret ve ürün arama konularında yardımcı olabilirim."
                    else:
                        answer = parsed.answer
                    break
                except Exception as parse_err:
                    if attempt == max_retries - 1:
                        raise ValueError(f"Failed to parse structured output: {parse_err}")
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM synthesis error: {e}")

    latency_ms = (time.perf_counter() - t0) * 1000

    from app.config import get_settings
    settings = get_settings()

    call = LlmCall(
        caller="search.post_search",
        api_key=api_key,
        model=settings.default_chat_model,
        input_tokens=in_tok,
        output_tokens=out_tok,
        latency_ms=latency_ms,
    )
    await log_llm_call(call)

    return ProductSearchResponse(
        query=req.query,
        hits=hits,
        answer=answer,
        cost_usd=call.total_cost_usd,
    )
