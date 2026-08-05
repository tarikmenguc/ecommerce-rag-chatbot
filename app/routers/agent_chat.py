"""B2C Agent Chat Router for the e-commerce AI Sales Assistant."""
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db import get_session
from app.limiter import limiter
from app.auth import verify_api_key
from app.logger import LlmCall, log_llm_call
from app.models import Interaction
from app.agent import run_agent
from app.config import get_settings

router = APIRouter(prefix="/agent", tags=["agent"])
settings = get_settings()

class AgentMessage(BaseModel):
    role: str
    content: str

class AgentChatRequest(BaseModel):
    message: str
    conversation_history: list[AgentMessage] | None = None
    user_id: str | None = None

class AgentChatResponse(BaseModel):
    answer: str
    tools_used: list[str]
    iterations: int
    cost_usd: float
    latency_ms: float

@router.post("/chat", response_model=AgentChatResponse)
@limiter.limit("10/minute")
async def post_agent_chat(
    request: Request,
    req: AgentChatRequest,
    session: AsyncSession = Depends(get_session),
    api_key: str = Depends(verify_api_key),
) -> AgentChatResponse:
    t0 = time.perf_counter()
    
    # Convert Pydantic models to dicts
    history = [msg.model_dump() for msg in req.conversation_history] if req.conversation_history else None
    
    try:
        agent_result = await run_agent(
            user_message=req.message,
            conversation_history=history
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")
        
    latency_ms = (time.perf_counter() - t0) * 1000
    
    call = LlmCall(
        caller="agent_chat",
        api_key=api_key,
        model=settings.default_chat_model,
        input_tokens=agent_result.get("input_tokens", 0),
        output_tokens=agent_result.get("output_tokens", 0),
        latency_ms=latency_ms
    )
    
    await log_llm_call(call)
    
    interaction = Interaction(
        user_query=req.message,
        user_id=req.user_id,
        model=call.model,
        answer=agent_result.get("answer", ""),
        cost_usd=call.total_cost_usd
    )
    session.add(interaction)
    await session.commit()
    
    return AgentChatResponse(
        answer=agent_result.get("answer", ""),
        tools_used=agent_result.get("tools_used", []),
        iterations=agent_result.get("iterations", 1),
        cost_usd=call.total_cost_usd,
        latency_ms=latency_ms
    )
