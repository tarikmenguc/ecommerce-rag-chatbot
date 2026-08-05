"""FastAPI entrypoint."""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from sqlalchemy import text
from app.config import get_settings
from app.db import Base, engine
from app.logger import CostCapExceeded  # Kendi özel hata sınıfımız
from app.worker import queue_poller
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter
from app.routers import admin, chat, health, search, description, agent_chat, webhook_trendyol

settings = get_settings()
logging.basicConfig(level=settings.log_level)
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Tabloları oluştur (ilk çalıştırmada batch_job tablosu da oluşur)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    log.info("Startup complete. env=%s", settings.app_env)

    # Faz 2: Batch queue poller'ı arka planda başlat
    poller_task = asyncio.create_task(queue_poller())
    log.info("✅ queue_poller arka planda başlatıldı.")

    yield

    # Kapatırken poller'ı durdur
    poller_task.cancel()
    await engine.dispose()



app = FastAPI(
    title="AI Engineer Starter",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(search.router)
app.include_router(admin.router)
app.include_router(description.router)
app.include_router(agent_chat.router)
app.include_router(webhook_trendyol.router)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# CostCapExceeded hatası fırlatıldığında bu fonksiyon otomatik devreye girer.
# Kullanıcıya 429 (Too Many Requests) HTTP kodu ve açıklayıcı bir mesaj döner.
@app.exception_handler(CostCapExceeded)
async def cost_cap_handler(request: Request, exc: CostCapExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"error": "daily_cost_cap_exceeded", "detail": str(exc)},
    )


# Serve the CopyAI frontend at the root URL
_public_dir = Path(__file__).parent.parent / "public"
if _public_dir.exists():
    app.mount("/ui", StaticFiles(directory=_public_dir, html=True), name="static")

@app.get("/")
async def root():
    index = _public_dir / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"name": "ai-engineer-starter", "docs": "/docs"}
