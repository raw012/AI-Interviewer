"""Minimal multi-provider text generation and transcription adapters."""

from __future__ import annotations

from pathlib import Path
from io import BytesIO
import wave

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
    "elevenlabs": {
        "name": "ElevenLabs",
        "chat": False,
        "transcription": False,
        "tts": True,
        "model": "eleven_flash_v2_5",
    },
}


COMPATIBLE_BASES = {
    "groq": "https://api.groq.com/openai/v1",
    "openai": "https://api.openai.com/v1",
    "qwen_cn": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "qwen_intl": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
}


def chat_completion(
    provider: str,
    api_key: str,
    prompt: str,
    system: str = "",
    json_mode: bool = False,
    max_tokens: int = 4096,
    temperature: float | None = None,
    effort: str | None = None,
) -> tuple[str, dict]:
    """Send one system + user exchange and return (text, token usage).

    The system prompt is sent first and kept stable across turns so providers
    with automatic prefix caching (OpenAI, Groq) and Anthropic's explicit
    cache_control can reuse it instead of billing it again in full.
    """
    provider = provider.lower()
    if provider in COMPATIBLE_BASES:
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        body: dict = {"model": PROVIDERS[provider]["model"], "messages": messages}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens and provider != "groq":
            body["max_tokens"] = max_tokens
        if effort and PROVIDERS[provider]["model"].startswith("openai/gpt-oss"):
            # Reasoning models spend hidden tokens; routine turns need little.
            body["reasoning_effort"] = effort
        response = httpx.post(
            f"{COMPATIBLE_BASES[provider]}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=body,
            timeout=90,
        )
        if json_mode and response.status_code == 400:
            # Some models reject JSON mode; retry once in plain mode.
            body.pop("response_format", None)
            response = httpx.post(
                f"{COMPATIBLE_BASES[provider]}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=body,
                timeout=90,
            )
        response.raise_for_status()
        payload = response.json()
        usage = payload.get("usage") or {}
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
        return payload["choices"][0]["message"]["content"].strip(), {
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "cached_tokens": int(cached or 0),
        }

    if provider == "anthropic":
        body = {
            "model": PROVIDERS[provider]["model"],
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = [
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ]
        if temperature is not None:
            body["temperature"] = temperature
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=body,
            timeout=90,
        )
        response.raise_for_status()
        payload = response.json()
        usage = payload.get("usage") or {}
        text = "".join(block.get("text", "") for block in payload.get("content", [])).strip()
        return text, {
            "prompt_tokens": int(usage.get("input_tokens") or 0)
            + int(usage.get("cache_read_input_tokens") or 0)
            + int(usage.get("cache_creation_input_tokens") or 0),
            "completion_tokens": int(usage.get("output_tokens") or 0),
            "cached_tokens": int(usage.get("cache_read_input_tokens") or 0),
        }

    if provider == "gemini":
        model = PROVIDERS[provider]["model"]
        body = {"contents": [{"parts": [{"text": prompt}]}]}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        config: dict = {}
        if json_mode:
            config["responseMimeType"] = "application/json"
        if temperature is not None:
            config["temperature"] = temperature
        if config:
            body["generationConfig"] = config
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": api_key, "content-type": "application/json"},
            json=body,
            timeout=90,
        )
        response.raise_for_status()
        payload = response.json()
        candidates = payload.get("candidates", [])
        if not candidates:
            raise ValueError("Gemini returned no response")
        usage = payload.get("usageMetadata") or {}
        text = "".join(
            part.get("text", "")
            for part in candidates[0].get("content", {}).get("parts", [])
        ).strip()
        return text, {
            "prompt_tokens": int(usage.get("promptTokenCount") or 0),
            "completion_tokens": int(usage.get("candidatesTokenCount") or 0),
            "cached_tokens": int(usage.get("cachedContentTokenCount") or 0),
        }

    raise ValueError(f"Unsupported LLM provider: {provider}")


def complete_text(provider: str, api_key: str, prompt: str) -> str:
    """Send one text prompt through the selected provider's API."""
    return chat_completion(provider, api_key, prompt)[0]


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
    if provider == "elevenlabs":
        _elevenlabs_speech("Ready.", api_key)
        return
    if not complete_text(provider, api_key, "Reply with exactly: connected"):
        raise ValueError("Provider returned an empty verification response")


def _groq_chunks(text: str) -> list[str]:
    """Keep each Orpheus request within Groq's 200-character input limit."""
    words = text.split()
    chunks: list[str] = []
    current = ""
    for word in words:
        if len(word) > 200:
            raise ValueError("Question contains a word too long for Groq speech")
        candidate = f"{current} {word}" if current else word
        if len(candidate) > 200:
            chunks.append(current)
            current = word
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _combine_wav(parts: list[bytes]) -> bytes:
    """Join Groq speech chunks without introducing lossy audio conversion."""
    if len(parts) == 1:
        return parts[0]
    output = BytesIO()
    expected = None
    with wave.open(output, "wb") as destination:
        for part in parts:
            with wave.open(BytesIO(part), "rb") as source:
                format_info = (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getcomptype())
                if expected is None:
                    expected = format_info
                    destination.setnchannels(format_info[0])
                    destination.setsampwidth(format_info[1])
                    destination.setframerate(format_info[2])
                elif format_info != expected:
                    raise ValueError("Groq returned incompatible audio chunks")
                destination.writeframes(source.readframes(source.getnframes()))
    return output.getvalue()


