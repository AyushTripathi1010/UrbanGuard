"""raw-frames consumer: CLIP-gate, ResNet-score, emit Alert onto alerts topic."""

from __future__ import annotations

import asyncio
import base64
import io
import uuid

import structlog
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.coordinator.assignors.sticky.sticky_assignor import StickyPartitionAssignor
from PIL import Image
from shared.kafka_io import send_model
from shared.settings import settings

from detect.clip_classifier import classify
from detect.resnet_scorer import score_severity
from shared import ALERTS, RAW_FRAMES, Alert, Frame

log = structlog.get_logger("detect.consumer")


async def run() -> None:
    consumer = AIOKafkaConsumer(
        RAW_FRAMES,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_group_detect,
        auto_offset_reset="latest",
        enable_auto_commit=False,
        session_timeout_ms=45_000,
        partition_assignment_strategy=(StickyPartitionAssignor,),
    )
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        enable_idempotence=True,
        acks="all",
        linger_ms=10,
        compression_type="lz4",
    )
    await consumer.start()
    await producer.start()
    log.info(
        "detect.started",
        group=settings.kafka_group_detect,
        clip_threshold=settings.clip_accident_threshold,
        resnet_threshold=settings.resnet_severity_threshold,
    )
    try:
        async for record in consumer:
            try:
                frame = Frame.model_validate_json(record.value)
            except Exception as exc:
                log.warning("frame.parse_failed", error=str(exc), partition=record.partition)
                await consumer.commit()
                continue

            decision = await asyncio.to_thread(_classify_and_score, frame)
            if decision is not None:
                await send_model(producer, ALERTS, decision, key=frame.camera_id)
                log.info(
                    "alert.emitted",
                    alert=decision.alert_id,
                    camera=decision.camera_id,
                    clip=decision.clip_score,
                    severity=decision.resnet_severity,
                )
            await consumer.commit()
    finally:
        await consumer.stop()
        await producer.stop()


def _classify_and_score(frame: Frame) -> Alert | None:
    """Sync inference path — runs on a worker thread so the event loop stays free."""
    jpeg = base64.b64decode(frame.jpeg_bytes_b64)
    image = Image.open(io.BytesIO(jpeg)).convert("RGB")

    pred = classify(image)
    if not pred.is_incident:
        return None

    severity, _ = score_severity(image)
    if severity < settings.resnet_severity_threshold:
        return None

    return Alert(
        alert_id=uuid.uuid4().hex,
        frame_id=frame.frame_id,
        camera_id=frame.camera_id,
        zone_id=frame.zone_id,
        clip_label=pred.label,
        clip_score=pred.incident_score,
        resnet_severity=severity,
        geo=frame.geo,
    )
