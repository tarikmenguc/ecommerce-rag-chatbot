from fastapi import APIRouter
from app.schemas import DescriptionRequest, DescriptionResponse
from app.llm import generate_ecommerce_description

router = APIRouter(prefix="/description", tags=["Description"])

@router.post("/generate", response_model=DescriptionResponse)
async def generate_description(req: DescriptionRequest):
    # Modelin fine-tune edilirken gördüğü veri formatına (Title / Features) birebir uyuyoruz
    prompt = f"Title: {req.product_name}\n\nFeatures:\n{req.features if req.features else ''}"
    
    text = await generate_ecommerce_description(prompt)
    
    return DescriptionResponse(
        description=text,
        model="ecommerce-llama3",
    )
