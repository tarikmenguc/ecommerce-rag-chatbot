"""B2B Webhook Router (Trendyol Scenario)."""
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.db import get_session
from app.agent import run_agent

router = APIRouter(prefix="/webhook", tags=["webhook"])
log = logging.getLogger("app.webhook")

class TrendyolQuestionMessage(BaseModel):
    messageId: str
    text: str
    customerId: str
    productId: str

class TrendyolWebhookPayload(BaseModel):
    eventType: str
    timestamp: int
    message: TrendyolQuestionMessage

@router.post("/trendyol-qa")
async def handle_trendyol_qa(
    payload: TrendyolWebhookPayload,
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(None)
):
    """Trendyol Seller Q&A Webhook (Mock)."""
    # 1. Simple auth check (in reality, verify signature)
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    log.info(f"Received Trendyol QA webhook: {payload.model_dump_json()}")
    
    if payload.eventType != "QuestionReceived":
        return {"status": "ignored", "reason": f"Unhandled event type: {payload.eventType}"}

    customer_question = payload.message.text
    product_id = payload.message.productId
    
    # 2. Add system context for B2B Scenario
    # Tell the agent it's answering a specific product question on Trendyol
    system_message = (
        f"A customer ({payload.message.customerId}) asked a question on our Trendyol store.\n"
        f"The SKU of the product asked about: {product_id}\n"
        f"Please provide a short, polite, and clear answer to the customer using only the tools at your disposal.\n"
        f"Customer's question: {customer_question}"
    )

    try:
        # Run agent in background or wait for it (for demo, we'll await it)
        # Note: in a real webhook, we'd enqueue this and respond 200 immediately.
        # For this prototype, we'll process it synchronously and return the answer or log it.
        result = await run_agent(
            user_message=system_message,
            max_iterations=4
        )
        
        answer = result.get("answer", "")
        log.info(f"Generated reply for Trendyol question: {answer}")
        
        # In reality, we'd call Trendyol's API to post the answer back.
        
        return {
            "status": "success",
            "message_id": payload.message.messageId,
            "generated_answer": answer,
            "tools_used": result.get("tools_used")
        }
        
    except Exception as e:
        log.error(f"Error processing Trendyol webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Error generating answer")
