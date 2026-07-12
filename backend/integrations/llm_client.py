"""OpenRouter chat completion — OpenAI-compatible, cheap default model."""

from __future__ import annotations

import httpx
from django.conf import settings

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Cheap, follows JSON/instructions well enough for explain + copilot parse.
DEFAULT_MODEL = "openai/gpt-4o-mini"


def complete(system: str, user: str) -> str:
    key = (
        getattr(settings, "OPENROUTER_API_KEY", "")
        or getattr(settings, "GROQ_API_KEY", "")
        or ""
    )
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    model = getattr(settings, "OPENROUTER_MODEL", "") or DEFAULT_MODEL
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/hamdan-ishfaq/HAULRANK",
                "X-Title": "HaulRank",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"].strip()
