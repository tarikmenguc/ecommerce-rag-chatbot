import asyncio
import base64
import logging
from typing import Dict, Any, List

import httpx

from app.config import get_settings

log = logging.getLogger("app.shopify_client")
settings = get_settings()

class ShopifyClient:
    """Shopify Partner API V2 — Rate-limited client."""

    def __init__(self):
        self.seller_id = settings.shopify_store_domain
        self.api_key = settings.shopify_access_token or "mock"
        self.api_secret = "mock" # Shopify doesn't need secret for admin API if using access token, we keep it for mock logic
        
        self.is_mock = self.api_key == "mock"
        
        if self.is_mock:
            self.base_url = f"http://localhost:8000/mock-shopify/admin/api/{settings.shopify_api_version}/products.json"
            log.info("ShopifyClient initialized in MOCK mode.")
        else:
            self.base_url = f"https://{self.seller_id}/admin/api/{settings.shopify_api_version}/products.json"
        
        # Calculate delay based on rate limit (e.g., 100 req/min)
        self.delay_between_requests = 60.0 / float(settings.shopify_rate_limit_per_min) if settings.shopify_rate_limit_per_min else 0.6
        self._semaphore = asyncio.Semaphore(1) # We can process requests sequentially
        
    @property
    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"{self.seller_id} - AI Optimizer App"
        }
        
        if not self.is_mock:
            headers["X-Shopify-Access-Token"] = self.api_key
            
        return headers

    async def _request(self, method: str, url: str, json_data: dict | None = None, params: dict | None = None) -> httpx.Response:
        """Execute rate-limited HTTP request with Exponential Backoff."""
        max_retries = 3
        backoff_factor = 2
        current_delay = 1.0

        async with self._semaphore:
            # Enforce global rate limit delay
            await asyncio.sleep(self.delay_between_requests)
            
            async with httpx.AsyncClient() as client:
                for attempt in range(max_retries + 1):
                    try:
                        request_params = {
                            "method": method,
                            "url": url,
                            "headers": self._headers,
                            "timeout": 30.0
                        }
                        if json_data:
                            request_params["json"] = json_data
                        if params:
                            request_params["params"] = params
                            
                        resp = await client.request(**request_params)
                        
                        if resp.status_code == 429:
                            log.warning(f"Shopify Rate Limit (429) hit. Attempt {attempt + 1}/{max_retries}. Sleeping for {current_delay}s")
                            if attempt < max_retries:
                                await asyncio.sleep(current_delay)
                                current_delay *= backoff_factor
                                continue
                            
                        resp.raise_for_status()
                        return resp
                        
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 429 and attempt < max_retries:
                            continue # handled above, but just in case
                        log.error(f"Shopify HTTP error: {e.response.status_code} - {e.response.text}")
                        raise
                    except Exception as e:
                        log.error(f"Shopify Request failed: {str(e)}")
                        if attempt == max_retries:
                            raise
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff_factor
                
                raise RuntimeError("Max retries exceeded for Shopify API")


    async def get_products(self, limit: int = 50) -> Dict[str, Any]:
        """Fetch products (Shopify Admin API Read)"""
        params = {
            "limit": limit
        }
        resp = await self._request("GET", self.base_url, params=params)
        return resp.json()

    async def update_product_description(self, product_id: str, new_description: str) -> Dict[str, Any]:
        """Update product description ONLY (Shopify Admin API)."""
        payload = {
            "product": {
                "id": product_id,
                "body_html": new_description
            }
        }
        url = self.base_url.replace("products.json", f"products/{product_id}.json")
        resp = await self._request("PUT", url, json_data=payload)
        return resp.json()