def _elevenlabs_speech(text: str, api_key: str) -> bytes:
    """Generate MP3 speech with the account's ElevenLabs Flash voice."""
    response = httpx.post(
        "https://api.elevenlabs.io/v1/text-to-speech/JBFqnCBsd6RMkjVDRZzb",
        headers={"xi-api-key": api_key},
        params={"output_format": "mp3_44100_128"},
        json={"text": text, "model_id": "eleven_flash_v2_5"},
        timeout=45,
    )
    response.raise_for_status()
    if not response.content:
        raise ValueError("ElevenLabs returned empty audio")
    return response.content


def synthesize_question(text: str, groq_key: str | None, elevenlabs_key: str | None) -> tuple[bytes, str, str]:
    """Use Groq English TTS, falling back to ElevenLabs on rate limits or outages."""
    if not text.strip() or len(text) > 1600:
        raise ValueError("Question is empty or too long for speech generation")
    if groq_key:
        try:
            parts = []
            for chunk in _groq_chunks(text):
                response = httpx.post(
                    "https://api.groq.com/openai/v1/audio/speech",
                    headers={"Authorization": f"Bearer {groq_key}"},
                    json={
                        "model": "canopylabs/orpheus-v1-english",
                        "voice": "troy",
                        "input": chunk,
                        "response_format": "wav",
                    },
                    timeout=45,
                )
                response.raise_for_status()
                parts.append(response.content)
            return _combine_wav(parts), "audio/wav", "groq"
        except (httpx.TimeoutException, httpx.RequestError, ValueError):
            if not elevenlabs_key:
                raise
        except httpx.HTTPStatusError as error:
            if error.response.status_code != 429 and error.response.status_code < 500:
                raise
            if not elevenlabs_key:
                raise

    if not elevenlabs_key:
        raise ValueError("Connect a Groq or ElevenLabs key to hear questions")
    return _elevenlabs_speech(text, elevenlabs_key), "audio/mpeg", "elevenlabs"


def verification_failure_message(provider: str, error: Exception) -> str:
    """Explain a failed connection without exposing the key or upstream response."""
    name = PROVIDERS[provider]["name"]
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        if status == 401:
            return f"{name} rejected this API key. Check that it is active and belongs to {name}."
        if status == 402:
            return f"{name} has no available credits for this request. Check the account's usage or billing plan."
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


GROQ_VOICES = {"autumn", "diana", "hannah", "austin", "daniel", "troy"}


def _groq_speech(text: str, api_key: str, voice: str) -> bytes:
    parts = []
    for chunk in _groq_chunks(text):
        response = httpx.post(
            "https://api.groq.com/openai/v1/audio/speech",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": "canopylabs/orpheus-v1-english", "voice": voice, "input": chunk, "response_format": "wav"},
            timeout=45,
        )
        response.raise_for_status()
        parts.append(response.content)
    return _combine_wav(parts)


def _elevenlabs_voice(text: str, api_key: str, voice_id: str) -> bytes:
    response = httpx.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={"xi-api-key": api_key},
        params={"output_format": "mp3_44100_128"},
        json={"text": text, "model_id": "eleven_flash_v2_5", "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.15}},
        timeout=45,
    )
    response.raise_for_status()
    if not response.content:
        raise ValueError("ElevenLabs returned empty audio")
    return response.content


def synthesize_voice(
    text: str,
    provider: str,
    voice: str,
    groq_key: str | None,
    elevenlabs_key: str | None,
    fallback_groq_voice: str = "hannah",
    fallback_eleven_voice: str = "EXAVITQu4vr4xnSDxMaL",
) -> tuple[bytes, str, str]:
    """Speak text in the chosen voice; fall back to the other provider on failure."""
    text = text.strip()
    if not text or len(text) > 2400:
        raise ValueError("Text is empty or too long for speech")
    attempts = []
    if provider == "elevenlabs" and elevenlabs_key:
        attempts.append(("elevenlabs", voice))
    if groq_key:
        attempts.append(("groq", voice if provider == "groq" and voice in GROQ_VOICES else fallback_groq_voice))
    if elevenlabs_key and not any(a[0] == "elevenlabs" for a in attempts):
        attempts.append(("elevenlabs", fallback_eleven_voice))
    last_error: Exception | None = None
    for name, chosen in attempts:
        try:
            if name == "groq":
                return _groq_speech(text, groq_key or "", chosen), "audio/wav", f"groq:{chosen}"
            return _elevenlabs_voice(text, elevenlabs_key or "", chosen), "audio/mpeg", f"elevenlabs:{chosen}"
        except Exception as error:  # try the next provider
            last_error = error
    raise ValueError("No voice provider available") from last_error
