"""Week 1 homework: write these tests AI-off.

These are skeletons. Fill in the bodies by hand.
Use httpx.AsyncClient + ASGITransport against app.main.app.
"""
import pytest


@pytest.mark.skip(reason="AI-off homework")
@pytest.mark.asyncio
async def test_root_returns_name():
    # TODO (AI-off):
    #   async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
    #       r = await ac.get("/")
    #   assert r.status_code == 200
    #   assert r.json()["name"] == "ai-engineer-starter"
    raise NotImplementedError("Fill in by hand.")


@pytest.mark.skip(reason="AI-off homework")
@pytest.mark.asyncio
async def test_health_returns_ok_when_db_up():
    raise NotImplementedError("Fill in by hand.")
