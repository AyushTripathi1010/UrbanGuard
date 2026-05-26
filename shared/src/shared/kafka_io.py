"""Helpers wrapping aiokafka with our Pydantic-typed payloads."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TypeVar

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.coordinator.assignors.sticky.sticky_assignor import StickyPartitionAssignor
from pydantic import BaseModel

from shared.settings import settings

T = TypeVar("T", bound=BaseModel)


@asynccontextmanager
async def producer() -> AsyncIterator[AIOKafkaProducer]:
    p = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        enable_idempotence=True,
        acks="all",
        linger_ms=10,
        compression_type="lz4",
    )
    await p.start()
    try:
        yield p
    finally:
        await p.stop()


async def send_model(p: AIOKafkaProducer, topic: str, msg: BaseModel, key: str | None = None) -> None:
    """Serialize a Pydantic model as JSON bytes and send."""
    payload = msg.model_dump_json().encode("utf-8")
    k = key.encode("utf-8") if key is not None else None
    await p.send_and_wait(topic, value=payload, key=k)


@asynccontextmanager
async def consumer(
    *topics: str,
    group_id: str,
    auto_offset_reset: str = "earliest",
) -> AsyncIterator[AIOKafkaConsumer]:
    c = AIOKafkaConsumer(
        *topics,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=group_id,
        auto_offset_reset=auto_offset_reset,
        enable_auto_commit=False,
        session_timeout_ms=45_000,
        max_poll_interval_ms=300_000,
        partition_assignment_strategy=(StickyPartitionAssignor,),
    )
    await c.start()
    try:
        yield c
    finally:
        await c.stop()


async def consume_model(c: AIOKafkaConsumer, model: type[T]) -> AsyncIterator[T]:
    """Iterate parsed messages of a given Pydantic model type."""
    async for record in c:
        yield model.model_validate_json(record.value)
