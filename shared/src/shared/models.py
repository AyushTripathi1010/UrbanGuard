from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SeverityTier(str, Enum):
    none = "none"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class GeoPoint(BaseModel):
    lat: float
    lon: float


class Frame(BaseModel):
    """One sampled JPEG frame from a simulated camera, carried on raw-frames."""

    model_config = ConfigDict(frozen=True)

    frame_id: str
    camera_id: str
    zone_id: str
    captured_at: datetime = Field(default_factory=_utcnow)
    width: int
    height: int
    jpeg_bytes_b64: str
    geo: GeoPoint | None = None
    source: str = "synthetic"


class Alert(BaseModel):
    """A detection event emitted by the detect service onto the alerts topic."""

    alert_id: str
    frame_id: str
    camera_id: str
    zone_id: str
    detected_at: datetime = Field(default_factory=_utcnow)
    clip_label: str
    clip_score: float
    resnet_severity: float
    bbox: tuple[float, float, float, float] | None = None
    geo: GeoPoint | None = None


class Incident(BaseModel):
    """Outcome of the agent pipeline; persisted to Postgres."""

    incident_id: str
    alert_id: str
    severity: SeverityTier
    triage_note: str
    route_target: str | None = None
    route_eta_seconds: int | None = None
    notified_channels: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)


class RLFeedback(BaseModel):
    """Reward signal published when an alert is verified true / false."""

    alert_id: str
    zone_id: str
    detected_early: bool
    was_false_alarm: bool
    was_missed: bool
    compute_frames_used: int
    emitted_at: datetime = Field(default_factory=_utcnow)
