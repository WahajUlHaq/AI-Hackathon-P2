"""
Gemini API wrapper with 429 retry + model fallback.

Free tier limits (RPM):
  gemini-2.5-flash  →  5 RPM
  gemini-2.0-flash  → 15 RPM
  gemini-1.5-flash  → 15 RPM  (final fallback)

On 429: parse retry_delay from error, wait, then retry.
After 2 failed attempts on the primary model, switch to next model in chain.
"""
import asyncio
import re

from google import genai
from google.genai import types

# Model preference order — best first, most lenient quota last.
# Each model has its OWN daily quota bucket on the free tier.
_MODEL_CHAIN = [
    "gemini-2.5-flash-lite",   # primary
    "gemini-2.0-flash-lite",   # 30 RPM fallback
    "gemini-2.0-flash",        # 15 RPM fallback
    "gemini-1.5-flash",        # final fallback (1.5-flash-8b not in v1beta)
]


def _parse_retry_after(exc: Exception) -> float:
    """Extract retry delay seconds from 429 error message. Default 30s."""
    msg = str(exc)
    m = re.search(r"retry[_ ](?:in|after)[: ]+([0-9.]+)\s*s", msg, re.IGNORECASE)
    if m:
        return float(m.group(1)) + 1.0   # +1s buffer
    # Also check for retryDelay field like '28s'
    m2 = re.search(r"'retryDelay':\s*'([0-9.]+)s'", msg)
    if m2:
        return float(m2.group(1)) + 1.0
    return 30.0


def _is_daily_quota_exceeded(exc: Exception) -> bool:
    """Return True if the error is a daily (RPD) quota exhaustion — no point retrying."""
    msg = str(exc)
    return "PerDay" in msg or "free_tier_input_token_count" in msg or "RPD" in msg


async def generate_with_retry(
    client: genai.Client,
    contents,
    config: types.GenerateContentConfig,
    preferred_model: str = "gemini-2.5-flash-lite",
    max_retries: int = 1,
):
    """
    Call Gemini with automatic 429 backoff and model fallback.
    Returns the response object.
    Raises the last exception if all retries + fallbacks are exhausted.
    """
    # Build model list: preferred first, then rest of chain
    models = [preferred_model] + [m for m in _MODEL_CHAIN if m != preferred_model]

    last_exc: Exception | None = None
    for model in models:
        for attempt in range(max_retries):
            try:
                response = await client.aio.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
                return response  # success
            except Exception as exc:
                last_exc = exc
                err = str(exc)
                if "429" in err or "RESOURCE_EXHAUSTED" in err:
                    # Daily quota exhausted — no point waiting, skip to next model
                    if _is_daily_quota_exceeded(exc):
                        break
                    delay = _parse_retry_after(exc)
                    if attempt < max_retries - 1:
                        # Retry same model after waiting
                        await asyncio.sleep(delay)
                        continue
                    else:
                        # Exhausted retries on this model → try next model
                        break
                else:
                    # Non-rate-limit error — raise immediately
                    raise

    raise last_exc  # all models + retries failed
