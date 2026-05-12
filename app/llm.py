"""Thin wrappers around provider SDKs. NO LangChain.

Keep the surface tiny:
    - chat_completion(messages, model) -> (text, input_tokens, output_tokens)
    - embed(texts) -> list[list[float]]

If you find yourself needing more, push complexity into the caller, not here.
"""
from __future__ import annotations

import asyncio
from anthropic import AsyncAnthropic

from app.config import get_settings

settings = get_settings()

_anthropic_client: AsyncAnthropic | None = None
_sentence_model = None


def get_anthropic() -> AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        _anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _anthropic_client


def get_sentence_model():
    global _sentence_model
    if _sentence_model is None:
        from sentence_transformers import SentenceTransformer
        # İlk çağrıda model indirilecek ve RAM'e yüklenecek
        _sentence_model = SentenceTransformer(settings.default_embed_model)
    return _sentence_model


async def chat_completion(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 512,
) -> tuple[str, int, int]:
    """Return (text, input_tokens, output_tokens). Caller logs via app.logger."""
    client = get_anthropic()

    system_prompt = None
    anthropic_messages = []
    for m in messages:
        if m["role"] == "system":
            system_prompt = m["content"]
        else:
            anthropic_messages.append(m)

    kwargs = {
        "model": model or settings.default_chat_model,
        "messages": anthropic_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if system_prompt:
        kwargs["system"] = system_prompt

    resp = await client.messages.create(**kwargs)
    text = resp.content[0].text
    return text, resp.usage.input_tokens, resp.usage.output_tokens


async def embed(
    texts: list[str],
) -> list[list[float]]:
    """Return list of 1024-dim vectors using local SentenceTransformer.
    """
    model = get_sentence_model()

    def _do_embed():
        embeddings = model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

    resp = await asyncio.to_thread(_do_embed)
    return resp
