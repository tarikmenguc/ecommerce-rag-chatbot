"""SQLAlchemy ORM models — V2 (Week 5: Advanced Chunking).

V2 Changes vs V1:
- Product: `embedding` and `description` columns REMOVED (now stored in ProductChunk).
  `avg_rating` added to support SQL Agent queries in Week 6.
- ProductChunk: NEW table. Each product has N chunks (metadata, description, review).
  Only this table holds embeddings. Searching is done against this table.

Faz 2:
- BatchJob: Async batch description generation job tracker.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import List

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.db import Base


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class LlmCallLog(Base):
    __tablename__ = "llm_call_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    caller: Mapped[str] = mapped_column(String(128), index=True)
    api_key: Mapped[str] = mapped_column(String(64), index=True, server_default="unknown")
    model: Mapped[str] = mapped_column(String(64), index=True)
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)
    input_cost_usd: Mapped[float] = mapped_column(Float)
    output_cost_usd: Mapped[float] = mapped_column(Float)
    total_cost_usd: Mapped[float] = mapped_column(Float)
    latency_ms: Mapped[float] = mapped_column(Float)


class Interaction(Base):
    __tablename__ = "interaction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    user_query: Mapped[str] = mapped_column(Text)
    user_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    api_key: Mapped[str] = mapped_column(String(64), server_default="unknown")
    model: Mapped[str] = mapped_column(String(64))
    answer: Mapped[str] = mapped_column(Text)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)


class Product(Base):
    """Week 5 V2 — Lightweight product catalog.

    No longer holds embeddings or raw description text.
    All semantic content lives in ProductChunk rows.
    """
    __tablename__ = "product"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512))
    category: Mapped[str] = mapped_column(String(256), index=True)
    price_usd: Mapped[float] = mapped_column(Float, default=0.0)
    avg_rating: Mapped[float] = mapped_column(Float, default=0.0)

    # One product → many chunks
    chunks: Mapped[List["ProductChunk"]] = relationship(
        "ProductChunk", back_populates="product", cascade="all, delete-orphan"
    )


class ProductChunk(Base):
    """Week 5 V2 — Chunk-level storage for embeddings.

    chunk_type values:
        'metadata'    — Structured product attributes (title, brand, price, category).
                        Strategy: Document-Aware (one chunk per product).
        'description' — Long product description / features list.
                        Strategy: Recursive Character Splitting (500 chars, 50 overlap).
        'review'      — Customer review text.
                        Strategy: Sentence-level (one review = one chunk, top-5 per product).

    content is always context-enriched:
        "[{product_title} — {chunk_type}]: {raw_text}"
    """
    __tablename__ = "product_chunk"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_sku: Mapped[str] = mapped_column(
        String(64), ForeignKey("product.sku", ondelete="CASCADE"), index=True
    )
    chunk_type: Mapped[str] = mapped_column(String(32), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024))  # BAAI/bge-m3

    # Many chunks → one product
    product: Mapped["Product"] = relationship("Product", back_populates="chunks")


class BatchJob(Base):
    """Faz 2 — Async batch description job tracker.

    queue_poller() bu tabloyu her 5 saniyede bir okur ve
    PENDING işleri sırayla Ollama'ya gönderir.
    """
    __tablename__ = "batch_job"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), index=True)
    external_reference_id: Mapped[str] = mapped_column(String(128))
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="jobstatus"), default=JobStatus.PENDING, index=True
    )
    product_title: Mapped[str] = mapped_column(String(512))
    product_features: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook_url: Mapped[str] = mapped_column(String(2048))
    sheet_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )


class ShopifyJobStatus(str, enum.Enum):
    PENDING = "PENDING"
    VISION_PROCESSING = "VISION"
    TEXT_GENERATING = "TEXT_GEN"
    AWAITING_APPROVAL = "APPROVAL"
    SENDING = "SENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ShopifyJob(Base):
    __tablename__ = "shopify_job"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), index=True)
    shopify_product_id: Mapped[str] = mapped_column(String(128), index=True)
    barcode: Mapped[str] = mapped_column(String(128), index=True)
    original_title: Mapped[str] = mapped_column(String(512))
    original_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    vision_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ShopifyJobStatus] = mapped_column(
        Enum(ShopifyJobStatus, name="shopifyjobstatus"), default=ShopifyJobStatus.PENDING, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

