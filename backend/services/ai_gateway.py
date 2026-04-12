"""AI Gateway: LLM routing with provider failover and rate limiting."""

import os
from datetime import datetime
from typing import Optional

import google.generativeai as genai
from groq import Groq
import redis.asyncio as redis
from fastapi import HTTPException, status


# LLM API keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Initialize LLM clients
genai.configure(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Redis connection (lazy initialization)
_redis_client: Optional[redis.Redis] = None


async def get_redis_client() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = await redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


async def check_and_increment_quota(user_id: str, plan: str) -> bool:
    """
    Check if user has quota remaining and increment the counter.
    - Pro users: always return True (unlimited)
    - Free users: check daily limit (10 requests), return True after incrementing
    - Raise HTTPException 429 if quota exceeded
    """
    if plan == "pro":
        return True

    redis_client = await get_redis_client()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    rate_limit_key = f"rate_limit:{user_id}:{today}"
    
    # Get current count
    current_count = await redis_client.get(rate_limit_key)
    current_count = int(current_count) if current_count else 0

    # Check limit
    if current_count >= 10:
        raise HTTPException(
            status_code=429,
            detail="Daily quota exceeded. Upgrade to Pro for unlimited access.",
        )

    # Increment count
    await redis_client.incr(rate_limit_key)
    # Set TTL to 24 hours if this is the first increment
    if current_count == 0:
        await redis_client.expire(rate_limit_key, 86400)

    return True


async def _call_gemini(prompt: str, system_prompt: str) -> str:
    """Call Gemini API (gemini-1.5-flash)."""
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini API not configured",
        )

    model = genai.GenerativeModel(model_name="gemini-1.5-flash", system_instruction=system_prompt)
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "rate" in error_msg.lower():
            raise ValueError("Rate limited")  # Will be caught to try fallback
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Gemini API error: {error_msg}",
        )


async def _call_groq(prompt: str, system_prompt: str) -> str:
    """Call Groq API (llama-3.1-8b-instant)."""
    if not GROQ_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Groq API not configured",
        )

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=1,  # Required by Groq
        )
        return response.choices[0].message.content
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "rate" in error_msg.lower():
            raise ValueError("Rate limited")  # Will be caught for next provider
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Groq API error: {error_msg}",
        )


async def call_llm(prompt: str, system_prompt: str, user_id: str, plan: str) -> str:
    """
    Call LLM with provider failover.
    1. Check quota first
    2. Try Gemini (primary) → Groq (fallback)
    3. Return first available response
    Raise 503 if all providers fail
    """
    # Check quota
    await check_and_increment_quota(user_id, plan)

    # Try providers in order: Gemini first, Groq fallback
    providers = [
        ("gemini", _call_gemini),
        ("groq", _call_groq),
    ]

    last_error = None
    for provider_name, provider_func in providers:
        try:
            response = await provider_func(prompt, system_prompt)
            return response
        except ValueError as e:
            # Rate limited, try next provider
            if "rate limited" in str(e).lower():
                last_error = e
                continue
            raise
        except HTTPException:
            raise

    # All providers failed or rate limited
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="All AI providers are currently unavailable. Please try again shortly.",
    )
