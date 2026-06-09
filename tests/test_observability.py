"""Smoke tests for the shared observability helpers."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from shared.observability import install_prometheus, trace


def test_trace_no_keys_yields_none_and_doesnt_raise() -> None:
    with trace("noop", input={"x": 1}) as t:
        # No langfuse keys configured in tests → trace yields None
        assert t is None


def test_install_prometheus_exposes_metrics_endpoint() -> None:
    app = FastAPI()
    install_prometheus(app)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    with TestClient(app) as c:
        c.get("/ping")
        r = c.get("/metrics")
    assert r.status_code == 200
    assert ("http_requests_total" in r.text) or ("http_request_duration" in r.text)
