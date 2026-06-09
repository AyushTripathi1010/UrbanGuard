"""SSE helper: bridge a Kafka topic into a server-sent-event stream."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from aiokafka import AIOKafkaConsumer
from aiokafka.coordinator.assignors.sticky.sticky_assignor import StickyPartitionAssignor
from shared.settings import settings

log = structlog.get_logger("gateway.sse")


@asynccontextmanager
async def topic_consumer(topic: str, group_id: str) -> AsyncIterator[AIOKafkaConsumer]:
    c = AIOKafkaConsumer(
        topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=group_id,
        auto_offset_reset="latest",
        enable_auto_commit=True,
        session_timeout_ms=45_000,
        partition_assignment_strategy=(StickyPartitionAssignor,),
    )
    await c.start()
    try:
        yield c
    finally:
        await c.stop()


async def stream_records(topic: str, group_id: str) -> AsyncIterator[str]:
    """Yield each record's value (utf-8 string) as it arrives."""
    async with topic_consumer(topic, group_id) as c:
        try:
            async for record in c:
                yield record.value.decode("utf-8")
        except asyncio.CancelledError:
            raise
