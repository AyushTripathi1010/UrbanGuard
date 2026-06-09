"""Memory node — persists the resolved IncidentState into Postgres."""

from __future__ import annotations

import uuid

import structlog
from shared.settings import settings
from sqlalchemy import JSON, Boolean, Column, DateTime, Float, MetaData, String, Table
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.sql import insert

from agents.state import IncidentState

log = structlog.get_logger("agents.memory")

_metadata = MetaData()

incidents = Table(
    "incidents",
    _metadata,
    Column("incident_id", String, primary_key=True),
    Column("alert_id", String, nullable=False, index=True),
    Column("camera_id", String, nullable=False, index=True),
    Column("zone_id", String, nullable=False, index=True),
    Column("severity", String, nullable=False),
    Column("requires_dispatch", Boolean, nullable=False),
    Column("triage_rationale", String, nullable=False),
    Column("route_target_type", String, nullable=True),
    Column("route_target_name", String, nullable=True),
    Column("route_distance_m", Float, nullable=True),
    Column("route_eta_s", Float, nullable=True),
    Column("notified_channels", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("raw_state", JSON, nullable=False),
)


_engine: AsyncEngine | None = None


def _get_engine() -> AsyncEngine:
    # NullPool: every call opens + closes a connection. Safe across event loops
    # (important for pytest, which creates a fresh loop per async test) and the
    # per-alert throughput here is far below the cost ceiling that would justify
    # connection pooling. If you ever flip back to a pooled engine, be sure the
    # engine is loop-scoped, not module-scoped.
    global _engine
    if _engine is None:
        _engine = create_async_engine(settings.postgres_dsn, poolclass=NullPool)
    return _engine


async def dispose_engine() -> None:
    """Drop the cached engine. Used by tests; harmless in production."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


async def init_schema() -> None:
    eng = _get_engine()
    async with eng.begin() as conn:
        await conn.run_sync(_metadata.create_all)


async def memory_node(state: IncidentState) -> IncidentState:
    incident_id = uuid.uuid4().hex
    row = {
        "incident_id": incident_id,
        "alert_id": state.alert.alert_id,
        "camera_id": state.alert.camera_id,
        "zone_id": state.alert.zone_id,
        "severity": (state.triage.severity.value if state.triage else "none"),
        "requires_dispatch": bool(state.triage and state.triage.requires_dispatch),
        "triage_rationale": (state.triage.rationale if state.triage else ""),
        "route_target_type": (state.route.target_type if state.route else None),
        "route_target_name": (state.route.target_name if state.route else None),
        "route_distance_m": (state.route.distance_meters if state.route else None),
        "route_eta_s": (state.route.eta_seconds if state.route else None),
        "notified_channels": (state.notify.channels if state.notify else []),
        "created_at": state.received_at,
        "raw_state": state.model_dump(mode="json"),
    }
    eng = _get_engine()
    async with eng.begin() as conn:
        await conn.execute(insert(incidents).values(**row))
    log.info("memory.persisted", incident=incident_id, alert=state.alert.alert_id)
    return state.model_copy(update={"persisted_incident_id": incident_id})
