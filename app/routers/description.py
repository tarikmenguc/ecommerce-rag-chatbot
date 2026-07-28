import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
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

router = APIRouter(prefix="/description", tags=["Description"])


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

