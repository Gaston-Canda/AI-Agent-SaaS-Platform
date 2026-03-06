"""Reusable OpenAI client wrapper."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    """Create and cache OpenAI client."""
    global _client

    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not configured")

    if _client is None:
        try:
            from openai import OpenAI
        except Exception as exc:
            raise RuntimeError("openai SDK not installed") from exc

        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def generate_response(prompt: str) -> str:
    """
    Generate text response using OpenAI chat completions.

    Raises RuntimeError on configuration or provider failures.
    """
    prompt = prompt.strip()
    if not prompt:
        return ""

    client = _get_client()

    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )

        content: Optional[str] = response.choices[0].message.content
        if not content:
            return ""
        return content.strip()
    except Exception as exc:
        logger.error("OpenAI generation failed: %s", str(exc))
        raise RuntimeError("OpenAI request failed") from exc


@dataclass
class OpenAICompletionResult:
    """Normalized completion payload for usage tracking."""
    response: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


def generate_response_with_usage(prompt: str) -> OpenAICompletionResult:
    """Generate text response including token usage."""
    prompt = prompt.strip()
    if not prompt:
        return OpenAICompletionResult(response="", prompt_tokens=0, completion_tokens=0, total_tokens=0)

    client = _get_client()

    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        content: Optional[str] = response.choices[0].message.content
        usage = response.usage
        return OpenAICompletionResult(
            response=(content or "").strip(),
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            total_tokens=getattr(usage, "total_tokens", 0) or 0,
        )
    except Exception as exc:
        logger.error("OpenAI generation with usage failed: %s", str(exc))
        raise RuntimeError("OpenAI request failed") from exc


def generate_embedding(text: str, model: str = "text-embedding-3-small") -> list[float]:
    """Generate embedding vector for semantic memory."""
    payload = text.strip()
    if not payload:
        return []

    client = _get_client()
    try:
        response = client.embeddings.create(model=model, input=payload)
        return list(response.data[0].embedding or [])
    except Exception as exc:
        logger.error("OpenAI embedding failed: %s", str(exc))
        raise RuntimeError("OpenAI embedding request failed") from exc
