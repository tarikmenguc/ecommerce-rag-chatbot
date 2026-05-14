"""SQLAlchemy ORM models."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector  # enabled for Week 2

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
    api_key: Mapped[str] = mapped_column(String(64), server_default="unknown")
    model: Mapped[str] = mapped_column(String(64))
    answer: Mapped[str] = mapped_column(Text)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)


class Product(Base):
    """Week 2 — e-commerce catalog target table."""
    __tablename__ = "product"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(128), index=True)
    price_usd: Mapped[float] = mapped_column(Float, default=0.0)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024))  # BAAI/bge-m3
