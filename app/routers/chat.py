"""
/chat endpoint — the Week 1 target.

Week 1 contract:
    POST /chat  {"message": "..."}  -> ChatResponse with cost logged.

DELIBERATELY INCOMPLETE: the logger call is a TODO. You wire it up AI-off.
"""
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
    
    # End-User ID injection (Hafta 8)
    sys_prompt = req.system_prompt or "Sen e-ticaret asistanısın. Müşteri ürünle ilgili sormuyorsa is_product_related=false dön."
    if req.user_id:
        sys_prompt += f"\n\n[System Note: Request from user_id: {req.user_id}]"

    messages.append({"role": "system", "content": sys_prompt})
    messages.append({"role": "user", "content": req.message})

    from app.llm import check_moderation, ModerationFlagged
    from pydantic import BaseModel
    
    class AssistantOutput(BaseModel):
        is_product_related: bool
        answer: str

    t0 = time.perf_counter()
    try:
        # 1. Moderation check
        await check_moderation(req.message)
        
        # 2. Structured Output with Retry
        max_retries = 2
        for attempt in range(max_retries):
            try:
                # Assuming chat_completion is updated to accept response_schema
                # Since we don't have chat_completion doing it natively yet, we can ask it to return JSON.
                # Actually, let's update chat_completion to accept response_schema!
                text, in_tok, out_tok = await chat_completion(messages, model=req.model, response_schema=AssistantOutput)
                # Since google-genai returns a Pydantic object if response_schema is passed:
                import json
                try:
                    # if it returns raw json string:
                    if isinstance(text, str):
                        parsed = AssistantOutput.model_validate_json(text)
                    else:
                        parsed = AssistantOutput.model_validate(text)
                    
                    if not parsed.is_product_related:
                        final_answer = "Üzgünüm, sadece e-ticaret ve ürün arama konularında yardımcı olabilirim."
                    else:
                        final_answer = parsed.answer
                    break # Success!
                except Exception as parse_err:
                    if attempt == max_retries - 1:
                        raise ValueError(f"Failed to parse structured output: {parse_err}")
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
    except ModerationFlagged:
        raise HTTPException(status_code=400, detail="Mesajınız güvenlik politikalarımıza aykırıdır.")
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
        user_id=req.user_id,
        model=call.model,
        answer=final_answer,
        cost_usd=call.total_cost_usd,
    )
    session.add(interaction)
    await session.commit()

    return ChatResponse(
        answer=final_answer,
        model=call.model,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=call.total_cost_usd,
        latency_ms=latency_ms,
    )
