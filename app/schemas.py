"""Pydantic request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    model: str | None = None
    system_prompt: str | None = None


class ChatResponse(BaseModel):
    answer: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float


class ProductQuery(BaseModel):
    """Week 2 — RAG search request."""
    query: str = Field(min_length=2, max_length=512)
    top_k: int = Field(default=5, ge=1, le=20)
    category: str | None = None


class ProductHit(BaseModel):
    sku: str
    title: str
    category: str
    price_usd: float
    score: float


class ProductSearchResponse(BaseModel):
    query: str
    hits: list[ProductHit]
    answer: str | None = None
    cost_usd: float
