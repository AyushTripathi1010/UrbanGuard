from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import pytest
from aiokafka import AIOKafkaProducer
from ingest.camera import CameraProducer, CameraSpec
from ingest.video_loader import synthesize_clip
from shared.settings import settings
from shared.testing import requires_kafka

from shared import RAW_FRAMES, Frame, consumer


@pytest.fixture
def tiny_clip(tmp_path: Path) -> Path:
    return synthesize_clip(tmp_path / "tiny.mp4", seconds=2, fps=30, width=160, height=120)


@pytest.mark.asyncio
@requires_kafka
async def test_camera_producer_emits_frames_to_raw_frames(tiny_clip: Path) -> None:
    cam_id = f"cam-{uuid.uuid4().hex[:6]}"
    spec = CameraSpec(camera_id=cam_id, zone_id="z-test", clip_path=tiny_clip, target_fps=2)

    group = f"ingest-test-{uuid.uuid4().hex[:6]}"

    async with consumer(RAW_FRAMES, group_id=group, auto_offset_reset="latest") as c:
        await c.seek_to_end()

        producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            enable_idempotence=True,
            acks="all",
            linger_ms=10,
            compression_type="lz4",
        )
        await producer.start()
        cam = CameraProducer(spec, producer)
        await cam.start()
        try:
            received: list[Frame] = []
            for _ in range(3):
                rec = await asyncio.wait_for(c.getone(), timeout=15.0)
                f = Frame.model_validate_json(rec.value)
                if f.camera_id == cam_id:
                    received.append(f)
            assert len(received) == 3
            assert {f.zone_id for f in received} == {"z-test"}
            assert all(f.width == 160 and f.height == 120 for f in received)
            assert all(f.jpeg_bytes_b64 for f in received)
        finally:
            await cam.stop()
            await producer.stop()
