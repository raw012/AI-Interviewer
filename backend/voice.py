"""Interviewer voice: resolves the persona's voice, synthesises, and caches audio on disk.

Cached clips are keyed by voice + text, so repeated lines (openings, previews,
replays) cost nothing. The cache is pruned to a fixed size."""

from __future__ import annotations

import hashlib
from pathlib import Path

from deps import optional_voice_key
from knowledge import PERSONAS, VOICES
from providers import synthesize_voice
from storage import DATA_DIR

CACHE_DIR = DATA_DIR / "tts_cache"
CACHE_LIMIT_BYTES = 300 * 1024 * 1024


def resolve_voice(persona_key: str, voice_pref: str) -> tuple[str, str]:
    """Return (provider, voice) for a preference like 'groq:hannah' or 'auto'."""
    if voice_pref and voice_pref not in ("auto", "browser") and ":" in voice_pref:
        provider, voice = voice_pref.split(":", 1)
        return provider, voice
    if voice_pref == "browser":
        return "browser", ""
    persona = PERSONAS.get(persona_key) or PERSONAS["maya"]
    return "groq", persona["voices"]["groq"]


def available_voices(user_id: str) -> list[dict]:
    groq = bool(optional_voice_key(user_id, "groq"))
    eleven = bool(optional_voice_key(user_id, "elevenlabs"))
    out = []
    for v in VOICES:
        ready = v["provider"] == "browser" or (v["provider"] == "groq" and groq) or (v["provider"] == "elevenlabs" and eleven)
        out.append({**v, "available": ready})
    return out


def _prune() -> None:
    files = sorted(CACHE_DIR.glob("*.bin"), key=lambda p: p.stat().st_atime)
    total = sum(p.stat().st_size for p in files)
    while files and total > CACHE_LIMIT_BYTES:
        victim = files.pop(0)
        total -= victim.stat().st_size
        victim.unlink(missing_ok=True)


def speak(user_id: str, text: str, persona_key: str, voice_pref: str) -> tuple[bytes, str, str]:
    provider, voice = resolve_voice(persona_key, voice_pref)
    if provider == "browser":
        raise ValueError("Browser voice selected")
    persona = PERSONAS.get(persona_key) or PERSONAS["maya"]
    key = hashlib.sha256(f"{provider}:{voice}:{text}".encode()).hexdigest()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{key}.bin"
    meta = CACHE_DIR / f"{key}.type"
    if path.exists() and meta.exists():
        path.touch()
        media_type, used = meta.read_text().split("|", 1)
        return path.read_bytes(), media_type, used
    audio, media_type, used = synthesize_voice(
        text,
        provider,
        voice,
        optional_voice_key(user_id, "groq"),
        optional_voice_key(user_id, "elevenlabs"),
        fallback_groq_voice=persona["voices"]["groq"],
        fallback_eleven_voice=persona["voices"]["elevenlabs"],
    )
    path.write_bytes(audio)
    meta.write_text(f"{media_type}|{used}")
    _prune()
    return audio, media_type, used
