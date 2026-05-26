from __future__ import annotations

import pytest

from shared import Alert, SeverityTier

from agents import llm_provider as lp
from agents.nodes.notify import notify_node
from agents.nodes.route import route_node
from agents.nodes.triage import triage_node
from agents.state import IncidentState, RouteDecision, TriageDecision


def _make_alert(severity: float = 0.7) -> Alert:
    return Alert(
        alert_id="a-test",
        frame_id="f-test",
        camera_id="cam-1",
        zone_id="z-1",
        clip_label="a road traffic accident, crash, or collision",
        clip_score=0.85,
        resnet_severity=severity,
    )


@pytest.mark.asyncio
async def test_triage_node_uses_llm_and_writes_decision(monkeypatch) -> None:
    async def fake_generate_json(prompt, schema, providers=None):  # noqa: ARG001
        return schema.model_validate({"severity": "high", "rationale": "fits", "requires_dispatch": True})

    monkeypatch.setattr("agents.nodes.triage.generate_json", fake_generate_json)
    state = IncidentState(alert=_make_alert())
    out = await triage_node(state)
    assert out.triage is not None
    assert out.triage.severity == SeverityTier.high
    assert out.triage.requires_dispatch is True


@pytest.mark.asyncio
async def test_triage_node_recovers_when_llm_unavailable(monkeypatch) -> None:
    async def boom(prompt, schema, providers=None):  # noqa: ARG001
        raise lp.LLMUnavailable("no provider")

    monkeypatch.setattr("agents.nodes.triage.generate_json", boom)
    state = IncidentState(alert=_make_alert())
    out = await triage_node(state)
    assert out.triage is not None  # default TriageDecision
    assert any("llm unavailable" in e for e in out.errors)


@pytest.mark.asyncio
async def test_route_node_skips_when_no_dispatch() -> None:
    state = IncidentState(
        alert=_make_alert(),
        triage=TriageDecision(severity=SeverityTier.low, requires_dispatch=False),
    )
    out = await route_node(state)
    assert out.route is not None
    assert out.route.target_type == "none"


@pytest.mark.asyncio
async def test_route_node_picks_hospital_for_critical(monkeypatch) -> None:
    # Force OSRM to be unreachable so we exercise the synthetic fallback.
    async def osrm_off(src, dst):  # noqa: ARG001
        return None

    monkeypatch.setattr("agents.nodes.route._osrm_route", osrm_off)
    state = IncidentState(
        alert=_make_alert(),
        triage=TriageDecision(severity=SeverityTier.critical, requires_dispatch=True),
    )
    out = await route_node(state)
    assert out.route is not None
    assert out.route.target_type == "hospital"
    assert out.route.distance_meters is not None
    assert out.route.eta_seconds is not None


@pytest.mark.asyncio
async def test_notify_node_skips_when_no_dispatch() -> None:
    state = IncidentState(
        alert=_make_alert(),
        triage=TriageDecision(severity=SeverityTier.low, requires_dispatch=False),
    )
    out = await notify_node(state)
    assert out.notify is not None
    assert out.notify.channels == []


@pytest.mark.asyncio
async def test_notify_node_records_log_channel_on_dispatch() -> None:
    state = IncidentState(
        alert=_make_alert(),
        triage=TriageDecision(severity=SeverityTier.high, requires_dispatch=True),
        route=RouteDecision(target_type="hospital", target_name="X", distance_meters=1200, eta_seconds=180),
    )
    out = await notify_node(state)
    assert out.notify is not None
    assert "log" in out.notify.channels
    assert out.notify.ok is True
