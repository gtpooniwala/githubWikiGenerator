"""LLM client wrapper for all OpenAI interactions.

Public API
----------
``chat_text(system, user, *, model, temperature)``
    Returns raw text from the model.

``chat_json(system, user, schema, *, model)``
    Enforces JSON-only output, strips code fences, validates against a
    Pydantic model, and returns the validated instance.

Both functions retry up to *MAX_RETRIES* times on transient errors
(rate limits, connection issues, server errors).
"""

from __future__ import annotations

import json
import re
import time
from typing import TypeVar, Type

import openai
from pydantic import BaseModel, ValidationError

import config

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MODEL: str = "gpt-5-mini"  # challenge.md says "gpt-5-mini"; map to valid id
MAX_RETRIES: int = 2
RETRY_DELAY: float = 1.0  # seconds between retries

# Regex: match ```json ... ``` or ``` ... ```
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)

T = TypeVar("T", bound=BaseModel)

# ---------------------------------------------------------------------------
# Module-level client (lazily initialised, replaceable in tests)
# ---------------------------------------------------------------------------

_client: openai.OpenAI | None = None


def _get_client() -> openai.OpenAI:
    global _client
    if _client is None:
        _client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
    return _client


def _set_client(client: openai.OpenAI | None) -> None:
    """Replace the module-level client (used in tests)."""
    global _client
    _client = client


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def strip_fences(text: str) -> str:
    """Remove markdown code fences from *text* and return the inner content.

    Handles::

        ```json
        { ... }
        ```

    and bare::

        ```
        { ... }
        ```

    If no fences are found the original text is returned stripped.
    """
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


_TRANSIENT = (
    openai.RateLimitError,
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.InternalServerError,
)


def _call_with_retries(fn: "callable", *args, **kwargs):
    """Call *fn* with retry on transient OpenAI errors."""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except _TRANSIENT as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * (attempt + 1))
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def chat_text(
    system: str,
    user: str,
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
) -> str:
    """Call the chat completions API and return the raw text response.

    Args:
        system:      System prompt.
        user:        User message.
        model:       Model identifier.
        temperature: Sampling temperature.

    Returns:
        The assistant's reply as a plain string.

    Raises:
        openai.OpenAIError: On non-transient API errors (after retries exhausted).
    """
    client = _get_client()

    def _call():
        response = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""

    return _call_with_retries(_call)


def chat_json(
    system: str,
    user: str,
    schema: Type[T],
    *,
    model: str = DEFAULT_MODEL,
) -> T:
    """Call the chat completions API and return a validated Pydantic instance.

    The model is instructed to return JSON only.  Code fences are stripped
    before parsing.  The result is validated against *schema*.

    Args:
        system: System prompt (will have JSON instruction appended).
        user:   User message.
        schema: Pydantic model class to validate against.
        model:  Model identifier.

    Returns:
        A validated instance of *schema*.

    Raises:
        ValueError:        If the response is not valid JSON or doesn't match
                           the schema.
        openai.OpenAIError: On non-transient API errors (after retries
                           exhausted).
    """
    json_system = (
        f"{system}\n\n"
        "Respond with valid JSON only. Do not include any explanation, "
        "prose, or markdown code fences outside the JSON object."
    )
    client = _get_client()

    def _call():
        response = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": json_system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""

    raw = _call_with_retries(_call)
    cleaned = strip_fences(raw)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM returned non-JSON content: {exc}\nRaw output: {raw[:500]}"
        ) from exc

    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        raise ValueError(
            f"LLM JSON does not match schema {schema.__name__}: {exc}\n"
            f"Raw output: {raw[:500]}"
        ) from exc
