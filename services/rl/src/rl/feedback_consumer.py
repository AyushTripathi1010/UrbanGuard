"""Reads rl-feedback events and accumulates them for offline training.

In Phase 5 this is a sink that writes feedback events as JSONL into
`data/processed/rl_feedback.jsonl`. The aggregation/replay phase (Phase 6)
turns this into training rollouts.
"""

from __future__ import annotations

import json
from pathlib import Path

import structlog
from aiokafka import AIOKafkaConsumer
from aiokafka.coordinator.assignors.sticky.sticky_assignor import StickyPartitionAssignor
from shared.settings import settings

from shared import RL_FEEDBACK, RLFeedback

log = structlog.get_logger("rl.feedback")

_SINK_PATH = Path("data/processed/rl_feedback.jsonl")


async def run() -> None:
    _SINK_PATH.parent.mkdir(parents=True, exist_ok=True)
    consumer = AIOKafkaConsumer(
        RL_FEEDBACK,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_group_rl,
        auto_offset_reset="latest",
        enable_auto_commit=False,
        session_timeout_ms=45_000,
        partition_assignment_strategy=(StickyPartitionAssignor,),
    )
    await consumer.start()
    log.info("rl.feedback_consumer.started", sink=str(_SINK_PATH))
    try:
        async for record in consumer:
            try:
                fb = RLFeedback.model_validate_json(record.value)
            except Exception as exc:
                log.warning("rl.feedback.parse_failed", error=str(exc))
                await consumer.commit()
                continue
            with _SINK_PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps(fb.model_dump(mode="json"), separators=(",", ":")) + "\n")
            await consumer.commit()
    finally:
        await consumer.stop()
