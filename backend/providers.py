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
