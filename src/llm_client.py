"""LLM client for DER RegCheck RAG and evaluation.

Uses Google's official AI SDK for Gemini models.
Provides structured and text generation with rate limiting and retry logic.
"""
from __future__ import annotations

import os
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Any, TypeVar

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel


load_dotenv()


SchemaT = TypeVar("SchemaT", bound=BaseModel)


@dataclass(slots=True)
class RateLimiter:
    """
    Thread-safe rate limiter using a fixed-window approach.
    
    Enforces at most `max_calls` per `window_seconds` across all callers
    that share this instance.
    """

    max_calls: int
    window_seconds: float
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _calls: list[float] = field(default_factory=list, repr=False)

    def acquire(self) -> float:
        """
        Block until a call slot is available, then record the call.
        
        Returns the time spent waiting (in seconds).
        """
        with self._lock:
            now = time.perf_counter()
            window_start = now - self.window_seconds

            # Drop calls outside the current window
            self._calls = [t for t in self._calls if t > window_start]

            if len(self._calls) < self.max_calls:
                # Slot available immediately
                self._calls.append(now)
                return 0.0

            # Need to wait until the oldest call exits the window
            oldest = self._calls[0]
            wait_until = oldest + self.window_seconds
            wait_seconds = wait_until - now

        # Sleep outside the lock so other threads can proceed
        if wait_seconds > 0:
            time.sleep(wait_seconds)

        # Re-acquire and record after waiting
        with self._lock:
            now = time.perf_counter()
            window_start = now - self.window_seconds
            self._calls = [t for t in self._calls if t > window_start]
            self._calls.append(now)

        return max(0.0, wait_seconds)


def get_client() -> genai.Client:
    """Create a Google AI client."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is not set")
    return genai.Client(api_key=api_key)


def get_default_model() -> str:
    """Get default model from environment."""
    model = os.getenv("MODEL_ID", "gemini-3.5-flash-lite")
    return model


def _is_retryable_error(exc: Exception) -> bool:
    """Check if an error is retryable (rate limit, timeout, server error)."""
    message = str(exc).lower()
    retry_markers = [
        "429",
        "rate limit",
        "quota",
        "resource exhausted",
        "temporarily unavailable",
        "timeout",
        "timed out",
        "connection reset",
        "internal error",
        "server error",
        "503",
        "502",
        "504",
    ]
    return any(marker in message for marker in retry_markers)


def _compute_backoff(
    attempt: int,
    initial_wait: float = 8.0,
    max_wait: float = 60.0,
    jitter_ratio: float = 0.25,
) -> float:
    """Compute exponential backoff with jitter."""
    base = min(max_wait, initial_wait * (2 ** attempt))
    jitter = base * jitter_ratio * random.random()
    return base + jitter


def generate_structured_answer(
    *,
    instructions: str,
    user_prompt: str,
    output_type: type[SchemaT],
    model: str | None = None,
    client: genai.Client | None = None,
    max_retries: int = 6,
    initial_wait: float = 8.0,
    max_wait: float = 60.0,
    jitter_ratio: float = 0.25,
    verbose: bool = True,
    rate_limiter: RateLimiter | None = None,
) -> tuple[SchemaT, Any]:
    """
    Generate structured output using Gemini with schema validation.
    
    Uses Gemini's native response schema feature for structured generation.
    """
    resolved_client = client or get_client()
    resolved_model = model or get_default_model()

    # Optional rate limiting (primarily for batch tasks)
    if rate_limiter is not None:
        wait_seconds = rate_limiter.acquire()
        if verbose and wait_seconds > 0:
            print(f"[RATE LIMIT] Waited {wait_seconds:.2f}s before LLM call")

    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            response = resolved_client.models.generate_content(
                model=resolved_model,
                contents=f"{instructions}\n\n{user_prompt}",
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=output_type.model_json_schema(),
                ),
            )
            
            # Parse JSON response into Pydantic model
            import json
            text = response.text
            parsed_dict = json.loads(text)
            parsed = output_type(**parsed_dict)
            
            # Usage info (if available)
            usage = response.usage_metadata if hasattr(response, 'usage_metadata') else None
            return parsed, usage

        except Exception as exc:
            last_error = exc

            if not _is_retryable_error(exc) or attempt == max_retries - 1:
                raise

            wait_seconds = _compute_backoff(
                attempt=attempt,
                initial_wait=initial_wait,
                max_wait=max_wait,
                jitter_ratio=jitter_ratio,
            )

            if verbose:
                print(
                    f"[WARN] Structured generation failed "
                    f"(attempt {attempt + 1}/{max_retries}): {type(exc).__name__}: {exc}"
                )
                print(f"[INFO] Waiting {wait_seconds:.1f}s before retrying...")

            time.sleep(wait_seconds)

    if last_error is not None:
        raise last_error

    raise RuntimeError("Structured generation failed without a captured exception.")


def generate_text_answer(
    *,
    instructions: str,
    user_prompt: str,
    model: str | None = None,
    client: genai.Client | None = None,
    max_retries: int = 6,
    initial_wait: float = 8.0,
    max_wait: float = 60.0,
    jitter_ratio: float = 0.25,
    verbose: bool = True,
    rate_limiter: RateLimiter | None = None,
) -> tuple[str, Any]:
    """
    Generate text output using Gemini.
    
    Returns the generated text and usage information.
    """
    resolved_client = client or get_client()
    resolved_model = model or get_default_model()

    # Optional rate limiting
    if rate_limiter is not None:
        wait_seconds = rate_limiter.acquire()
        if verbose and wait_seconds > 0:
            print(f"[RATE LIMIT] Waited {wait_seconds:.2f}s before LLM call")

    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            response = resolved_client.models.generate_content(
                model=resolved_model,
                contents=f"{instructions}\n\n{user_prompt}",
            )
            text = response.text
            usage = response.usage_metadata if hasattr(response, 'usage_metadata') else None
            return text, usage

        except Exception as exc:
            last_error = exc

            if not _is_retryable_error(exc) or attempt == max_retries - 1:
                raise

            wait_seconds = _compute_backoff(
                attempt=attempt,
                initial_wait=initial_wait,
                max_wait=max_wait,
                jitter_ratio=jitter_ratio,
            )

            if verbose:
                print(
                    f"[WARN] Text generation failed "
                    f"(attempt {attempt + 1}/{max_retries}): {type(exc).__name__}: {exc}"
                )
                print(f"[INFO] Waiting {wait_seconds:.1f}s before retrying...")

            time.sleep(wait_seconds)

    if last_error is not None:
        raise last_error

    raise RuntimeError("Text generation failed without a captured exception.")