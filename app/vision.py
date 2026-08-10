import base64
import httpx
import logging
from fastapi import HTTPException
from app.config import get_settings

log = logging.getLogger("app.vision")
settings = get_settings()

async def analyze_product_image(image_url: str) -> str:
    """Downloads an image from URL and uses Ollama Vision model to analyze it."""
    
    # 1. Download the image
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(image_url, timeout=30.0)
            resp.raise_for_status()
            image_bytes = resp.content
            
            if len(image_bytes) > 10 * 1024 * 1024:
                raise ValueError("Image size exceeds 10MB limit.")
                
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    except Exception as e:
        log.error(f"Failed to download image from {image_url}: {e}")
        return f"Error downloading image: {str(e)}"

    # 2. Call Ollama Vision Model
    url = f"{settings.ollama_base_url}/api/chat"
    prompt = (
        "Analyze this e-commerce product image. "
        "List the following in English: color, material, style, notable features, target audience. "
        "Be factual and concise."
    )
    
    payload = {
        "model": settings.ollama_vision_model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [image_base64]
            }
        ],
        "stream": False,
        "options": {
            "temperature": 0.2
        }
    }
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=120.0)
            resp.raise_for_status()
            data = resp.json()
            
            vision_text = data.get("message", {}).get("content", "")
            return vision_text.strip()
    except Exception as e:
        log.error(f"Ollama Vision model failed: {e}")
        return f"Error analyzing image with vision model: {str(e)}"
