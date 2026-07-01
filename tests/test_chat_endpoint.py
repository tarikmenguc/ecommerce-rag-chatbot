"""
Integration tests for POST /chat endpoint.

Strateji:
  - Gerçek OpenAI'ye gitmiyoruz → chat_completion mock'lanıyor.
  - Gerçek DB'ye gitmiyoruz  → log_llm_call mock'lanıyor +
    FastAPI'nin dependency_overrides ile get_session sahteleniyor.
  - Sadece endpoint'in kendi mantığını test ediyoruz.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import get_session
from app.main import app

# Sahte OpenAI cevabı: (metin, input_token, output_token)
# Updated to return valid JSON for the structured output logic
FAKE_LLM_RESPONSE = ('{"is_product_related": true, "answer": "Merhaba! Nasıl yardımcı olabilirim?"}', 10, 20)


# ---------------------------------------------------------------------------
# Sahte DB session — FastAPI dependency_overrides ile inject edilir
# ---------------------------------------------------------------------------
async def fake_get_session():
    """Gerçek Postgres'e bağlanmak yerine sahte session verir."""
    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    yield session


# ---------------------------------------------------------------------------
# Test 1 — Normal istek → 200 ve "answer" alanı gelir
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_chat_returns_200_with_answer():
    app.dependency_overrides[get_session] = fake_get_session
    try:
        with patch("app.routers.chat.chat_completion", new=AsyncMock(return_value=FAKE_LLM_RESPONSE)), \
             patch("app.routers.chat.log_llm_call", new=AsyncMock()), \
             patch("app.llm.check_moderation", new=AsyncMock()):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"X-API-Key": "tarik-proje"}) as ac:
                response = await ac.post("/chat", json={"message": "Merhaba"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert data["answer"] == "Merhaba! Nasıl yardımcı olabilirim?"



@pytest.mark.asyncio
async def test_chat_empty_message_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"X-API-Key": "tarik-proje"}) as ac:
        response = await ac.post("/chat", json={"message": ""})

  
    assert response.status_code == 422



@pytest.mark.asyncio
async def test_chat_response_has_cost_and_tokens():
    app.dependency_overrides[get_session] = fake_get_session
    try:
        with patch("app.routers.chat.chat_completion", new=AsyncMock(return_value=FAKE_LLM_RESPONSE)), \
             patch("app.routers.chat.log_llm_call", new=AsyncMock()), \
             patch("app.llm.check_moderation", new=AsyncMock()):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"X-API-Key": "tarik-proje"}) as ac:
                response = await ac.post("/chat", json={"message": "Token testi"})
    finally:
        app.dependency_overrides.clear()

    data = response.json()
    # Sahte cevap 10 input + 20 output token döndürdü
    assert data["input_tokens"] == 10
    assert data["output_tokens"] == 20
    # gpt-4o-mini fiyatına göre maliyet 0'dan büyük olmalı
    assert data["cost_usd"] > 0


# ---------------------------------------------------------------------------
# Test 4 — OpenAI hata fırlatırsa → endpoint 502 döner
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_chat_returns_502_when_llm_fails():
    app.dependency_overrides[get_session] = fake_get_session
    try:
        with patch("app.routers.chat.chat_completion", new=AsyncMock(side_effect=RuntimeError("API down"))), \
             patch("app.llm.check_moderation", new=AsyncMock()):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"X-API-Key": "tarik-proje"}) as ac:
                response = await ac.post("/chat", json={"message": "Hata testi"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert "LLM error" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Test 5 — system_prompt ile istek → model alanı response'da geliyor mu?
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_chat_with_system_prompt_returns_model_field():
    app.dependency_overrides[get_session] = fake_get_session
    try:
        with patch("app.routers.chat.chat_completion", new=AsyncMock(return_value=FAKE_LLM_RESPONSE)), \
             patch("app.routers.chat.log_llm_call", new=AsyncMock()), \
             patch("app.llm.check_moderation", new=AsyncMock()):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"X-API-Key": "tarik-proje"}) as ac:
                response = await ac.post("/chat", json={
                    "message": "Bana Python öğret",
                    "system_prompt": "Sen bir Python hocasısın.",
                    "model": "gpt-4o-mini",
                })
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["model"] == "gpt-4o-mini"
    assert "latency_ms" in data
