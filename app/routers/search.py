from __future__ import annotations

import time
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.llm import embed, chat_completion
from app.limiter import limiter
from app.auth import verify_api_key
from app.services.search_service import hybrid_search
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
    t0 = time.perf_counter()
    
    # 1. Embed user query
    try:
        query_vectors = await embed([req.query])
        query_vector = query_vectors[0]
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Embedding error: {e}")

    # 2. Hybrid search (Vector + BM25)
    try:
        results = await hybrid_search(req.query, query_vector, limit=req.top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {e}")

    # 3. Build Hits for response
    hits = [
        ProductHit(
            sku=p.sku,
            title=p.title,
            category=p.category,
            price_usd=p.price_usd,
            score=float(score)
        )
        for p, score in results
    ]

    # 4. LLM RAG Synthesis
    context_parts = []
    for p, score in results:
        context_parts.append(
            f"Product: {p.title}\nCategory: {p.category}\n"
            f"Price: ${p.price_usd}\nDescription: {p.description}\n---"
        )
    context = "\n".join(context_parts)
    
    system_prompt = (
        "You are a helpful e-commerce assistant. Use the following product results "
        "to answer the user's question. Be concise and professional. "
        "If the products are not relevant, inform the user.\n\n"
        f"CONTEXT:\n{context}"
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": req.query}
    ]
    
    try:
        answer, in_tok, out_tok = await chat_completion(messages)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM synthesis error: {e}")
        
    latency_ms = (time.perf_counter() - t0) * 1000
    
   
    call = LlmCall(
        caller="search.post_search",
        api_key=api_key,
        model="gpt-4o-mini",
        input_tokens=in_tok,
        output_tokens=out_tok,
        latency_ms=latency_ms
    )
    await log_llm_call(call)
    
    return ProductSearchResponse(
        query=req.query,
        hits=hits,
        answer=answer,
        cost_usd=call.total_cost_usd
    )
