"""Groq chat completion — thin httpx wrapper."""

from __future__ import annotations

import httpx
from django.conf import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"


def complete(system: str, user: str) -> str:
    key = getattr(settings, "GROQ_API_KEY", "") or ""
    if not key:
        raise RuntimeError("GROQ_API_KEY not set")

    payload = {
        "model": MODEL,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"].strip()
