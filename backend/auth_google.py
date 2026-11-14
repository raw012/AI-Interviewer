"""Verify Google Identity Services ID tokens without extra dependencies.

The frontend receives a signed JWT from Google's sign-in button. We check the
RS256 signature against Google's published keys, then the audience, issuer,
expiry and verified-email claims.
"""

from __future__ import annotations

import base64
import json
import os
import time

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
_cache: dict = {"keys": {}, "expires": 0.0}


def client_id() -> str:
    return os.getenv("GOOGLE_CLIENT_ID", "").strip()


def _b64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _keys() -> dict:
    if _cache["keys"] and _cache["expires"] > time.time():
        return _cache["keys"]
    response = httpx.get(JWKS_URL, timeout=10)
    response.raise_for_status()
    keys = {}
    for jwk in response.json().get("keys", []):
        if jwk.get("kty") == "RSA":
            numbers = rsa.RSAPublicNumbers(int.from_bytes(_b64(jwk["e"]), "big"), int.from_bytes(_b64(jwk["n"]), "big"))
            keys[jwk["kid"]] = numbers.public_key()
    max_age = 3600
    for part in response.headers.get("cache-control", "").split(","):
        if part.strip().startswith("max-age="):
            max_age = int(part.strip()[8:])
    _cache.update(keys=keys, expires=time.time() + max_age)
    return keys


def verify_id_token(token: str) -> dict:
    """Return verified claims (sub, email, name, picture) or raise ValueError."""
    audience = client_id()
    if not audience:
        raise ValueError("Google sign-in is not configured")
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        header = json.loads(_b64(header_b64))
        claims = json.loads(_b64(payload_b64))
    except Exception as exc:
        raise ValueError("Malformed Google credential") from exc
    if header.get("alg") != "RS256":
        raise ValueError("Unexpected token algorithm")
    key = _keys().get(header.get("kid"))
    if key is None:
        _cache["expires"] = 0  # keys may have rotated
        key = _keys().get(header.get("kid"))
    if key is None:
        raise ValueError("Unknown signing key")
    try:
        key.verify(_b64(signature_b64), f"{header_b64}.{payload_b64}".encode(), padding.PKCS1v15(), hashes.SHA256())
    except Exception as exc:
        raise ValueError("Invalid Google signature") from exc
    if claims.get("aud") != audience:
        raise ValueError("Credential was issued for another app")
    if claims.get("iss") not in ISSUERS:
        raise ValueError("Unexpected issuer")
    if float(claims.get("exp", 0)) < time.time() - 30:
        raise ValueError("Google credential expired")
    if not claims.get("email") or not claims.get("email_verified"):
        raise ValueError("Google account email is not verified")
    return claims
