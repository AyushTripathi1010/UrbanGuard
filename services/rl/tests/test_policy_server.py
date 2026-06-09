from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from rl.env import EnvConfig
from rl.policy_server import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_healthz_reports_no_model_when_checkpoint_absent(client) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "num_zones" in body


def test_predict_returns_uniform_when_no_model(client) -> None:
    cfg = EnvConfig()
    payload = {
        "recent_incident_counts": [0.0] * cfg.num_zones,
        "hour_of_day_norm": 0.5,
        "last_clip_score_per_zone": [0.0] * cfg.num_zones,
    }
    r = client.post("/predict", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert len(body["sampling_rates"]) == cfg.num_zones
    # Fallback returns all 1.0
    assert all(rate == 1.0 for rate in body["sampling_rates"])


def test_predict_rejects_wrong_dimensionality(client) -> None:
    cfg = EnvConfig()
    payload = {
        "recent_incident_counts": [0.0] * (cfg.num_zones - 1),
        "hour_of_day_norm": 0.5,
        "last_clip_score_per_zone": [0.0] * cfg.num_zones,
    }
    r = client.post("/predict", json=payload)
    assert r.status_code == 400
