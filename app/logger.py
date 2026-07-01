"""
============================================================
YOU ARE LOOKING AT THE MOST IMPORTANT FILE IN THIS REPO.
============================================================

This is the LLM call logger + cost tracker.

HOMEWORK (Week 1, AI-off):
    Fill in the functions below BY HAND. No Copilot. No Cursor Chat.
    Only the OpenAI/Anthropic docs and the pricing pages are allowed.

Contract:
    - `log_llm_call(...)` must be called for every model invocation.
    - It records: timestamp, model, input tokens, output tokens,
      input cost USD, output cost USD, total cost USD, latency ms,
      and the caller function name.
    - It persists the row to Postgres (`llm_call_log` table).
    - It enforces `DAILY_COST_CAP_USD`: if today's total > cap, raise
      `CostCapExceeded`.

Why this matters:
    In the YouTube talk you watched, the speaker said the #1 reason
    juniors get burned on LLM projects is forgetting to track cost.
    This file is your insurance. Write it well.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, timezone, datetime
from typing import Any

from sqlalchemy import select, func

from app.config import get_settings
from app.db import session_scope

# Prices in USD per 1M tokens. Update as pricing changes.
# Source: https://openai.com/api/pricing/ & https://ai.google.dev/pricing
PRICES: dict[str, dict[str, float]] = {
    "gpt-4o-mini":            {"input": 0.150, "output": 0.600},
    "gpt-4o":                 {"input": 2.500, "output": 10.000},
    "text-embedding-3-small": {"input": 0.020, "output": 0.000},
    "gemini-3.5-flash":       {"input": 0.000, "output": 0.000},
    "gemini-3.1-flash-lite":  {"input": 0.000, "output": 0.000},
}


class CostCapExceeded(Exception):
    """Raised when the daily cost cap is hit."""


@dataclass
class LlmCall:
    caller: str
    api_key: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float

    @property
    def input_cost_usd(self) -> float:
        rate = PRICES.get(self.model, {}).get("input", 0.0)
        return rate * self.input_tokens / 1_000_000

    @property
    def output_cost_usd(self) -> float:
        rate = PRICES.get(self.model, {}).get("output", 0.0)
        return rate * self.output_tokens / 1_000_000

    @property
    def total_cost_usd(self) -> float:
        return self.input_cost_usd + self.output_cost_usd


async def log_llm_call(call: LlmCall) -> None:
    """
    TODO (Week 1, AI-off):
        1. Open a DB session.
        2. INSERT into llm_call_log (created_at, caller, model,
           input_tokens, output_tokens, input_cost_usd,
           output_cost_usd, total_cost_usd, latency_ms).
        3. SELECT SUM(total_cost_usd) WHERE created_at::date = today.
        4. If sum > settings.daily_cost_cap_usd -> raise CostCapExceeded.

    This is the stub. You fill it. Do not delete this docstring.
    """
    # Döngüsel import'u önlemek için fonksiyon içinde import ediyoruz.
    # (models.py → db.py → logger.py → models.py döngüsünü kırar)
    from app.models import LlmCallLog

    settings = get_settings()

    async with session_scope() as session:

        # ADIM 1 — Bugünkü toplam harcamayı veritabanından sorgula (Global)
        today = datetime.now(tz=timezone.utc).date()
        result = await session.execute(
            select(func.sum(LlmCallLog.total_cost_usd)).where(
                func.date(LlmCallLog.created_at) == today
            )
        )
        daily_total: float = result.scalar() or 0.0

        # ADIM 1.5 — Kullanıcı bazlı harcamayı sorgula (Per-User)
        user_result = await session.execute(
            select(func.sum(LlmCallLog.total_cost_usd)).where(
                func.date(LlmCallLog.created_at) == today,
                LlmCallLog.api_key == call.api_key
            )
        )
        user_daily_total: float = user_result.scalar() or 0.0

        # ADIM 2 — Günlük bütçe kontrolü (Global & Per-User)
        if daily_total + call.total_cost_usd > settings.daily_cost_cap_usd:
            raise CostCapExceeded(
                f"Global günlük maliyet sınırı aşıldı: "
                f"${daily_total + call.total_cost_usd:.4f} > ${settings.daily_cost_cap_usd:.4f}"
            )
            
        if user_daily_total + call.total_cost_usd > settings.user_daily_cost_cap_usd:
            raise CostCapExceeded(
                f"Kullanıcı günlük maliyet sınırı aşıldı: "
                f"${user_daily_total + call.total_cost_usd:.4f} > ${settings.user_daily_cost_cap_usd:.4f}"
            )

        # ADIM 3 — Bütçe aşılmadıysa kaydı veritabanına ekle (INSERT)
        row = LlmCallLog(
            caller=call.caller,
            api_key=call.api_key,
            model=call.model,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            input_cost_usd=call.input_cost_usd,
            output_cost_usd=call.output_cost_usd,
            total_cost_usd=call.total_cost_usd,
            latency_ms=call.latency_ms,
        )
        session.add(row)
        # flush() veriyi DB'ye gönderir ama kalıcı yapmaz.
        # session_scope'taki commit() bu bloğun sonunda kalıcı yazar.
        await session.flush()


def timed_llm_call(caller: str):
    """
    Decorator hint — another AI-off exercise.

    Usage (after you implement it):
        @timed_llm_call(caller="chat.generate_answer")
        async def generate_answer(...):
            resp = await openai_client.chat.completions.create(...)
            return resp, resp.usage.prompt_tokens, resp.usage.completion_tokens

    The decorator should:
      - time the inner call
      - build an LlmCall from its return value
      - await log_llm_call(call)
      - return the original response (not the tuple)
    """
    import functools
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any):
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            
            # Unpack response depending on length
            if isinstance(result, tuple) and len(result) == 5:
                resp, in_tok, out_tok, model, api_key = result
            elif isinstance(result, tuple) and len(result) == 3:
                resp, in_tok, out_tok = result
                model = kwargs.get("model", "unknown")
                api_key = kwargs.get("api_key", "unknown")
            else:
                raise ValueError("Decorated function must return (resp, in_tok, out_tok) or (resp, in_tok, out_tok, model, api_key)")

            latency_ms = (time.perf_counter() - start) * 1000
            
            call = LlmCall(
                caller=caller,
                api_key=api_key,
                model=model,
                input_tokens=in_tok,
                output_tokens=out_tok,
                latency_ms=latency_ms,
            )
            await log_llm_call(call)
            return resp
        return wrapper
    return decorator
