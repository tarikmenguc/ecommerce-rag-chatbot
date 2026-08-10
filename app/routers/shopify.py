from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import uuid

from app.db import get_session
from app.models import ShopifyJob, ShopifyJobStatus
from app.services.shopify_client import ShopifyClient
from app.config import get_settings

router = APIRouter(prefix="/shopify", tags=["shopify"])
settings = get_settings()

class OptimizeRequest(BaseModel):
    items: List[Dict[str, Any]] # Expecting list of {barcode, title, description, image_url, id}

class ApproveRequest(BaseModel):
    job_ids: List[int]

class ReviseRequest(BaseModel):
    prompt: str

class ManualApproveRequest(BaseModel):
    manual_text: str

@router.get("/connect")
async def connect_and_fetch():
    """Validates API keys and fetches first page of products."""
    try:
        client = ShopifyClient()
        data = await client.get_products(limit=50)
        
        # Shopify analysis
        products = data.get("products", [])
        total = len(products)
        
        needs_optimization = []
        for item in products:
            desc = item.get("body_html", "") or ""
            if len(desc) < 100:
                # Handle image URL mapping
                image_url = None
                if item.get("images") and len(item.get("images")) > 0:
                    image_url = item["images"][0].get("src")
                    
                needs_optimization.append({
                    "id": item.get("id"),
                    "barcode": item.get("variants", [{}])[0].get("barcode") if item.get("variants") else None,
                    "title": item.get("title"),
                    "description": desc,
                    "image_url": image_url
                })
                
        return {
            "status": "success",
            "total_products": total,
            "needs_optimization": needs_optimization,
            "sample_content": products[:2]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/optimize")
async def optimize_products(req: OptimizeRequest, session: AsyncSession = Depends(get_session)):
    """Puts selected products into the ShopifyJob queue for AI optimization."""
    batch_id = str(uuid.uuid4())
    jobs_created = 0
    
    for item in req.items:
        job = ShopifyJob(
            batch_id=batch_id,
            shopify_product_id=str(item.get("id", "")),
            barcode=item.get("barcode") or "",
            original_title=item.get("title") or "",
            original_description=item.get("description") or "",
            image_url=item.get("image_url") or ""
        )
        session.add(job)
        jobs_created += 1
        
    await session.commit()
    return {"status": "success", "batch_id": batch_id, "jobs_queued": jobs_created}

@router.get("/jobs")
async def list_jobs(session: AsyncSession = Depends(get_session)):
    """Lists all Shopify jobs for the UI Dashboard."""
    result = await session.execute(
        select(ShopifyJob).order_by(ShopifyJob.created_at.desc()).limit(100)
    )
    jobs = result.scalars().all()
    return jobs

@router.post("/jobs/approve")
async def approve_jobs(req: ApproveRequest, session: AsyncSession = Depends(get_session)):
    """Approves generated descriptions and sends them to Shopify API queue."""
    result = await session.execute(
        select(ShopifyJob).where(ShopifyJob.id.in_(req.job_ids))
    )
    jobs = result.scalars().all()
    
    approved_count = 0
    for job in jobs:
        if job.status == ShopifyJobStatus.AWAITING_APPROVAL:
            job.status = ShopifyJobStatus.SENDING
            approved_count += 1
            
    await session.commit()
    return {"status": "success", "approved_count": approved_count}

@router.post("/jobs/{job_id}/revise")
async def revise_job(job_id: int, req: ReviseRequest, session: AsyncSession = Depends(get_session)):
    from app.llm import revise_ecommerce_description
    job = await session.get(ShopifyJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Generate revision
    new_text = await revise_ecommerce_description(
        original_text=job.generated_description or "",
        revision_prompt=req.prompt
    )
    
    job.generated_description = new_text
    job.status = ShopifyJobStatus.AWAITING_APPROVAL
    await session.commit()
    
    return {"status": "success", "new_text": new_text}

@router.post("/jobs/{job_id}/regenerate")
async def regenerate_job(job_id: int, session: AsyncSession = Depends(get_session)):
    job = await session.get(ShopifyJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Put it back in the pipeline
    job.status = ShopifyJobStatus.TEXT_GENERATING
    # Clear the old description
    job.generated_description = None
    await session.commit()
    
    return {"status": "success"}

@router.post("/jobs/{job_id}/manual_approve")
async def manual_approve_job(job_id: int, req: ManualApproveRequest, session: AsyncSession = Depends(get_session)):
    job = await session.get(ShopifyJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job.generated_description = req.manual_text
    job.status = ShopifyJobStatus.SENDING
    await session.commit()
    
    return {"status": "success"}
