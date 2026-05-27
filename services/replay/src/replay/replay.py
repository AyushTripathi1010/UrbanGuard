"""Rewind a consumer group to a given timestamp so the detect or agents service
can re-process a recent window of `raw-frames` or `alerts`. Useful for offline
debugging or for re-training the detection thresholds against past data.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from aiokafka import AIOKafkaConsumer, TopicPartition

from shared.settings import settings

log = structlog.get_logger("replay.replay")


async def rewind_group(
    *,
    topic: str,
    group_id: str,
    not_before: datetime,
) -> dict[int, int]:
    """Seek the given consumer group to the earliest offset >= `not_before` for each partition.

    Returns {partition: new_offset}.
    """
    if not_before.tzinfo is None:
        not_before = not_before.replace(tzinfo=timezone.utc)

    consumer = AIOKafkaConsumer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=group_id,
        enable_auto_commit=False,
    )
    await consumer.start()
    try:
        partitions = consumer.partitions_for_topic(topic) or set()
        if not partitions:
            await consumer._client._wait_on_metadata(topic)
            partitions = consumer.partitions_for_topic(topic) or set()
        tps = [TopicPartition(topic, p) for p in partitions]
        ms = int(not_before.timestamp() * 1000)
        offsets_for_times = await consumer.offsets_for_times({tp: ms for tp in tps})
        new_offsets: dict[int, int] = {}
        for tp, info in offsets_for_times.items():
            if info is None:
                continue
            consumer.seek(tp, info.offset)
            new_offsets[tp.partition] = info.offset
        # Commit the seek so the consumer group sticks at this offset.
        await consumer.commit({tp: info.offset for tp, info in offsets_for_times.items() if info is not None})
        log.info(
            "rewind.done",
            topic=topic,
            group=group_id,
            not_before=not_before.isoformat(),
            partitions=len(new_offsets),
        )
        return new_offsets
    finally:
        await consumer.stop()
