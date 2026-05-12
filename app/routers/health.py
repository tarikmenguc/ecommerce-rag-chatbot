"""Health endpoint — keep it cheap, keep it honest."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(session: AsyncSession = Depends(get_session)) -> dict:
    # Shallow check: DB is reachable.
    result = await session.execute(text("SELECT 1"))
    db_ok = result.scalar() == 1
    return {"status": "ok" if db_ok else "degraded", "db": db_ok}
