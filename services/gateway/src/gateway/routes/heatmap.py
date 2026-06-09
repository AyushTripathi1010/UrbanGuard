"""Heatmap endpoint: aggregate incident counts per zone for the last N hours."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import func, select

from agents.nodes.memory import _get_engine, incidents

router = APIRouter()


@router.get("/heatmap")
async def heatmap(hours: int = 24) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    eng = _get_engine()
    async with eng.connect() as conn:
        result = await conn.execute(
            select(
                incidents.c.zone_id,
                func.count().label("incident_count"),
                func.sum(
                    func.cast(
                        incidents.c.severity.in_(["high", "critical"]),
                        func.cast.type if False else None,  # placeholder, real cast below
                    )
                ).label("severe_count"),
            )
            .where(incidents.c.created_at >= since)
            .group_by(incidents.c.zone_id)
        )
        rows = result.mappings().all()
    return [
        {
            "zone_id": r["zone_id"],
            "incident_count": int(r["incident_count"]),
            "severe_count": int(r["severe_count"] or 0),
        }
        for r in rows
    ]
