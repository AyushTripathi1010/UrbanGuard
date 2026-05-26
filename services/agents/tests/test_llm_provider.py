from __future__ import annotations

import pytest
from pydantic import BaseModel

from agents.llm_provider import (
    LLMProvider,
    LLMUnavailable,
    StubProvider,
    generate_json,
)


class _DemoSchema(BaseModel):
    severity: str = "medium"
    rationale: str = "default"


class _AlwaysFails(LLMProvider):
    name = "always_fails"

    async def generate_json(self, prompt: str, schema):  # noqa: ARG002
        raise RuntimeError("boom")


class _AlwaysSucceeds(LLMProvider):
    name = "always_succeeds"

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    async def generate_json(self, prompt: str, schema):
        return schema.model_validate(self._payload)


@pytest.mark.asyncio
async def test_stub_provider_returns_default_schema() -> None:
    out = await StubProvider().generate_json("x", _DemoSchema)
    assert out.severity == "medium"
    assert out.rationale == "default"


@pytest.mark.asyncio
async def test_generate_json_falls_back_to_second_provider() -> None:
    chain = [_AlwaysFails(), _AlwaysSucceeds({"severity": "high", "rationale": "ok"})]
    out = await generate_json("x", _DemoSchema, providers=chain)
    assert out.severity == "high"


@pytest.mark.asyncio
async def test_generate_json_raises_when_all_fail() -> None:
    chain = [_AlwaysFails(), _AlwaysFails()]
    with pytest.raises(LLMUnavailable):
        await generate_json("x", _DemoSchema, providers=chain)
