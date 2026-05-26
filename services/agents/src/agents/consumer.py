"""alerts consumer: pull Alert events, run the LangGraph, persist outcome."""

from __future__ import annotations

import structlog
from aiokafka import AIOKafkaConsumer
from aiokafka.coordinator.assignors.sticky.sticky_assignor import StickyPartitionAssignor

from shared import ALERTS, Alert
from shared.settings import settings

from agents.graph import build_graph
from agents.nodes.memory import init_schema
from agents.state import IncidentState

log = structlog.get_logger("agents.consumer")


async def run() -> None:
    await init_schema()
    graph = build_graph()

    consumer = AIOKafkaConsumer(
        ALERTS,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_group_agents,
        auto_offset_reset="latest",
        enable_auto_commit=False,
        session_timeout_ms=45_000,
        partition_assignment_strategy=(StickyPartitionAssignor,),
    )
    await consumer.start()
    log.info("agents.started", group=settings.kafka_group_agents)
    try:
        async for record in consumer:
            try:
                alert = Alert.model_validate_json(record.value)
            except Exception as exc:  # noqa: BLE001
                log.warning("alert.parse_failed", error=str(exc))
                await consumer.commit()
                continue

            state = IncidentState(alert=alert)
            try:
                final = await graph.ainvoke(state)
                log.info(
                    "graph.complete",
                    alert=alert.alert_id,
                    severity=(final.get("triage") or {}).get("severity"),
                    incident=final.get("persisted_incident_id"),
                )
            except Exception as exc:  # noqa: BLE001
                log.error("graph.failed", alert=alert.alert_id, error=str(exc))
            finally:
                await consumer.commit()
    finally:
        await consumer.stop()
