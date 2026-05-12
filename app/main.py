"""FastAPI entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from sqlalchemy import text
from app.config import get_settings
from app.db import Base, engine
from app.logger import CostCapExceeded  # Kendi özel hata sınıfımız
from app.routers import chat, health, search

settings = get_settings()
logging.basicConfig(level=settings.log_level)
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Week 1: create tables naively. Switch to Alembic migrations later.
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    log.info("Startup complete. env=%s", settings.app_env)
    yield
    await engine.dispose()


app = FastAPI(
    title="AI Engineer Starter",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(search.router)


# CostCapExceeded hatası fırlatıldığında bu fonksiyon otomatik devreye girer.
# Kullanıcıya 429 (Too Many Requests) HTTP kodu ve açıklayıcı bir mesaj döner.
@app.exception_handler(CostCapExceeded)
async def cost_cap_handler(request: Request, exc: CostCapExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"error": "daily_cost_cap_exceeded", "detail": str(exc)},
    )


@app.get("/")
async def root() -> dict:
    return {"name": "ai-engineer-starter", "docs": "/docs"}
