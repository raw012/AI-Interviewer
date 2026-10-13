"""Minimal multi-provider text generation and transcription adapters."""

from __future__ import annotations

from pathlib import Path

import httpx


PROVIDERS = {
    "groq": {
        "name": "Groq",
        "chat": True,
        "transcription": True,
        "model": "openai/gpt-oss-120b",
    },
    "openai": {
        "name": "OpenAI",
        "chat": True,
        "transcription": True,
        "model": "gpt-4o-mini",
    },
    "anthropic": {
        "name": "Anthropic",
        "chat": True,
        "transcription": False,
        "model": "claude-haiku-4-5-20251001",
    },
    "gemini": {
        "name": "Google Gemini",
        "chat": True,
        "transcription": False,
        "model": "gemini-2.5-flash",
    },
    "qwen_cn": {
        "name": "Qwen (China)",
        "chat": True,
        "transcription": False,
        "model": "qwen-plus",
    },
    "qwen_intl": {
        "name": "Qwen (International)",
        "chat": True,
        "transcription": False,
        "model": "qwen-plus",
    },
}


def complete_text(provider: str, api_key: str, prompt: str) -> str:
    """Send one text prompt through the selected provider's API."""
    provider = provider.lower()
    compatible_bases = {
        "groq": "https://api.groq.com/openai/v1",
        "openai": "https://api.openai.com/v1",
        "qwen_cn": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "qwen_intl": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    }
    if provider in compatible_bases:
        base = compatible_bases[provider]
        response = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": PROVIDERS[provider]["model"],
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=90,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    if provider == "anthropic":
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": PROVIDERS[provider]["model"],
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=90,
        )
        response.raise_for_status()
        return "".join(block.get("text", "") for block in response.json().get("content", [])).strip()

    if provider == "gemini":
        model = PROVIDERS[provider]["model"]
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": api_key, "content-type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=90,
        )
        response.raise_for_status()
        candidates = response.json().get("candidates", [])
        if not candidates:
            raise ValueError("Gemini returned no response")
        return "".join(
            part.get("text", "")
            for part in candidates[0].get("content", {}).get("parts", [])
        ).strip()

    raise ValueError(f"Unsupported LLM provider: {provider}")


def transcribe_file(provider: str, api_key: str, audio_path: str) -> str:
    """Transcribe an audio file with Groq or OpenAI."""
    if provider not in {"groq", "openai"}:
        raise ValueError(f"{PROVIDERS.get(provider, {}).get('name', provider)} does not support transcription")
    base = "https://api.groq.com/openai/v1" if provider == "groq" else "https://api.openai.com/v1"
    model = "whisper-large-v3" if provider == "groq" else "whisper-1"
    path = Path(audio_path)
    with path.open("rb") as audio:
        response = httpx.post(
            f"{base}/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            data={"model": model},
            files={"file": (path.name, audio)},
            timeout=180,
        )
    response.raise_for_status()
    return response.json()["text"].strip()


def test_provider(provider: str, api_key: str) -> None:
    """Make a lightweight real request to validate a provider key."""
    if not complete_text(provider, api_key, "Reply with exactly: connected"):
        raise ValueError("Provider returned an empty verification response")


def verification_failure_message(provider: str, error: Exception) -> str:
    """Explain a failed connection without exposing the key or upstream response."""
    name = PROVIDERS[provider]["name"]
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        if status == 401:
            return f"{name} rejected this API key. Check that it is active and belongs to {name}."
        if status == 403:
            return f"{name} denied access. Check this project's model permissions."
        if status == 429:
            return f"{name} is rate-limiting requests. Try again later."
        if status in {400, 404}:
            return f"{name} rejected the configured model or request (HTTP {status}). Contact support if this persists."
        if status >= 500:
            return f"{name} is temporarily unavailable. Try again later."
        return f"{name} could not verify the connection (HTTP {status})."
    if isinstance(error, (httpx.TimeoutException, httpx.RequestError)):
        return f"The server could not reach {name}. Try again later."
    return f"{name} returned an invalid verification response. Try again later."
