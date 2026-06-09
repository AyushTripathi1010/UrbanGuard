"""Route node — deterministic OSRM lookup with a graceful synthetic fallback.

OSRM in `docker-compose` is enabled in Phase 9 (it needs an OSM extract). Until
then, we use a small synthetic registry of hospitals + police stations near a
default city centre so the rest of the pipeline can be exercised end-to-end.
"""

from __future__ import annotations

import math

import httpx
import structlog
from shared.settings import settings

from agents.state import IncidentState, RouteDecision
from shared import GeoPoint

log = structlog.get_logger("agents.route")


# Pune (Maharashtra) coordinates — placeholder city centre.
_DEFAULT_CITY_CENTRE = GeoPoint(lat=18.5204, lon=73.8567)

_FALLBACK_REGISTRY = [
    ("hospital", "Sahyadri Hospital Deccan", GeoPoint(lat=18.5181, lon=73.8417)),
    ("hospital", "Ruby Hall Clinic", GeoPoint(lat=18.5320, lon=73.8780)),
    ("hospital", "Jehangir Hospital", GeoPoint(lat=18.5288, lon=73.8717)),
    ("police", "Deccan Police Station", GeoPoint(lat=18.5165, lon=73.8418)),
    ("police", "Koregaon Park Police Station", GeoPoint(lat=18.5362, lon=73.8930)),
    ("police", "Shivajinagar Police Station", GeoPoint(lat=18.5293, lon=73.8439)),
]


def _haversine_metres(a: GeoPoint, b: GeoPoint) -> float:
    r = 6_371_000.0
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlat = lat2 - lat1
    dlon = math.radians(b.lon - a.lon)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _pick_target_kind(state: IncidentState) -> str | None:
    if state.triage is None or not state.triage.requires_dispatch:
        return None
    severity = state.triage.severity.value
    if severity in {"critical", "high"}:
        return "hospital"
    if severity == "medium":
        return "police"
    return None


async def _osrm_route(src: GeoPoint, dst: GeoPoint) -> tuple[float, int] | None:
    url = f"{settings.osrm_base_url.rstrip('/')}/route/v1/driving/{src.lon},{src.lat};{dst.lon},{dst.lat}"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(url, params={"overview": "false"})
        if r.status_code != 200:
            return None
        body = r.json()
        leg = body["routes"][0]
        return float(leg["distance"]), int(leg["duration"])
    except Exception as exc:
        log.debug("osrm.unreachable", error=str(exc))
        return None


async def route_node(state: IncidentState) -> IncidentState:
    kind = _pick_target_kind(state)
    if kind is None:
        return state.model_copy(update={"route": RouteDecision(target_type="none")})

    origin = state.alert.geo or _DEFAULT_CITY_CENTRE
    candidates = [(t, n, g) for t, n, g in _FALLBACK_REGISTRY if t == kind]
    if not candidates:
        return state.model_copy(update={"route": RouteDecision(target_type="none")})

    # Cheap nearest-by-haversine pre-filter then a single OSRM call.
    candidates.sort(key=lambda c: _haversine_metres(origin, c[2]))
    target_type, target_name, target_geo = candidates[0]

    osrm = await _osrm_route(origin, target_geo)
    if osrm is not None:
        distance, eta = osrm
        decision = RouteDecision(
            target_type=target_type,
            target_name=target_name,
            target_geo=target_geo,
            distance_meters=distance,
            eta_seconds=eta,
        )
    else:
        distance = _haversine_metres(origin, target_geo)
        eta = int(distance / 8.33)  # ~30 km/h average city speed
        decision = RouteDecision(
            target_type=target_type,
            target_name=target_name,
            target_geo=target_geo,
            distance_meters=distance,
            eta_seconds=eta,
        )

    log.info(
        "route.decided",
        target=target_name,
        kind=target_type,
        meters=int(decision.distance_meters or 0),
        eta=decision.eta_seconds,
    )
    return state.model_copy(update={"route": decision})
