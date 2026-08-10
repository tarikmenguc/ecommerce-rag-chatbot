import asyncio
import logging
from sqlalchemy import select

from app.db import SessionLocal
from app.models import ShopifyJob, ShopifyJobStatus
from app.vision import analyze_product_image
from app.llm import generate_description_from_vision, generate_ecommerce_description
from app.services.shopify_client import ShopifyClient

log = logging.getLogger("app.shopify_worker")

POLL_INTERVAL = 5

async def _process_shopify_job(job: ShopifyJob, session, client: ShopifyClient):
    try:
        # Step 1: Vision Processing (if image_url is provided and not already done)
        if job.image_url and job.status == ShopifyJobStatus.PENDING:
            job.status = ShopifyJobStatus.VISION_PROCESSING
            await session.commit()
            
            vision_text = await analyze_product_image(job.image_url)
            job.vision_analysis = vision_text
            
            # Move to next phase
            job.status = ShopifyJobStatus.TEXT_GENERATING
            await session.commit()
            
        elif job.status == ShopifyJobStatus.PENDING:
            # Skip vision if no image
            job.status = ShopifyJobStatus.TEXT_GENERATING
            await session.commit()

        # Step 2: Text Generation
        if job.status == ShopifyJobStatus.TEXT_GENERATING:
            if job.vision_analysis:
                text = await generate_description_from_vision(
                    title=job.original_title,
                    vision_analysis=job.vision_analysis,
                    original_description=job.original_description
                )
            else:
                prompt = f"Title: {job.original_title}\nFeatures: {job.original_description or ''}"
                text = await generate_ecommerce_description(prompt)
                
            job.generated_description = text
            job.status = ShopifyJobStatus.AWAITING_APPROVAL
            await session.commit()
            log.info(f"Shopify Job {job.id} generated text and awaits approval.")

        # Step 3: Sending to Shopify (this happens AFTER user approves, so worker picks it up if SENDING)
        if job.status == ShopifyJobStatus.SENDING:
            if not job.generated_description:
                raise ValueError("Cannot send to Shopify: Generated description is empty.")
                
            await client.update_product_description(
                barcode=job.barcode,
                new_description=job.generated_description
            )
            job.status = ShopifyJobStatus.COMPLETED
            await session.commit()
            log.info(f"Shopify Job {job.id} successfully sent to Shopify.")

    except Exception as e:
        log.error(f"Shopify Job {job.id} failed: {str(e)}")
        job.status = ShopifyJobStatus.FAILED
        job.error_message = str(e)
        await session.commit()


async def shopify_queue_poller():
    """Polls the ShopifyJob table for jobs in PENDING, TEXT_GENERATING, or SENDING states."""
    log.info("🚀 shopify_queue_poller started")
    client = ShopifyClient()
    
    while True:
        try:
            async with SessionLocal() as session:
                # Fetch jobs that need processing (limit to 5 at a time)
                result = await session.execute(
                    select(ShopifyJob)
                    .where(ShopifyJob.status.in_([
                        ShopifyJobStatus.PENDING, 
                        ShopifyJobStatus.TEXT_GENERATING, 
                        ShopifyJobStatus.SENDING
                    ]))
                    .order_by(ShopifyJob.created_at)
                    .limit(5)
                )
                active_jobs = result.scalars().all()
                
                for job in active_jobs:
                    await _process_shopify_job(job, session, client)
                    
        except Exception as e:
            log.error(f"❗ shopify_queue_poller error: {e}")
            
        await asyncio.sleep(POLL_INTERVAL)
