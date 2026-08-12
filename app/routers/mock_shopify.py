from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter(prefix="/mock-shopify", tags=["mock_shopify"])

# In-memory store for mock products
MOCK_PRODUCTS = [
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

@router.get("/admin/api/{api_version}/products.json")
async def get_mock_products(api_version: str) -> Dict[str, Any]:
    """Returns fake product data simulating the Shopify API."""
    return {"products": MOCK_PRODUCTS}

@router.put("/admin/api/{api_version}/products/{product_id}.json")
async def update_mock_products(api_version: str, product_id: str, payload: dict) -> Dict[str, Any]:
    """Simulates a successful update to the Shopify API."""
    for p in MOCK_PRODUCTS:
        if str(p["id"]) == str(product_id):
            p["body_html"] = payload.get("product", {}).get("body_html", "")
            break
            
    return {
        "product": {
            "id": product_id,
            "body_html": payload.get("product", {}).get("body_html", "")
        }
    }

@router.post("/admin/api/{api_version}/products.json")
async def create_mock_product(api_version: str, payload: dict) -> Dict[str, Any]:
    """Simulates a successful creation of a new product in the Shopify API."""
    import random
    product_data = payload.get("product", {})
    new_id = random.randint(1000, 99999)
    
    new_product = {
        "id": new_id,
        "title": product_data.get("title", "New Product"),
        "body_html": product_data.get("body_html", ""),
        "images": product_data.get("images", []),
        "status": product_data.get("status", "draft")
    }
    
    MOCK_PRODUCTS.append(new_product)
    
    return {"product": new_product}
