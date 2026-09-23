"""The LLM provider layer (TRD §10.3; D-021: Google Gemini free tier).

`make_client` returns None when no key is configured, so everything above it runs offline by
design. A call that times out, is rate-limited (429) or fails on the server raises
`LlmUnavailableError` at once, and callers fall back to their offline path; a reply that is not the
JSON object asked for raises `LlmBadOutputError`, which callers treat as a refusal. `CachedClient`
stores every reply on disk keyed by a hash of (model, system prompt, prompt) and paces real calls,
so evaluation re-runs spend no quota. The key is read from the environment and never logged.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Protocol

from shiftmate.schema.config import LlmConfig


class LlmUnavailableError(Exception):
    """No answer from the provider (no key, timeout, 429, server error): use offline mode."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class LlmBadOutputError(Exception):
    """The provider answered, but not with the JSON object that was asked for."""


class LlmClient(Protocol):
    model: str

    def generate_json(self, system: str, prompt: str) -> dict[str, Any]: ...


def parse_json_object(text: str) -> dict[str, Any]:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("{") :] if "{" in t else t
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end <= start:
        raise LlmBadOutputError("no JSON object in the reply")
    try:
        value = json.loads(t[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LlmBadOutputError(f"invalid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise LlmBadOutputError("the reply is not a JSON object")
    return value


class GeminiClient:
    def __init__(self, api_key: str, model: str, cfg: LlmConfig) -> None:
        from google import genai
        from google.genai import types

        self.model = model
        self.cfg = cfg
        self._types = types
        self._client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=int(cfg.timeout_s * 1000))
        )

    def generate_json(self, system: str, prompt: str) -> dict[str, Any]:
        from google.genai import errors

        t = self._types
        try:
            reply = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=t.GenerateContentConfig(
                    system_instruction=system,
                    temperature=self.cfg.temperature,
                    max_output_tokens=self.cfg.max_output_tokens,
                    response_mime_type="application/json",
                    automatic_function_calling=t.AutomaticFunctionCallingConfig(disable=True),
                ),
            )
        except errors.ClientError as exc:
            code = getattr(exc, "code", None)
            raise LlmUnavailableError("rate_limit" if code == 429 else f"client_{code}") from None
        except errors.ServerError as exc:
            raise LlmUnavailableError(f"server_{getattr(exc, 'code', '')}") from None
        except Exception as exc:  # timeouts and network errors surface as httpx exceptions
            raise LlmUnavailableError(type(exc).__name__) from None
        return parse_json_object(reply.text or "")


class CachedClient:
    """Disk cache + pacing for evaluation runs (TRD §10.6)."""

    def __init__(self, inner: LlmClient | None, cache_dir: Path, min_interval_s: float) -> None:
        self.inner = inner
        self.model = inner.model if inner else "none"
        self.cache_dir = cache_dir
        self.min_interval_s = min_interval_s
        self._last = 0.0
        self.hits = 0
        self.calls = 0

    def _key(self, system: str, prompt: str) -> str:
        h = hashlib.sha256(f"{self.model}\n{system}\n{prompt}".encode()).hexdigest()
        return h[:32]

    def generate_json(self, system: str, prompt: str) -> dict[str, Any]:
        path = self.cache_dir / f"{self._key(system, prompt)}.json"
        if path.exists():
            self.hits += 1
            return json.loads(path.read_text(encoding="utf-8"))
        if self.inner is None:
            raise LlmUnavailableError("no_key")
        wait = self.min_interval_s - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        self.calls += 1
        value = self.inner.generate_json(system, prompt)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return value


def make_client(provider: str, api_key: str | None, model: str, cfg: LlmConfig) -> LlmClient | None:
    """The configured client, or None (offline by design) when there is no key."""
    if not api_key or provider != "gemini":
        return None
    return GeminiClient(api_key, model or cfg.default_model, cfg)
