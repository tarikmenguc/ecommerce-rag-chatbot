"""SQLAlchemy ORM models — V2 (Week 5: Advanced Chunking).

V2 Changes vs V1:
- Product: `embedding` and `description` columns REMOVED (now stored in ProductChunk).
  `avg_rating` added to support SQL Agent queries in Week 6.
- ProductChunk: NEW table. Each product has N chunks (metadata, description, review).
  Only this table holds embeddings. Searching is done against this table.
"""
from __future__ import annotations

from datetime import datetime
from typing import List

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.db import Base


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
