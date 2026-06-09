"""IncidentState — the typed payload that flows through the LangGraph."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from shared import Alert, GeoPoint, SeverityTier


def _utcnow() -> datetime:
    return datetime.now(UTC)


class TriageDecision(BaseModel):
    severity: SeverityTier = SeverityTier.medium
    rationale: str = "no rationale provided"
    requires_dispatch: bool = True


class RouteDecision(BaseModel):
    target_type: Literal["hospital", "police", "none"] = "none"
    target_name: str | None = None
    target_geo: GeoPoint | None = None
    distance_meters: float | None = None
    eta_seconds: int | None = None


class NotifyOutcome(BaseModel):
    channels: list[str] = Field(default_factory=list)
    ok: bool = True
    note: str | None = None


class IncidentState(BaseModel):
    """The single source of truth flowing through the graph."""

    alert: Alert
    received_at: datetime = Field(default_factory=_utcnow)
    triage: TriageDecision | None = None
    route: RouteDecision | None = None
    notify: NotifyOutcome | None = None
    persisted_incident_id: str | None = None
    errors: list[str] = Field(default_factory=list)
