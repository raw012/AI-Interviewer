"""Shared request dependencies: authentication and provider key resolution."""

from __future__ import annotations

import os

from fastapi import Header, HTTPException

from providers import PROVIDERS
from storage import api_key_for_user, provider_settings, user_for_token

PLACEHOLDER_KEYS = {"paste_your_new_groq_api_key_here", "your_groq_api_key_here"}


def _environment_key(provider: str) -> str:
    key = os.getenv(f"{provider.upper()}_API_KEY", "").strip()
    return "" if not key or key in PLACEHOLDER_KEYS or key.startswith("your_") else key


# Prefer the user's saved key, then the server's fallback key.
def resolved_api_key(user_id: str, provider: str = "groq") -> str:
    key = api_key_for_user(user_id, provider) or _environment_key(provider)
    if not key:
        raise HTTPException(
            status_code=400,
            detail=f"Configure a {PROVIDERS[provider]['name']} API key in Settings",
        )
    return key


# Voice is optional; prefer the user's key, then a server key, and never expose either.
def optional_voice_key(user_id: str, provider: str) -> str | None:
    return api_key_for_user(user_id, provider) or _environment_key(provider) or None


def server_fallback_available(provider: str) -> bool:
    return bool(_environment_key(provider))


# Resolve the active provider and key for text or transcription.
def provider_runtime(user_id: str, capability: str) -> tuple[str, str]:
    settings = provider_settings(user_id)
    provider = settings[
        "transcription_provider" if capability == "transcription" else "llm_provider"
    ]
    if provider not in PROVIDERS or not PROVIDERS[provider].get(
        capability if capability == "transcription" else "chat"
    ):
        raise HTTPException(status_code=400, detail=f"Selected provider cannot perform {capability}")
    return provider, resolved_api_key(user_id, provider)


# Authenticate a bearer token on protected routes.
def current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Please sign in")
    user = user_for_token(authorization.removeprefix("Bearer ").strip())
    if not user:
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again")
    return user
