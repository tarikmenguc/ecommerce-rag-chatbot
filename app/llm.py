"""Thin wrappers around provider SDKs. NO LangChain.

Keep the surface tiny:
    - chat_completion(messages, model) -> (text, input_tokens, output_tokens)
    - embed(texts) -> list[list[float]]

If you find yourself needing more, push complexity into the caller, not here.
"""
from __future__ import annotations

import asyncio
from typing import Any
from google import genai

from app.config import get_settings

settings = get_settings()

_gemini_client: genai.Client | None = None
_sentence_model = None


def get_gemini() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        _gemini_client = genai.Client(api_key=settings.gemini_api_key)
    return _gemini_client


def get_sentence_model():
    global _sentence_model
    if _sentence_model is None:
        from sentence_transformers import SentenceTransformer
        # İlk çağrıda model indirilecek ve RAM'e yüklenecek
        _sentence_model = SentenceTransformer(settings.default_embed_model)
    return _sentence_model


class ModerationFlagged(Exception):
    pass

async def check_moderation(text: str) -> None:
    """Check text against OpenAI Moderation API. Raises ModerationFlagged if flagged."""
    if not settings.openai_api_key:
        # If no key is set, we skip moderation or raise error?
        # Let's just skip if not configured, or log a warning.
        return
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.openai.com/v1/moderations",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={"input": text}
        )
        resp.raise_for_status()
        data = resp.json()
        if data["results"][0]["flagged"]:
            raise ModerationFlagged("Input flagged by moderation API")


async def chat_completion(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 512,
    response_schema: Any = None,
) -> tuple[Any, int, int]:
    """Return (text_or_object, input_tokens, output_tokens). Caller logs via app.logger."""
    client = get_gemini()
    from google.genai import types

    system_prompt = None
    contents = []
    for m in messages:
        if m["role"] == "system":
            system_prompt = m["content"]
        else:
            role = "model" if m["role"] == "assistant" else "user"
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m["content"])]))

    config = types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=max_tokens,
    )
    if response_schema:
        config.response_mime_type = "application/json"
        config.response_schema = response_schema

    if system_prompt:
        config.system_instruction = system_prompt

    resp = await client.aio.models.generate_content(
        model=model or settings.default_chat_model,
        contents=contents,
        config=config,
    )
    
    text = resp.text
    in_tok = resp.usage_metadata.prompt_token_count if resp.usage_metadata else 0
    out_tok = resp.usage_metadata.candidates_token_count if resp.usage_metadata else 0
    return text, in_tok, out_tok


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
