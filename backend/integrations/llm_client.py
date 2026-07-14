"""OpenRouter chat completion — OpenAI-compatible, cheap default model."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
from django.conf import settings

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-4o-mini"


def _api_key() -> str:
    return (
        getattr(settings, "OPENROUTER_API_KEY", "")
        or getattr(settings, "GROQ_API_KEY", "")
        or ""
    )


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/hamdan-ishfaq/HAULRANK",
        "X-Title": "HaulRank",
    }


def complete(system: str, user: str) -> str:
    key = _api_key()
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
    with httpx.Client(timeout=12.0) as client:
        resp = client.post(OPENROUTER_URL, headers=_headers(), json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def complete_with_tools(
    system: str,
    user: str,
    tools: list[dict[str, Any]],
    execute_tool: Callable[[str, dict[str, Any]], Any],
    *,
    max_rounds: int = 3,
) -> tuple[str, list[str], list[dict[str, Any]]]:
    """OpenAI-compatible tool loop (no LangGraph). Returns narration, tools_called, results."""
    key = _api_key()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    model = getattr(settings, "OPENROUTER_MODEL", "") or DEFAULT_MODEL
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    tools_called: list[str] = []
    tool_results: list[dict[str, Any]] = []

    with httpx.Client(timeout=20.0) as client:
        for _ in range(max_rounds):
            payload = {
                "model": model,
                "temperature": 0.2,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
            }
            resp = client.post(OPENROUTER_URL, headers=_headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()
            msg = data["choices"][0]["message"]
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                return (msg.get("content") or "").strip(), tools_called, tool_results

            # Persist assistant turn with tool_calls for the next request
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.get("content") or "",
                    "tool_calls": tool_calls,
                }
            )
            for tc in tool_calls:
                fn = tc.get("function") or {}
                name = fn.get("name") or ""
                raw_args = fn.get("arguments") or "{}"
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                except json.JSONDecodeError:
                    args = {}
                if not isinstance(args, dict):
                    args = {}
                tools_called.append(name)
                result = execute_tool(name, args)
                tool_results.append({"name": name, "result": result})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.get("id") or name,
                        "content": json.dumps(result),
                    }
                )

    return "", tools_called, tool_results
