from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from shared.testing import requires_postgres


@pytest.fixture
def client():
    from gateway.main import app

    with TestClient(app) as c:
        yield c


def test_healthz(client) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_metrics_exposed(client) -> None:
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "http_requests_total" in r.text or "http_request_duration" in r.text


@requires_postgres
def test_alerts_endpoint_returns_list(client) -> None:
    r = client.get("/alerts")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_cameras_returns_empty_when_ingest_offline(client) -> None:
    # Ingest service is not running in the test env; the endpoint must
    # degrade gracefully instead of 500-ing.
    r = client.get("/cameras")
    assert r.status_code == 200
    assert r.json() == []
