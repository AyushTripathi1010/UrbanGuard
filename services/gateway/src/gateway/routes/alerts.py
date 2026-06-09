"""Alert endpoints: recent list + live SSE stream."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse

from agents.nodes.memory import _get_engine, incidents
from gateway.sse import stream_records
from shared import ALERTS

router = APIRouter()


@router.get("/alerts")
async def recent_alerts(limit: int = 50) -> list[dict]:
    eng = _get_engine()
    async with eng.connect() as conn:
        result = await conn.execute(
            select(incidents).order_by(incidents.c.created_at.desc()).limit(limit)
        )
        rows = result.mappings().all()
    out = []
    for r in rows:
        out.append(
            {
                "incident_id": r["incident_id"],
                "alert_id": r["alert_id"],
                "camera_id": r["camera_id"],
                "zone_id": r["zone_id"],
                "severity": r["severity"],
                "route_target_name": r["route_target_name"],
                "route_eta_s": r["route_eta_s"],
                "created_at": r["created_at"].isoformat(),
            }
        )
    return out


@router.get("/alerts/stream")
async def alerts_stream():
    group = f"gateway-sse-{uuid.uuid4().hex[:8]}"

    async def event_generator():
        async for payload in stream_records(ALERTS, group_id=group):
            yield {"event": "alert", "data": payload}

    return EventSourceResponse(event_generator())
