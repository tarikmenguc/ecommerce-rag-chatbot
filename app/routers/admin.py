"""
Admin dashboard router.

GET /admin/dashboard  →  Aggregated stats from llm_call_log.

Metrics returned:
  - today_cost_usd        : total spend today (global)
  - today_request_count   : total LLM calls today
  - last_24h_request_count: requests in the last 24 hours
  - avg_latency_ms        : average response latency (all time)
  - top_model             : most-used model (all time)
  - cost_by_api_key       : per-key spend today
  - cost_by_model         : per-model spend today
  - hourly_requests_today : request count per hour today (for sparkline)
"""
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, cast, Integer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_api_key
from app.db import get_session

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard")
async def get_dashboard(
    session: AsyncSession = Depends(get_session),
    api_key: str = Depends(verify_api_key),
) -> dict:
    """Return aggregated monitoring metrics from llm_call_log."""
    # Döngüsel import'u önlemek için içeride import ediyoruz
    from app.models import LlmCallLog

    now_utc = datetime.now(tz=timezone.utc)
    today = now_utc.date()
    last_24h = now_utc - timedelta(hours=24)

    # --- 1. Bugünkü toplam maliyet ---
    result = await session.execute(
        select(func.coalesce(func.sum(LlmCallLog.total_cost_usd), 0.0)).where(
            func.date(LlmCallLog.created_at) == today
        )
    )
    today_cost_usd: float = round(result.scalar(), 6)

    # --- 2. Bugünkü toplam istek sayısı ---
    result = await session.execute(
        select(func.count()).where(func.date(LlmCallLog.created_at) == today)
    )
    today_request_count: int = result.scalar()

    # --- 3. Son 24 saatteki istek sayısı ---
    result = await session.execute(
        select(func.count()).where(LlmCallLog.created_at >= last_24h)
    )
    last_24h_request_count: int = result.scalar()

    # --- 4. Ortalama gecikme (tüm zamanlar) ---
    result = await session.execute(
        select(func.coalesce(func.avg(LlmCallLog.latency_ms), 0.0))
    )
    avg_latency_ms: float = round(result.scalar(), 2)

    # --- 5. En çok kullanılan model (tüm zamanlar) ---
    result = await session.execute(
        select(LlmCallLog.model, func.count().label("cnt"))
        .group_by(LlmCallLog.model)
        .order_by(func.count().desc())
        .limit(1)
    )
    row = result.first()
    top_model: str = row[0] if row else "N/A"

    # --- 6. API key bazlı bugünkü maliyet ---
    result = await session.execute(
        select(
            LlmCallLog.api_key,
            func.coalesce(func.sum(LlmCallLog.total_cost_usd), 0.0).label("cost"),
            func.count().label("requests"),
        )
        .where(func.date(LlmCallLog.created_at) == today)
        .group_by(LlmCallLog.api_key)
        .order_by(func.sum(LlmCallLog.total_cost_usd).desc())
    )
    cost_by_api_key = [
        {"api_key": r[0], "cost_usd": round(r[1], 6), "requests": r[2]}
        for r in result.all()
    ]

    # --- 7. Model bazlı bugünkü maliyet ---
    result = await session.execute(
        select(
            LlmCallLog.model,
            func.coalesce(func.sum(LlmCallLog.total_cost_usd), 0.0).label("cost"),
            func.count().label("requests"),
        )
        .where(func.date(LlmCallLog.created_at) == today)
        .group_by(LlmCallLog.model)
        .order_by(func.sum(LlmCallLog.total_cost_usd).desc())
    )
    cost_by_model = [
        {"model": r[0], "cost_usd": round(r[1], 6), "requests": r[2]}
        for r in result.all()
    ]

    # --- 8. Saatlik istek dağılımı (bugün, sparkline için) ---
    result = await session.execute(
        select(
            cast(func.extract("hour", LlmCallLog.created_at), Integer).label("hour"),
            func.count().label("requests"),
        )
        .where(func.date(LlmCallLog.created_at) == today)
        .group_by("hour")
        .order_by("hour")
    )
    hourly_requests_today = [
        {"hour": r[0], "requests": r[1]} for r in result.all()
    ]

    return {
        "generated_at": now_utc.isoformat(),
        "today": str(today),
        "summary": {
            "today_cost_usd": today_cost_usd,
            "today_request_count": today_request_count,
            "last_24h_request_count": last_24h_request_count,
            "avg_latency_ms": avg_latency_ms,
            "top_model": top_model,
        },
        "cost_by_api_key": cost_by_api_key,
        "cost_by_model": cost_by_model,
        "hourly_requests_today": hourly_requests_today,
    }
