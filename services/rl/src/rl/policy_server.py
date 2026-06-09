"""Serve PPO actions over HTTP. The ingest service queries this for per-zone sampling rates."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from shared.observability import install_prometheus
from stable_baselines3 import PPO

from rl.env import EnvConfig

_DEFAULT_CHECKPOINT = Path("data/checkpoints/ppo_zone_policy.zip")


class PredictRequest(BaseModel):
    recent_incident_counts: list[float] = Field(..., description="length = num_zones")
    hour_of_day_norm: float = Field(..., ge=0.0, le=1.0)
    last_clip_score_per_zone: list[float] = Field(..., description="length = num_zones")


class PredictResponse(BaseModel):
    sampling_rates: list[float]
    model_loaded: bool


_model: PPO | None = None
_cfg = EnvConfig()


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _model
    ckpt = _DEFAULT_CHECKPOINT
    if ckpt.exists():
        _model = PPO.load(str(ckpt))
    yield


app = FastAPI(title="urbanguard-rl-policy", lifespan=lifespan)
install_prometheus(app)


@app.get("/healthz")
async def healthz() -> dict[str, object]:
    return {"status": "ok", "model_loaded": _model is not None, "num_zones": _cfg.num_zones}


@app.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest) -> PredictResponse:
    Z = _cfg.num_zones
    if len(req.recent_incident_counts) != Z or len(req.last_clip_score_per_zone) != Z:
        raise HTTPException(400, f"expected {Z}-dim vectors for incident counts and clip scores")
    obs = np.concatenate(
        [
            np.asarray(req.recent_incident_counts, dtype=np.float32),
            np.asarray([req.hour_of_day_norm], dtype=np.float32),
            np.asarray(req.last_clip_score_per_zone, dtype=np.float32),
        ]
    )
    if _model is None:
        # Untrained fallback: uniform rate 1.0 for every zone.
        rates = np.ones(Z, dtype=np.float32).tolist()
    else:
        action, _ = _model.predict(obs, deterministic=True)
        rates = np.clip(action, 0.5, 4.0).astype(float).tolist()
    return PredictResponse(sampling_rates=rates, model_loaded=_model is not None)
