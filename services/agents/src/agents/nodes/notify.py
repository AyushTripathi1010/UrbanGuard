"""Notify node — structured-log dispatch + optional webhook (stub)."""

from __future__ import annotations

import structlog

from agents.state import IncidentState, NotifyOutcome

log = structlog.get_logger("agents.notify")


async def notify_node(state: IncidentState) -> IncidentState:
    if state.triage is None or not state.triage.requires_dispatch:
        return state.model_copy(
            update={"notify": NotifyOutcome(channels=[], ok=True, note="no dispatch required")}
        )

    channels = ["log"]
    log.info(
        "notify.dispatch",
        alert=state.alert.alert_id,
        severity=state.triage.severity.value,
        target=state.route.target_name if state.route else None,
        eta=state.route.eta_seconds if state.route else None,
    )
    return state.model_copy(
        update={"notify": NotifyOutcome(channels=channels, ok=True, note="dispatched to log")}
    )
