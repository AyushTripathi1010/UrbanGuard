from __future__ import annotations

import pytest

from shared import Alert, SeverityTier
from shared.testing import requires_postgres

from agents.graph import build_graph
from agents.nodes.memory import init_schema
from agents.state import IncidentState


def _make_alert() -> Alert:
    return Alert(
        alert_id=f"a-test-{id(object())}",
        frame_id="f-test",
        camera_id="cam-1",
        zone_id="z-1",
        clip_label="a road traffic accident, crash, or collision",
        clip_score=0.92,
        resnet_severity=0.81,
    )


def test_graph_compiles_with_four_nodes() -> None:
    g = build_graph()
    # Topology assertion: all nodes present and reachable from START.
    nodes = set(g.get_graph().nodes)
    # LangGraph adds synthetic __start__ / __end__ nodes; subtract them.
    real = {n for n in nodes if not n.startswith("__")}
    assert real == {"triage", "route", "notify", "memory"}


@pytest.mark.asyncio
@requires_postgres
async def test_graph_runs_end_to_end_against_real_postgres(monkeypatch) -> None:
    # Mock the LLM call so the test doesn't need API keys.
    async def fake_generate_json(prompt, schema, providers=None):  # noqa: ARG001
        return schema.model_validate({"severity": "high", "rationale": "ok", "requires_dispatch": True})

    monkeypatch.setattr("agents.nodes.triage.generate_json", fake_generate_json)

    # OSRM isn't reachable in dev — force the synthetic fallback.
    async def osrm_off(src, dst):  # noqa: ARG001
        return None

    monkeypatch.setattr("agents.nodes.route._osrm_route", osrm_off)

    await init_schema()
    g = build_graph()
    state = IncidentState(alert=_make_alert())
    final = await g.ainvoke(state)
    assert final["persisted_incident_id"] is not None
    assert final["triage"].severity == SeverityTier.high
    assert final["route"].target_type == "hospital"
    assert "log" in final["notify"].channels
