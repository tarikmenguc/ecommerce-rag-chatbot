"""Faz 2: Async Queue Poller — Batch İş İşleyici.

Bu modül, FastAPI uygulaması başladığında lifespan hook'u tarafından
asyncio.create_task() ile arka planda süresiz çalıştırılır.

MVP Davranışı:
    - Her 5 saniyede PostgreSQL'deki PENDING batch_job satırlarını çeker.
    - Ollama üzerinden generate_ecommerce_description() çağırır.
    - Üretilen metni HTML'e çevirir (markdown kütüphanesi kullanılır).
    - Sonucu webhook_url'e httpx ile POST eder.
    - Sistem çöküp kalkarsa PENDING işler otomatik kaldığı yerden devam eder.
"""
from __future__ import annotations

import asyncio
import logging
import textwrap

import httpx
from sqlalchemy import select

from app.db import SessionLocal
from app.models import BatchJob, JobStatus

log = logging.getLogger("app.worker")

POLL_INTERVAL = 5  # saniye


def _to_html(text: str) -> str:
    """Markdown veya düz metni basit HTML'e dönüştür.

    Tam markdown kütüphanesi gerektirmeden MVP için yeterli:
    - **bold** → <strong>
    - * veya - ile başlayan satırlar → <ul><li>
    - Diğer satırlar → <p>
    """
    try:
        import markdown  # type: ignore
        return markdown.markdown(text)
    except ImportError:
        # markdown paketi yoksa basit fallback
        lines = text.strip().split("\n")
        html_parts: list[str] = []
        in_list = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if in_list:
                    html_parts.append("</ul>")
                    in_list = False
                continue
            if stripped.startswith(("* ", "- ", "• ")):
                if not in_list:
                    html_parts.append("<ul>")
                    in_list = True
                html_parts.append(f"<li>{stripped[2:]}</li>")
            else:
                if in_list:
                    html_parts.append("</ul>")
                    in_list = False
                html_parts.append(f"<p>{stripped}</p>")
        if in_list:
            html_parts.append("</ul>")
        return "\n".join(html_parts)


def _truncate_features(text: str, max_chars: int = 2000) -> str:
    """Özellikleri son tam cümleden keserek kırp (kelime ortasında kesme)."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    # Son nokta veya satır başında kes
    last_stop = max(truncated.rfind("."), truncated.rfind("\n"))
    return truncated[:last_stop + 1] if last_stop > 0 else truncated


async def _process_one_job(job: BatchJob, session) -> None:
    """Tek bir işi işle: Ollama çağır → HTML çevir → DB güncelle → webhook at."""
    from app.llm import generate_ecommerce_description  # circular import önlemi

    features = _truncate_features(job.product_features or "")
    prompt = f"Title: {job.product_title}\n\nFeatures:\n{features}"

    try:
        job.status = JobStatus.PROCESSING
        await session.commit()

        # Ollama çağrısı (llm.py'deki mevcut fonksiyonu kullanıyoruz)
        raw_text = await generate_ecommerce_description(prompt)

        # Markdown → HTML
        html_text = _to_html(raw_text)

        job.generated_text = html_text
        job.status = JobStatus.COMPLETED
        await session.commit()

        log.info("✅ Job %s (batch=%s) tamamlandı.", job.external_reference_id, job.batch_id)

        # Webhook tetikle
        payload = {
            "external_reference_id": job.external_reference_id,
            "batch_id": job.batch_id,
            "status": "COMPLETED",
            "generated_text": html_text,
        }
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(job.webhook_url, json=payload, timeout=15.0)
                log.info("📬 Webhook → %s  HTTP %s", job.webhook_url, resp.status_code)
            except Exception as wh_err:
                # Webhook hatası işin başarısını etkilemez
                log.warning("⚠️  Webhook POST başarısız: %s", wh_err)

    except Exception as exc:
        log.error("❌ Job %s başarısız: %s", job.external_reference_id, exc)
        job.status = JobStatus.FAILED
        job.error_message = str(exc)
        await session.commit()


async def queue_poller() -> None:
    """Sonsuz döngü: Her POLL_INTERVAL saniyede PostgreSQL'i kontrol et."""
    log.info("🚀 queue_poller başlatıldı (interval=%ds)", POLL_INTERVAL)
    while True:
        try:
            async with SessionLocal() as session:
                result = await session.execute(
                    select(BatchJob)
                    .where(BatchJob.status == JobStatus.PENDING)
                    .order_by(BatchJob.created_at)
                    .limit(10)  # MVP: aynı anda en fazla 10 iş çek
                )
                pending_jobs = result.scalars().all()

                if pending_jobs:
                    log.info("🔍 %d PENDING iş bulundu, işleniyor...", len(pending_jobs))

                for job in pending_jobs:
                    # Semaphore(1): Ollama'ya aynı anda tek istek (OOM koruması)
                    await _process_one_job(job, session)

        except Exception as poll_err:
            log.error("❗ queue_poller hatası: %s", poll_err)

        await asyncio.sleep(POLL_INTERVAL)
