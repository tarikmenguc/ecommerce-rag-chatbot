from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter(prefix="/mock-shopify", tags=["mock_shopify"])

@router.get("/admin/api/{api_version}/products.json")
async def get_mock_products(api_version: str) -> Dict[str, Any]:
    """Returns fake product data simulating the Shopify API."""
    mock_data = {
        "products": [
            {
                "id": 101,
                "title": "Harley Davidson Kışlık Erkek Bot",
                "body_html": "Siyah renk bot. Sıcak tutar. Deri.",
                "images": [
                    {"src": "https://m.media-amazon.com/images/I/71R22X54e5L._AC_UY1000_.jpg"}
                ],
                "status": "active"
            },
            {
                "id": 102,
                "title": "The North Face Mont",
                "body_html": "Erkek mont. Kırmızı renkli, kapüşonlu, fermuarlı kışlık.",
                "images": [
                    {"src": "https://m.media-amazon.com/images/I/61N9uS2rM8L._AC_SX569_.jpg"}
                ],
                "status": "active"
            }
        ]
    }
    return mock_data

@router.put("/admin/api/{api_version}/products/{product_id}.json")
async def update_mock_products(api_version: str, product_id: str, payload: dict) -> Dict[str, Any]:
    """Simulates a successful update to the Shopify API."""
    return {
        "product": {
            "id": product_id,
            "body_html": payload.get("product", {}).get("body_html", "")
        }
    }
