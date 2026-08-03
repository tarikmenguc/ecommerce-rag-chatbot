import logging
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import BatchJob, JobStatus
from app.schemas import (
    BatchProcessRequest,
    BatchProcessResponse,
    DescriptionRequest,
    DescriptionResponse,
)
from app.llm import generate_ecommerce_description

log = logging.getLogger("app.description")

router = APIRouter(prefix="/description", tags=["Description"])


# ── Trigger-Batch schema ────────────────────────────────────────────────────
class TriggerBatchRequest(BaseModel):
    sheet_url: str | None = None  # informational only, stored for future use


class BatchSingleRequest(BaseModel):
    """Tek ürün için düz (flat) batch isteği — n8n 'Using Fields' ile uyumlu."""
    webhook_url: str
    sheet_url: str | None = None
    external_reference_id: str
    product_title: str
    product_features: str | None = None



class TriggerBatchResponse(BaseModel):
    status: str
    message: str


@router.post("/generate", response_model=DescriptionResponse)
async def generate_description(req: DescriptionRequest):
    """Tek ürün için anlık açıklama üretir (mevcut endpoint)."""
    prompt = f"Title: {req.product_name}\n\nFeatures:\n{req.features if req.features else ''}"
    text = await generate_ecommerce_description(prompt)
    return DescriptionResponse(description=text, model="ecommerce-llama3")


@router.post(
    "/batch",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=BatchProcessResponse,
)
async def start_batch(
    req: BatchProcessRequest,
    db: AsyncSession = Depends(get_session),
):
    """Toplu açıklama üretim isteği.

    - Tüm ürünleri PostgreSQL'e PENDING olarak kaydeder.
    - Anında 202 Accepted döner (n8n timeout almaz).
    - Arka planda çalışan queue_poller() işleri sırayla tamamlar.
    - Her iş bittiğinde webhook_url'e POST atar.
    """
    batch_id = str(uuid.uuid4())

    # Gelen ürünleri DB'ye toplu kaydet
    jobs = [
        BatchJob(
            batch_id=batch_id,
            external_reference_id=item.external_reference_id,
            product_title=item.product_title,
            product_features=item.product_features,
            webhook_url=req.webhook_url,
            sheet_url=req.sheet_url,
            status=JobStatus.PENDING,
        )
        for item in req.products
    ]
    db.add_all(jobs)
    await db.commit()

    return BatchProcessResponse(
        message="İşlem sıraya alındı. Sonuçlar webhook ile gönderilecek.",
        batch_id=batch_id,
        total_products=len(req.products),
    )


@router.post("/batch-single", status_code=status.HTTP_202_ACCEPTED)
async def start_batch_single(req: BatchSingleRequest, db: AsyncSession = Depends(get_session)):
    """Tekli ürün için düz form girişiyle batch oluşturur (n8n Webhook ile entegrasyon için)."""
    batch_id = str(uuid.uuid4())
    job = BatchJob(
        batch_id=batch_id,
        external_reference_id=req.external_reference_id,
        product_title=req.product_title,
        product_features=req.product_features,
        webhook_url=req.webhook_url,
        sheet_url=req.sheet_url,
        status=JobStatus.PENDING,
    )
    db.add(job)
    await db.commit()
    return {"message": "İşlem sıraya alındı.", "batch_id": batch_id}


# ── Trigger n8n Pipeline ────────────────────────────────────────────────────
N8N_WEBHOOK_START = "http://n8n_automation:5678/webhook/start-batch"


@router.post("/trigger-batch", response_model=TriggerBatchResponse)
async def trigger_batch_pipeline(req: TriggerBatchRequest):
    """Fires n8n's Webhook to kick off the Google Sheets → Async AI pipeline.

    Called by the UI's 'Trigger n8n Pipeline' button.
    Proxied through FastAPI to avoid browser CORS restrictions.
    n8n is reached via Docker's internal network (not localhost).
    """
    log.info("🚀 /trigger-batch called. sheet_url=%s", req.sheet_url)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                N8N_WEBHOOK_START,
                json={"sheet_url": req.sheet_url},
                timeout=10.0,
            )
        log.info("✅ n8n webhook responded with HTTP %s", resp.status_code)
        return TriggerBatchResponse(
            status="triggered",
            message=f"Pipeline started! n8n responded with HTTP {resp.status_code}. "
                    "Check your Google Sheet — products will be updated within ~60 seconds.",
        )
    except httpx.ConnectError:
        log.error("❌ n8n unreachable at %s", N8N_WEBHOOK_START)
        raise HTTPException(
            status_code=503,
            detail="n8n is not reachable. Make sure the n8n_automation container is running.",
        )
    except Exception as exc:
        log.error("❌ trigger-batch error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
