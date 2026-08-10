from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import time

from app.vision import analyze_product_image
from app.llm import generate_description_from_vision

router = APIRouter(prefix="/shopify", tags=["shopify_vision"])

class VisionPreviewRequest(BaseModel):
    image_url: str
    title: str
    original_description: str | None = None

@router.post("/vision-preview")
async def vision_preview(req: VisionPreviewRequest):
    """Preview endpoint for multimodal vision pipeline."""
    try:
        start = time.time()
        
        # 1. Analyze Image
        vision_analysis = await analyze_product_image(req.image_url)
        
        # 2. Generate Description
        text, _, _, _, _ = await generate_description_from_vision(
            title=req.title,
            vision_analysis=vision_analysis,
            original_description=req.original_description
        )
        
        elapsed_ms = int((time.time() - start) * 1000)
        
        return {
            "status": "success",
            "vision_analysis": vision_analysis,
            "generated_description": text,
            "processing_time_ms": elapsed_ms
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
