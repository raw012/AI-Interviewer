"""One gateway for model calls: provider resolution, JSON parsing, accounting.

Every studio prompt goes through `ask_json`, which records prompt, completion
and cached-token counts per user and session so cost per interview is visible.
"""

from __future__ import annotations

import json
import re

from deps import provider_runtime
from providers import chat_completion
from studio_store import log_usage


class ModelError(RuntimeError):
    """The model call failed or returned something unusable."""


def ask(
    user_id: str,
    purpose: str,
    prompt: str,
    system: str = "",
    session_id: str = "",
    json_mode: bool = False,
    effort: str | None = "low",
    max_tokens: int = 2048,
    temperature: float | None = None,
) -> str:
    provider, api_key = provider_runtime(user_id, "llm")
    try:
        text, usage = chat_completion(
            provider,
            api_key,
            prompt,
            system=system,
            json_mode=json_mode,
            max_tokens=max_tokens,
            temperature=temperature,
            effort=effort,
        )
    except Exception as exc:  # network, quota, provider errors
        raise ModelError(str(exc)) from exc
    try:
        log_usage(user_id, session_id, purpose, provider, usage)
    except Exception:
        pass  # accounting must never break an interview
    return text


def ask_json(
    user_id: str,
    purpose: str,
    prompt: str,
    system: str = "",
    session_id: str = "",
    effort: str | None = "low",
    max_tokens: int = 2048,
    temperature: float | None = None,
) -> dict:
    text = ask(
        user_id,
        purpose,
        prompt,
        system=system,
        session_id=session_id,
        json_mode=True,
        effort=effort,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    parsed = parse_json(text)
    if parsed is None:
        raise ModelError(f"{purpose}: model did not return valid JSON")
    return parsed


def parse_json(text: str) -> dict | None:
    """Parse a JSON object, tolerating code fences or prose around it."""
    if not text:
        return None
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        value = json.loads(cleaned[start : end + 1])
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        return None


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 characters per token) for context budgeting."""
    return max(1, len(text) // 4)


def clip(text: str, max_chars: int) -> str:
    """Trim long text at a word boundary, marking the cut."""
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut + " …"
