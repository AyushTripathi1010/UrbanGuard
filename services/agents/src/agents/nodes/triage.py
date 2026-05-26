"""Triage node — LLM call that maps an Alert to a severity tier + rationale."""

from __future__ import annotations

import structlog

from agents.llm_provider import LLMUnavailable, generate_json
from agents.state import IncidentState, TriageDecision

log = structlog.get_logger("agents.triage")


_TRIAGE_PROMPT = """You are a city emergency triage operator.
You receive a detection alert from an automated CCTV/dashcam pipeline.
Classify the incident severity as one of: none, low, medium, high, critical.

- critical: multi-vehicle collision, fire, pedestrian struck, obvious major injury
- high: single-vehicle collision with likely injury, vehicle overturned
- medium: significant near-miss, minor collision, traffic disruption likely
- low: minor near-miss with no apparent damage, suspicious but unclear
- none: clearly not an incident on review

Alert summary:
- clip label: {label}
- clip incident probability: {clip_score:.3f}
- resnet severity score: {severity:.3f}
- zone: {zone_id}
- camera: {camera_id}

`requires_dispatch` should be true for severity high or critical, false otherwise.
Be conservative — favour "medium" over "high" when uncertain.
"""


async def triage_node(state: IncidentState) -> IncidentState:
    prompt = _TRIAGE_PROMPT.format(
        label=state.alert.clip_label,
        clip_score=state.alert.clip_score,
        severity=state.alert.resnet_severity,
        zone_id=state.alert.zone_id,
        camera_id=state.alert.camera_id,
    )
    try:
        decision = await generate_json(prompt, TriageDecision)
    except LLMUnavailable as exc:
        log.warning("triage.llm_unavailable", error=str(exc))
        return state.model_copy(
            update={
                "triage": TriageDecision(),
                "errors": [*state.errors, f"triage llm unavailable: {exc}"],
            }
        )
    log.info(
        "triage.decision",
        severity=decision.severity.value,
        dispatch=decision.requires_dispatch,
    )
    return state.model_copy(update={"triage": decision})
