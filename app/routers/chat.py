"""
/chat endpoint — the Week 1 target.

Week 1 contract:
    POST /chat  {"message": "..."}  -> ChatResponse with cost logged.

DELIBERATELY INCOMPLETE: the logger call is a TODO. You wire it up AI-off.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.llm import chat_completion
from app.limiter import limiter
from app.auth import verify_api_key
from app.logger import LlmCall,log_llm_call #  <- enable after you implement it
from app.models import Interaction
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
@limiter.limit("10/minute")
async def post_chat(
    request: Request,
    req: ChatRequest,
    session: AsyncSession = Depends(get_session),
    api_key: str = Depends(verify_api_key),
) -> ChatResponse:
    messages: list[dict[str, str]] = []
    if req.system_prompt:
        messages.append({"role": "system", "content": req.system_prompt})
    messages.append({"role": "user", "content": req.message})

    t0 = time.perf_counter()
    try:
        text, in_tok, out_tok = await chat_completion(messages, model=req.model)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error: {e}") from e
    latency_ms = (time.perf_counter() - t0) * 1000

    call = LlmCall(
        caller="chat.post_chat",
        api_key=api_key,
        model=req.model or "gpt-4o-mini",
        input_tokens=in_tok,
        output_tokens=out_tok,
        latency_ms=latency_ms,
    )

    await log_llm_call(call)

    interaction = Interaction(
        user_query=req.message,
        model=call.model,
        answer=text,
        cost_usd=call.total_cost_usd,
    )
    session.add(interaction)
    await session.commit()

    return ChatResponse(
        answer=text,
        model=call.model,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=call.total_cost_usd,
        latency_ms=latency_ms,
    )
