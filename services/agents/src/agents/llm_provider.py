"""Thin LLM provider abstraction with Gemini primary, Groq fallback.

We keep this deliberately small — no LangChain LLM classes, no provider-specific
abstractions leaking into the agent code. The agent code calls `generate(prompt,
schema=...)` and either gets a parsed Pydantic model back or raises. Retries +
fallback are handled here.
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from typing import TypeVar

import structlog
from pydantic import BaseModel, ValidationError
from shared.observability import trace
from shared.settings import settings
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = structlog.get_logger("agents.llm_provider")

T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(Exception):
    """Raised when no LLM provider can satisfy the request."""


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def generate_json(self, prompt: str, schema: type[T]) -> T: ...


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        self._client = genai.GenerativeModel(model)

    async def generate_json(self, prompt: str, schema: type[T]) -> T:
        # Gemini's "JSON mode" — ask it to return strictly the JSON for the schema.
        body = f"{prompt}\n\nRespond with ONLY a JSON object matching this schema:\n{schema.model_json_schema()}"
        resp = await asyncio.to_thread(
            self._client.generate_content,
            body,
            generation_config={"response_mime_type": "application/json"},
        )
        text = (resp.text or "").strip()
        try:
            return schema.model_validate_json(text)
        except ValidationError:
            # Some Gemini responses wrap the JSON in ```json fences.
            cleaned = text.strip("`").removeprefix("json").strip()
            return schema.model_validate_json(cleaned)


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self, api_key: str, model: str) -> None:
        from groq import AsyncGroq

        self._client = AsyncGroq(api_key=api_key)
        self._model = model

    async def generate_json(self, prompt: str, schema: type[T]) -> T:
        body = f"{prompt}\n\nReturn ONLY a JSON object matching this schema:\n{schema.model_json_schema()}"
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": body}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        text = resp.choices[0].message.content or ""
        return schema.model_validate_json(text)


class StubProvider(LLMProvider):
    """Used when no API keys are configured. Returns the schema's first-default."""

    name = "stub"

    async def generate_json(self, prompt: str, schema: type[T]) -> T:
        # Walk the schema fields and produce a sane default. Works because every
        # agent schema in this project sets sensible defaults / Literals.
        return schema.model_validate({})


def build_chain() -> list[LLMProvider]:
    """Return the configured provider chain in order: primary → fallback → stub."""
    chain: list[LLMProvider] = []
    if settings.gemini_api_key:
        chain.append(GeminiProvider(settings.gemini_api_key, settings.gemini_model))
    if settings.groq_api_key:
        chain.append(GroqProvider(settings.groq_api_key, settings.groq_model))
    if not chain:
        chain.append(StubProvider())
    # Honour LLM_PRIMARY if both are configured.
    if len(chain) == 2 and settings.llm_primary == "groq":
        chain.reverse()
    return chain


async def generate_json(
    prompt: str, schema: type[T], providers: list[LLMProvider] | None = None
) -> T:
    providers = providers or build_chain()
    last_exc: Exception | None = None
    with trace(
        "llm.generate_json",
        input={"prompt_chars": len(prompt), "schema": schema.__name__},
        metadata={"providers": [p.name for p in providers]},
    ) as t:
        for provider in providers:
            try:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
                    retry=retry_if_exception_type(Exception),
                    reraise=True,
                ):
                    with attempt:
                        out = await provider.generate_json(prompt, schema)
                        log.info("llm.ok", provider=provider.name, schema=schema.__name__)
                        if t is not None:
                            try:
                                t.update(
                                    output=out.model_dump(mode="json"),
                                    metadata={"provider": provider.name},
                                )
                            except Exception:
                                pass
                        return out
            except (RetryError, Exception) as exc:
                log.warning("llm.failed", provider=provider.name, error=str(exc))
                last_exc = exc
                continue
        raise LLMUnavailable(f"no provider succeeded: {last_exc}")


def render_for_log(payload: dict) -> str:
    """Compact, line-safe JSON for log lines so structlog stays single-line."""
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
